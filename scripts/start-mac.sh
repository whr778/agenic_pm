#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="pm-mvp:dev"
CONTAINER_NAME="pm-mvp"
DATA_DIR="$ROOT_DIR/backend/data"

cd "$ROOT_DIR"

mkdir -p "$DATA_DIR"

retry_command() {
  local attempts="$1"
  local delay_seconds="$2"
  shift 2

  local try=1
  until "$@"; do
    if [[ "$try" -ge "$attempts" ]]; then
      echo "Command failed after ${attempts} attempts: $*" >&2
      return 1
    fi
    echo "Command failed (attempt ${try}/${attempts}), retrying in ${delay_seconds}s..." >&2
    sleep "$delay_seconds"
    try=$((try + 1))
  done
}

if ! retry_command 3 3 docker build -t "$IMAGE_NAME" .; then
  echo "Falling back to local-only Docker build (no registry pull)." >&2

  if docker image inspect node:22.14-alpine3.21 >/dev/null 2>&1 \
    && docker image inspect python:3.12.9-slim >/dev/null 2>&1; then
    DOCKER_BUILDKIT=0 docker build --pull=false -t "$IMAGE_NAME" .
  else
    echo "Unable to build image: Docker Hub is unreachable and base images are not cached locally." >&2
    echo "When network is available, run: docker pull node:22.14-alpine3.21 && docker pull python:3.12.9-slim" >&2
    exit 1
  fi
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

docker run -d \
  --name "$CONTAINER_NAME" \
  -p 8000:8000 \
  -v "$DATA_DIR:/app/backend/data" \
  --env-file "$ROOT_DIR/.env" \
  "$IMAGE_NAME"

echo "PM MVP running at http://localhost:8000"
