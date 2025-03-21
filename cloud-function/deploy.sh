#!/bin/sh

# your function name
func_name='yndx-maps'

# zip needed stuff
zip -9 -f cloud-function.zip requirements.txt *.py

# add cloud function version
# assuming the function already exists
yc serverless function version create \
  --function-name="$func_name" \
  --runtime python312 \
  --entrypoint index.handler \
  --memory 128m \
  --execution-timeout 10s \
  --source-path ./cloud-function.zip

# сделать функцию публичной
yc serverless function allow-unauthenticated-invoke "$func_name"