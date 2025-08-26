import json
import requests
import logging
import gpxpy
import srtm
from bs4 import BeautifulSoup


config = {
    "local_cache_dir": "/tmp", # for SRTM data
    "summary_output_limit": 10, # max number of entries per type in gpx summary
    }


class GeoObject:
    def __init__(self, name: str, coordinates: list):
        self.name = name
        self.coordinates = coordinates # list of 2 or list of lists of 2


def get_yandex_maps_json(url: str) -> dict:
    
    # imitate real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/142.0",
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
    if response.status_code == 404:
        raise ConnectionError(
            f'Страница не найдена: HTTP {response.status_code}. '
            f'Проверьте <a href="{url}">ввеённый вами адрес</a> и скопируйте его правильно. '
            'Рекомендуется пользоваться функцией "Поделиться" или копировать адрес из адресной строки браузера.'
            )
    elif response.status_code != 200:
        raise ConnectionError(
            f'Страница карты не загрузилась: HTTP {response.status_code}. '
            'Проверьте адрес и попробуйте через некоторое время.'
            )
    
    # Находим элемент с нужным атрибутом
    soup = BeautifulSoup(response.text, 'html.parser')
    json_script = soup.find('script', attrs={'type': 'application/json', 'class': 'state-view'})
    if json_script is None:
        raise ValueError(
            'State-view не найден. Это точно Яндекс.Карты? '
            'Возможно, страница не загрузилась (такое бывает). '
            f'Проверьте <a href="{url}">адрес</a> и попробуйте через некоторое время.'
            )
    if len(json_script.string) < 1024: # min practical state-view length 50Kb
        logging.warning(f'State-view length: {len(json_script.string)}')
        raise ValueError(
            'Страница карты не загрузилась должным образом (такое бывает). '
            f'Проверьте <a href="{url}">её адрес</a> и попробуйте через некоторое время.'
            )
    # Преобразуем строку в JSON объект
    return json.loads(json_script.string)


def get_yandex_track_features(yandex_maps_json: dict) -> tuple[list, list]:
    '''
    Extracts line and placemark geographic features from a Yandex Maps JSON structure.

    Parses the provided Yandex Maps JSON to extract geographic features such as lines (routes or user-defined paths) and placemarks (points of interest).
    Attempts to identify multiple sources of geospatial data, including usermap features, router waypoints, navigation routes, and ruler-created segments.
    Each extracted feature is converted into a `GeoObject`, and collected into separate lists for lines and placemarks.

    Raises:
        ValueError: If no supported geospatial data is found.

    Returns:
        tuple[list, list]: A tuple containing a list of line GeoObjects and a list of placemark GeoObjects.

    (AI generated)
    '''
    lines, placemarks = [], []
    
    try:
        # usermap features
        for feature in yandex_maps_json['config']['userMap']['features']:
            if feature['type'] == 'line':
                lines.append(GeoObject(feature['title'], feature['geometry']['coordinates']))
            elif feature['type'] == 'placemark':
                placemarks.append(GeoObject(feature['title'], feature['coordinates']))
        logging.info(f'Found usermap with {len(lines)} lines and {len(placemarks)} placemarks')
    except TypeError:
        logging.error(f'State-view length: {len(json.dumps(yandex_maps_json))}')
        raise ValueError(
            'Cтраница карты не (правильно) загрузилась. '
            'Проверьте адрес и попробуйте через некоторое время.'
            )
    except KeyError:
        pass # Not a usermap
        
    try:
        # normal map waypoints
        for point in yandex_maps_json['config']['routerResponse']['waypoints']:
            placemarks.append(GeoObject(point.get('name', 'POI'), point['coordinates']))
        logging.info(f'Found {len(placemarks)} waypoints')
    except KeyError:
        pass # No waypoints on map

    try:
        # normal map routes - маршруты навигации, проложенные яндексом
        selected_route = int(yandex_maps_json['config']['query'].get('rtn', 0))
        try:
            route = yandex_maps_json['config']['routerResponse']['routes'][selected_route]
        except IndexError: # one route on map and misleading index = 1?
            logging.warning(f'Route index {selected_route} out of range {len(yandex_maps_json["config"]["routerResponse"]["routes"])}')
            route = yandex_maps_json['config']['routerResponse']['routes'][0]
        route_name = f'{route.get('type', 'Route')} {round(route['distance']['value']/1000,1):.1f} km'
        lines.append(GeoObject(route_name, route['coordinates']))
        logging.info(f'Found route {selected_route}/{len(yandex_maps_json["config"]["routerResponse"]["routes"])}: {route_name}')
    except KeyError:
        pass # No routes on map
    except TypeError:
        if type(yandex_maps_json['config']['query']['rtn']) == list:
            logging.error('Error: doubled url')
            raise ValueError(
                'Проверьте введенный вами адрес и вставьте его правильно (один раз). '
                'Рекомендуется пользоваться функцией "Поделиться" или копировать адрес из адресной строки браузера.'
                ) # Broken URL due to user error - autocorrected at frontend

    try:
        # ruler - отрезки, созданные линейкой
        ruler = GeoObject('Ruler', [pt['coordinates'] for pt in yandex_maps_json['ruler']['points']])
        if len(ruler.coordinates) > 1:
            lines.append(ruler)
            logging.info(f'Found ruler with {len(ruler.coordinates)} points')
    except KeyError:
        pass # No ruler on map
    
    if len(lines) + len(placemarks) == 0:
        if 'routePoints' in yandex_maps_json['config']:
            logging.warning('Map with routePoints not supported')
            raise ValueError(
                'Данный тип маршрута не поддерживается (координаты не встроены в страницу). '
                'Такое случается с длинными маршрутами (>300 км) и исправлению не поддается. '
                'Сократите маршрут или перерисуйте его в <a href="https://yandex.ru/map-constructor/">конструкторе карт</a>.'
                )
        elif 'bookmarksPublicList' in yandex_maps_json['config']:
            logging.warning('Map with bookmarksPublicList not supported')
            raise ValueError(
                'Это похоже на карту с публичным спискм мест. '
                'У них нет доступных координат, поэтому выгружать нечего. При необходимости '
                'отметьте те же точки в <a href="https://yandex.ru/map-constructor/">конструкторе карт</a>.'
                )
        else:
            logging.warning('No known geodata on map')
            raise ValueError(
                'Поддерживаемые геоданные на карте не найдены. '
                'Либо на карте нет маршрута, либо данная его разновидность не поддерживается. '
                'Можно перерисовать маршрут в <a href="https://yandex.ru/map-constructor/">конструкторе карт</a> '
                '- это самый надежный вариант.'
                )
    
    return lines, placemarks


def create_gpx(gpx=None, routes=None, tracks=None, track_segments=None, places=None,  add_elevation=False) -> gpxpy.gpx.GPX:
    '''
    gpx: если указан, данные добавляются в переданный объект gpxpy.gpx.GPX
    
    Из линейных Яндекс-объектов:
        routes: создает именованные маршруты
        tracks: создает именованные треки
        track_segments: создает один безымянный трек с сегментами
    
    Из точечных Яндекс-объектов:
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
        
        logging.info('Elevation added')
    
    return gpx


def get_gpx_summary(gpx: gpxpy.gpx.GPX, output_limit=config['summary_output_limit']) -> str:
    summary = []
    
    # Waypoints section
    if gpx.waypoints:
        summary.append(f"Путевые точки ({len(gpx.waypoints)}):")
        for waypoint in gpx.waypoints[:output_limit]:
            line = f"- {waypoint.name or 'Без имени'}"
            if waypoint.elevation is not None:
                line += f" - {int(round(waypoint.elevation))} м"
            summary.append(line)
        if len(gpx.waypoints) > output_limit:
            summary.append('...')
    
    # Tracks section
    if gpx.tracks:
        summary.append(f"Треки ({len(gpx.tracks)}):")
        for track in gpx.tracks[:output_limit]:
            summary.append(f" - {track.name or 'Без имени'} - {track.length_2d() / 1000:.1f} км")
        if len(gpx.tracks) > output_limit:
            summary.append('...')
    
    # Routes section
    if gpx.routes:
        summary.append(f"Маршруты ({len(gpx.routes)}):")
        for route in gpx.routes[:output_limit]:
            summary.append(f"- {route.name or 'Без имени'} - {route.length() / 1000:.1f} км")
        if len(gpx.routes) > output_limit:
            summary.append('...')
    
    return '\n'.join(summary)
