#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
docker_bin=${DOCKER_BIN:-docker}
image=${PROJECT3_IMAGE:-project3-c-dev:bookworm}
if [ "${1:-}" = build ]; then
    exec "$docker_bin" build -t "$image" -f "$root/scripts/dev/Dockerfile" "$root/scripts/dev"
fi
exec "$docker_bin" run --rm --init -v "$root:/work" "$image" "$@"
