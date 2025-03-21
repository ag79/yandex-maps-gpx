import json
import requests
import gpxpy
import gpxpy.gpx
import srtm
from bs4 import BeautifulSoup


def get_yandex_maps_json(url: str) -> dict:

    # Загружаем URL
    response = requests.get(url)
    if response.status_code != 200:
        raise ConnectionError(f'Ошибка загрузки страницы: HTTP {response.status_code}')
    
    # Находим элемент с нужным атрибутом
    soup = BeautifulSoup(response.text, 'html.parser')
    json_script = soup.find('script', attrs={'type': 'application/json', 'class': 'state-view'})
    if json_script is None:
        raise AttributeError('На странице не найдены геоданные')

    # Преобразуем строку в JSON объект
    return json.loads(json_script.string)


def get_yandex_track_features(yandex_maps_json: dict) -> tuple[dict, dict]:
    
    lines, placemarks = [], []
    
    for feature in yandex_maps_json['config']['userMap']['features']:
        if feature['type'] == 'line':
            lines.append(feature)
        elif feature['type'] == 'placemark':
            placemarks.append(feature)
    
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
            gpx_route = gpxpy.gpx.GPXRoute(name=line['title'])
            gpx.routes.append(gpx_route)
            # Create points:
            for point in line['geometry']['coordinates']:
                gpx_route.points.append(gpxpy.gpx.GPXRoutePoint(latitude=point[1], longitude=point[0]))
                
    if tracks:
        # multiple tracks with names
        for line in tracks:
            gpx_track = gpxpy.gpx.GPXTrack(name=line['title'])
            gpx.tracks.append(gpx_track)
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)
            # Create points:
            for point in line['geometry']['coordinates']:
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=point[1], longitude=point[0]))

    if track_segments:
        # one track with multiple segments
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)
        for line in track_segments:
            gpx_segment = gpxpy.gpx.GPXTrackSegment()
            gpx_track.segments.append(gpx_segment)
            # Create points:
            for point in line['geometry']['coordinates']:
                gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(latitude=point[1], longitude=point[0]))
    
    if places:
        for place in places:
            waypoint = gpxpy.gpx.GPXWaypoint(latitude=place['coordinates'][1], longitude=place['coordinates'][0], name=place['title'])
            gpx.waypoints.append(waypoint)

    if add_elevation:
        elevation_data = srtm.get_data(local_cache_dir="./")

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

