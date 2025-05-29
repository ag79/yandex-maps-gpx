import json
import requests
import gpxpy
import srtm
from bs4 import BeautifulSoup


config = {
    "local_cache_dir": "/tmp",
    "logging": True
    }


class GeoObject:
    def __init__(self, name: str, coordinates: list):
        self.name = name
        self.coordinates = coordinates # list of 2 or list of lists of 2


def log(message):
    if config['logging']:
        print(message)


def get_yandex_maps_json(url: str) -> dict:
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en,ru",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "close",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "DNT": "1"
        }

    # Загружаем URL
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        raise ConnectionError(f'Page load error: HTTP {response.status_code}')
    
    # Находим элемент с нужным атрибутом
    soup = BeautifulSoup(response.text, 'html.parser')
    json_script = soup.find('script', attrs={'type': 'application/json', 'class': 'state-view'})
    if json_script is None:
        raise ValueError('State-view not found. Not a Yandex.Maps page?')

    # Преобразуем строку в JSON объект
    return json.loads(json_script.string)


def get_yandex_track_features(yandex_maps_json: dict) -> tuple[list, list]:
    
    lines, placemarks = [], []
    
    try:
        # usermap features
        for feature in yandex_maps_json['config']['userMap']['features']:
            if feature['type'] == 'line':
                lines.append(GeoObject(feature['title'], feature['geometry']['coordinates']))
            elif feature['type'] == 'placemark':
                placemarks.append(GeoObject(feature['title'], feature['coordinates']))
        log('Usermap')
    except KeyError:
        pass #log('Not a usermap')
        
    try:
        # normal map waypoints
        for point in yandex_maps_json['config']['routerResponse']['waypoints']:
            placemarks.append(GeoObject(point.get('name', 'POI'), point['coordinates']))
    except KeyError:
        pass #log('No waypoints on map')

    try:
        # normal map routes - маршруты навигации, проложенные яндексом
        selected_route = int(yandex_maps_json['config']['query'].get('rtn', 0))
        route = yandex_maps_json['config']['routerResponse']['routes'][selected_route]
        lines.append(GeoObject(f'{route.get('type', 'Route')} {round(route['distance']['value']/1000,1):.1f} km',
                                route['coordinates']))
        log('Normal map with routes')
    except KeyError:
        pass #log('No routes on map')

    try:
        # ruler - отрезки, созданные линейкой
        ruler = GeoObject('Ruler', [pt['coordinates'] for pt in yandex_maps_json['ruler']['points']])
        if len(ruler.coordinates) > 1:
            lines.append(ruler)
            log('Normal map with ruler')
    except KeyError:
        pass #log('No ruler on map')
    
    if len(lines) + len(placemarks) == 0:
        log('No geodata on map')
        raise ValueError('Поддерживаемые геоданные на карте не найдены. Создайте какой-нибудь маршрут.')
    
    return lines, placemarks


def create_gpx(gpx=None, routes=None, tracks=None, track_segments=None, places=None,  add_elevation=False) -> gpxpy.gpx.GPX:
    '''
    gpx: если указан, данные добавляются в переданный объект gpxpy.gpx.GPX
    
    Из Яндекс-объектов "line":
        routes: создает именованные маршруты
        tracks: создает именованные треки
        track_segments: создает один безымянный трек с сегментами
    
    Из Яндекс-объектов "placemark":
        places: создает именованные путевые точки
        
    add_elevation: добавляет высоту из SRTM во все объекты
    '''
    
    if gpx is None:
        gpx = gpxpy.gpx.GPX()
    
    if routes:
        # multiple routes with names
        for line in routes:
            gpx_route = gpxpy.gpx.GPXRoute(name=line.name)
            gpx.routes.append(gpx_route)
            # Create points:
            for point in line.coordinates:
                gpx_route.points.append(gpxpy.gpx.GPXRoutePoint(latitude=point[1], longitude=point[0]))
                
    if tracks:
        # multiple tracks with names
        for line in tracks:
            gpx_track = gpxpy.gpx.GPXTrack(name=line.name)
            gpx.tracks.append(gpx_track)
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)
            # Create points:
            for point in line.coordinates:
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=point[1], longitude=point[0]))

    if track_segments:
        # one track with multiple segments in original order
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)
        for line in track_segments:
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)
            # Create points:
            for point in line.coordinates:
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=point[1], longitude=point[0]))
    
    if places:
        for place in places:
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=place.coordinates[1], longitude=place.coordinates[0], name=place.name)
            gpx.waypoints.append(waypoint)

    if add_elevation:
        elevation_data = srtm.get_data(local_cache_dir=config['local_cache_dir'])

        # tracks
        elevation_data.add_elevations(gpx, smooth=True)
        
        # routes
        for route in gpx.routes:
            for point in route.points:
                point.elevation = elevation_data.get_elevation(point.latitude, point.longitude)
        
        # waypoints
        for point in gpx.waypoints:
            point.elevation = elevation_data.get_elevation(point.latitude, point.longitude)
    
    return gpx


def get_gpx_summary(gpx: gpxpy.gpx.GPX) -> str:
    summary = []
    
    # Waypoints section
    if gpx.waypoints:
        summary.append("Путевые точки:")
        for waypoint in gpx.waypoints:
            line = f"- {waypoint.name or 'Без имени'}"
            if waypoint.elevation is not None:
                line += f" - {int(round(waypoint.elevation))} м"
            summary.append(line)
    
    # Tracks section
    if gpx.tracks:
        summary.append("Треки:")
        for track in gpx.tracks:
            summary.append(f" - {track.name or 'Без имени'} - {track.length_2d() / 1000:.1f} км")
    
    # Routes section
    if gpx.routes:
        summary.append("Маршруты:")
        for route in gpx.routes:
            summary.append(f"- {route.name or 'Без имени'} - {route.length() / 1000:.1f} км")
    
    return '\n'.join(summary)
