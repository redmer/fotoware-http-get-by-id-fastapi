#!/usr/bin/env bash

# - starts Litestar application

set -o errexit
set -o pipefail
set -o nounset

echo Starting app...
gunicorn \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --log-config-json log_conf.json \
  --access-logfile - \
  app.main:app
