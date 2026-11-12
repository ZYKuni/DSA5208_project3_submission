#!/bin/bash
# Usage: scripts/build.sh [cpu|cuda|smoke-cpu|smoke-cuda] [build_dir]
#   cpu  (default): serial + MPI + MPI/OpenMP
#   cuda          : additionally MPI/CUDA
set -euo pipefail
MODE=${1:-cpu}
BUILD=${2:-build}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXTRA=()
case "$MODE" in
  cpu) EXTRA+=(-DENABLE_CUDA=OFF -DBUILD_CLUSTER_SMOKE=OFF) ;;
  cuda) EXTRA+=(-DENABLE_CUDA=ON -DBUILD_CLUSTER_SMOKE=OFF) ;;
  smoke-cpu) EXTRA+=(-DENABLE_CUDA=OFF -DBUILD_CLUSTER_SMOKE=ON) ;;
  smoke-cuda) EXTRA+=(-DENABLE_CUDA=ON -DBUILD_CLUSTER_SMOKE=ON) ;;
  *) printf 'Unknown build mode: %s\n' "$MODE" >&2; exit 2 ;;
esac
if [[ "$BUILD" != /* ]]; then BUILD="$ROOT/$BUILD"; fi
if [[ "$MODE" = *cuda ]]; then
  : "${PCG_CUDA_ARCH:?Set PCG_CUDA_ARCH after checking the allocated GPU}"
  EXTRA+=("-DCMAKE_CUDA_ARCHITECTURES=$PCG_CUDA_ARCH")
fi
cmake -S "$ROOT" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_COMPILER="${CXX:-mpicxx}" "${EXTRA[@]}"
cmake --build "$BUILD" --parallel "${PCG_BUILD_JOBS:-2}"
ctest --test-dir "$BUILD" --output-on-failure
