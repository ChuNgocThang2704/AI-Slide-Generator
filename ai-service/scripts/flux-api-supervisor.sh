#!/bin/bash
set -e

utils=/opt/supervisor-scripts/utils
. "${utils}/logging.sh"
. "${utils}/environment.sh"

if [ -f /root/flux-server.env ]; then
    set -a
    . /root/flux-server.env
    set +a
fi

source /venv/main/bin/activate
cd /root

export FLUX_HOST="${FLUX_HOST:-0.0.0.0}"
export FLUX_PORT="${FLUX_PORT:-8080}"
export FLUX_MODEL_ID="${FLUX_MODEL_ID:-black-forest-labs/FLUX.1-schnell}"
export HF_HOME="${HF_HOME:-/root/.cache/huggingface}"

exec python /root/flux_api_server.py
