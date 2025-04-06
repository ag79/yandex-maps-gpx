#!/bin/sh

# your function name
func_name='yndx-maps-v2'

yell() { echo "$0: $*" >&2; }
die() { yell "$*"; exit 9; }

# check YC installed
which yc > /dev/null || die "Install yandex cloud CLI, see: https://cloud.yandex.ru/docs/cli/quickstart"

# zip needed stuff
zip -9 -f cloud-function.zip requirements.txt gpx_utils.py index.py

# create cloud function
yc serverless function create --name="$func_name" \
  --description "Convert Yandex maps tracks to gpx"

# add cloud function version
yc serverless function version create \
  --function-name="$func_name" \
  --runtime python312 \
  --entrypoint index.handler \
  --memory 128m \
  --execution-timeout 10s \
  --no-logging \
  --source-path ./cloud-function.zip

# save function url for test.ipynb
yc serverless function get "$func_name" | grep "http_invoke_url" |  cut -d' ' -f2 | tr -d '\n' > func-url.cfg

# сделать функцию публичной
yc serverless function allow-unauthenticated-invoke "$func_name"