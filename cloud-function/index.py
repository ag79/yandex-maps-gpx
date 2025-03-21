from gpx_utils import get_yandex_maps_json, get_yandex_track_features, create_gpx



def handler(event, context):
    # Получаем параметры из GET-запроса
    query_params = event.get('queryStringParameters', {})
    url = query_params.get('url')
    
    yandex_maps_json = get_yandex_maps_json(url)
    lines, placemarks = get_yandex_track_features(yandex_maps_json)
    gpx = create_gpx(tracks=lines, places=placemarks, add_elevation=False)

    return {
        'statusCode': 200,
        "headers": {
            "Content-Type": "application/xml",
            "Content-Disposition": 'attachment; filename="track.gpx"'
        },
        'body': gpx.to_xml(),
    }