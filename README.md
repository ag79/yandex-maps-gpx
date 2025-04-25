# Делаем gpx файл из маршрута Яндекс Карт

Создаем gpx файл с нужными объектами:

- маршрутами
- треками
- путевыми точками

Добавляем в файл высотные данные из [SRTM](http://www2.jpl.nasa.gov/srtm/).

Используем [gpxpy](https://github.com/tkrajina/gpxpy), [SRTM.py](https://github.com/tkrajina/srtm.py).

## Облачная функция [cloud-function](./cloud-function)

То же самое, реализованное в виде облачной функции на Yandex Cloud.

Попробовать в работе: [https://ag79.github.io/yndx-gpx-web](https://ag79.github.io/yndx-gpx-web/)
