import urllib.parse
from gpx_utils import get_yandex_maps_json, get_yandex_track_features, create_gpx


def make_filename(string):
    # URL-encode for safety
    invalid_chars = '<>:"/\\|?* '
    s = ''.join(c if c not in invalid_chars else '_' for c in string)
    s = s + '.gpx'
    return urllib.parse.quote(s)


def handler(event, context):
    ''' GET-query parameters
    
    url: map url
    
    add_elevation: boolean (0/1)
        Add elevation to all objects
    
    lines: "tracks", "routes" or "track_segments"
        Create respective objects in gpx from lines
    
    placemarks: boolean (0/1)
        Include placemarks in gpx
    '''
    query_params = event.get('queryStringParameters', {})
    
    yandex_maps_json = get_yandex_maps_json(query_params.get('url'))
    
    lines, placemarks = get_yandex_track_features(yandex_maps_json)
    
    line_param = query_params.get('lines', 'tracks')
    lines_param = {parameter: lines if line_param == parameter else None \
        for parameter in ("tracks", "routes", "track_segments")}
    
    encoded_filename = make_filename(yandex_maps_json['config']['userMap']['title'] + '_' + line_param)
    del yandex_maps_json
    
    # Note url params are str!
    gpx = create_gpx(**lines_param,
                     places = placemarks if int(query_params.get('placemarks', 0)) else None, 
                     add_elevation = int(query_params.get('add_elevation', 0)))

    return {
        'statusCode': 200,
        "headers": {
            "Content-Type": "application/xml",
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        },
        'body': gpx.to_xml(),
    }