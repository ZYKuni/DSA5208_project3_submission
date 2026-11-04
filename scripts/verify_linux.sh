#!/usr/bin/env bash
# Shared clean Linux/GCC verification entry point. Output must not exist.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $# -lt 1 || $# -gt 2 || "$(uname -s)" != Linux ]]; then
  echo 'Usage (Linux only): bash scripts/verify_linux.sh NEW_OUTPUT_DIRECTORY [serial|mpi|openmp|hybrid]' >&2
  exit 2
fi
mode="${2:-serial}"
case "$mode" in
  serial) mpi=OFF; openmp=OFF ;;
  mpi) mpi=ON; openmp=OFF ;;
  openmp) mpi=OFF; openmp=ON ;;
  hybrid) mpi=ON; openmp=ON ;;
  *) echo "Mode must be serial, mpi, openmp or hybrid" >&2; exit 2 ;;
esac
mkdir "$1"
out="$(cd "$1" && pwd)"
finish() {
  rc=$?
  trap - EXIT
  # Preserve incomplete runs too: a CTest timeout may precede summary creation.
  for entry in mpi-validation parallel-acceptance Testing; do
    if [[ -d "$out/build/$entry" ]]; then
      cp -R "$out/build/$entry" "$out/$entry" || rc=1
    fi
  done
  printf '%s\n' "$rc" > "$out/exit_code.txt"
  exit "$rc"
}
trap finish EXIT
export LC_ALL=C TZ=UTC PYTHONDONTWRITEBYTECODE=1
export CC=gcc CXX=g++
# Correctness runs only; do not reuse this waiting policy for timing experiments.
export OMP_WAIT_POLICY=PASSIVE OMP_DYNAMIC=FALSE
{
  date -u +%Y-%m-%dT%H:%M:%SZ
  printf "Verification mode: %s\n" "$mode"
  uname -a
  cat /etc/os-release
  gcc --version
  g++ --version
  cmake --version
  python3 --version
  make --version
  if [[ "$mpi" == ON ]]; then
    command -v mpicxx mpiexec
    mpicxx --showme:version
    mpiexec --version
    env | sort | grep -E "^(OMP_|OMPI_)" || true
  fi
  if [[ "$openmp" == ON ]]; then
    env | sort | grep -E "^OMP_" || true
  fi
  ldd --version
  printf '\nSource Git state (may be unavailable in exported snapshot):\n'
  git -C "$root" rev-parse HEAD || true
  git -C "$root" status --short || true
  printf '\nInstalled build packages:\n'
  if command -v dpkg-query >/dev/null; then
    dpkg-query -W gcc g++ cmake make python3 libc6
  fi
} > "$out/environment.txt" 2>&1
python3 - "$root" "$out/source_manifest.json" <<'PY'
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
files = [root / p for p in ('CMakeLists.txt', 'requirements.txt')]
for directory in ('src', 'include', 'scripts', 'tests', 'configs', '.github'):
    files.extend(p for p in (root / directory).rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
manifest = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files)}
pathlib.Path(sys.argv[2]).write_text(json.dumps(manifest, indent=2) + '\n')
PY
cmake -S "$root" -B "$out/build" -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=ON -DENABLE_MPI="$mpi" -DENABLE_OPENMP="$openmp" -DCMAKE_CXX_COMPILER=g++ \
  -DPython3_EXECUTABLE="$(command -v python3)" 2>&1 | tee "$out/configure.log"
cmake --build "$out/build" --parallel 2 2>&1 | tee "$out/build.log"
(cd "$out/build" && ctest --verbose --output-on-failure) 2>&1 | tee "$out/ctest.log"
python3 "$root/scripts/run_acceptance.py" --exe "$out/build/poisson_serial" \
  --config "$root/configs/acceptance_serial.json" --output "$out/acceptance" \
  2>&1 | tee "$out/acceptance.log"
cp "$out/build/CMakeCache.txt" "$out/CMakeCache.txt"
cp "$out/build/CMakeFiles/poisson_core.dir/flags.make" "$out/compiler_flags.txt"
cp "$out/build/validation/summary.json" "$out/serial_validation_summary.json"
sha256sum "$out/build/poisson_serial" > "$out/executable.sha256"
if [[ "$mpi" == ON ]]; then
  sha256sum "$out/build/poisson_mpi" >> "$out/executable.sha256"
fi
if [[ "$openmp" == ON ]]; then
  sha256sum "$out/build/poisson_openmp" >> "$out/executable.sha256"
  if [[ "$mpi" == ON ]]; then
    sha256sum "$out/build/poisson_hybrid" >> "$out/executable.sha256"
  fi
fi
echo "Linux GCC $mode build, CTest and unified acceptance passed."
