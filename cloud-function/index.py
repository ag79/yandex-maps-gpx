import urllib.parse
import base64
import logging
import warnings
from gpx_utils import get_yandex_maps_json, get_yandex_track_features, create_gpx, get_gpx_summary


warnings.filterwarnings("ignore", category=SyntaxWarning)  # clean up logs from srtm.py issues


def make_filename(string):
    # URL-encode for safety
    invalid_chars = '<>:"/\\|?* '
    s = ''.join(c if c not in invalid_chars else '_' for c in string)
    return urllib.parse.quote(s)


def handler(event, context):
    ''' URL parameters
    
    url: map url
        If not provided, geo content is expected in body
    
    add_elevation: boolean (0/1)
        Add elevation to all objects
    
    lines: "tracks", "routes" or "track_segments"
        Create respective objects in gpx from lines
    
    placemarks: boolean (0/1)
        Include placemarks in gpx
    '''
    query_params = event.get('queryStringParameters', {})
    
    # Param converion and support for non-js form submits
    query_params['placemarks'] = query_params.get('placemarks', '0') in {'1', 'on'}
    query_params['add_elevation'] = query_params.get('add_elevation', '0') in {'1', 'on'}
    
    try:
        ua = event['headers']['User-Agent']
        logging.info(ua)
        if ua.startswith('python-requests') or \
            ua.startswith('curl'):
            return {'statusCode': 403, 'body': 'Forbidden'}
    except KeyError:
        logging.error('No User-Agent?')
        return {'statusCode': 403, 'body': 'Forbidden'}
    
    url = query_params.get('url')
    if url is None:
        # client provides geo content in body
        yandex_maps_json = event.get('body')
        logging.debug('Loaded state-view from body')
    else:
        logging.info(url)
        try:
            yandex_maps_json = get_yandex_maps_json(url)
        except Exception as e:
            logging.error(e)
            return {'statusCode': 400, 'body': str(e)}
    
    try:
        lines, placemarks = get_yandex_track_features(yandex_maps_json)
    except ValueError as e:
        return {'statusCode': 400, 'body': str(e)}
    
    
    line_param = query_params.get('lines', 'routes')
    lines_param = {parameter: lines if line_param == parameter else None \
        for parameter in ("tracks", "routes", "track_segments")}
    
    # construct gpx file name
    try:
        filename = yandex_maps_json['config']['userMap']['title']
    except KeyError:
        filename = 'output'
    logging.info(f'{filename} with {len(lines)} lines and {len(placemarks)} placemarks')
    filename = f'{filename}_{line_param}.gpx'
        
    del yandex_maps_json
    
    # Note url params are str!
    gpx = create_gpx(**lines_param,
                     places = placemarks if query_params['placemarks'] else None,
                     add_elevation = query_params['add_elevation'])

    return {
        'statusCode': 200,
        "headers": {
            "Content-Type": "application/xml",
            "Content-Disposition": f"attachment; filename*=UTF-8''{make_filename(filename)}",
            "X-GPX-Info": base64.b64encode(get_gpx_summary(gpx).encode('utf-8')).decode("utf-8"),
            "Access-Control-Expose-Headers": "Content-Disposition, X-GPX-Info"
        },
        'body': gpx.to_xml(),
    }