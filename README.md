# DSA5208 Project 3 - Reproduction Guide

This submission implements Jacobi iteration for the two-dimensional Poisson equation using serial C++17, MPI, OpenMP, and hybrid MPI + OpenMP. It compares blocking Sendrecv with nonblocking halo exchange, strong and weak scaling, and the balance between MPI ranks and OpenMP threads.

| Team member | Student ID |
| --- | --- |
| Yikun Zhao | A0353894M |
| Jiahao Zhou | A0354090J |
| Zheke Chen | A0356140M |

Read **[report.pdf](report.pdf)** for the algorithm, parallel design, correctness results, Vanda runtimes, scaling analysis, limitations, and AI disclosure.

Repository: <https://github.com/ZYKuni/DSA5208_project3_submission>.

Run commands from the directory containing this README. Build and test output directories should be new. The sections below cover local builds and verification. New cluster measurements require access to Vanda and an allocation under your own account.

## 1. Package contents

```text
DSA5208_project3_submission/
├── report.pdf                     # Sole final report
├── report_facts.json              # Report statistics and PDF hash
├── README.md                      # This guide
├── CMakeLists.txt
├── requirements.txt               # Validation uses Python standard library only
├── requirements-analysis.txt      # Optional analysis dependencies
├── requirements-report.txt        # Pinned report-generation dependencies
├── src/                           # Four executable entry points and solver kernels
├── include/                       # Shared configuration, grid, and kernel interfaces
├── tests/                         # C++ contracts, independent oracles, CSV fixtures
├── configs/                       # Acceptance and experiment configurations
├── scripts/                       # Validation, collection, statistics, report generation
│   ├── cluster/                   # Vanda PBS scripts and experiment preparation
│   └── dev/                       # Optional development-container recipe
├── report/
│   ├── source/team.json           # Member names, IDs, repository URL
│   └── figures/Vanda_1103/        # Report figures
├── .github/workflows/             # Four-mode Linux GCC workflow
└── SUBMISSION_MANIFEST.json       # Per-file SHA256 and source provenance
```

Git metadata, virtual environments, local build trees, and historical progress PDFs are excluded.

## 2. Requirements and supported environments

- C++17 compiler, CMake >= 3.16, and Make or another CMake build backend.
- Python >= 3.8 for validation and collection. No third-party Python package is needed for these operations.
- Open MPI development libraries and `mpiexec` for MPI and hybrid targets.
- An OpenMP-capable compiler/runtime for OpenMP and hybrid targets. GCC supplies this on Linux; macOS Apple Clang does not provide OpenMP by default.
- Report generation: Python >= 3.10 and the packages in `requirements-report.txt` (the recorded rebuild used Python 3.12).

Ubuntu example:

```sh
sudo apt-get update
sudo apt-get install -y gcc g++ cmake make python3 openmpi-bin libopenmpi-dev
```

On macOS, a serial build can use Apple Clang. For OpenMP/hybrid, use a GCC or LLVM installation that supports OpenMP and a compatible MPI installation; select its actual C++ compiler path with `-DCMAKE_CXX_COMPILER=/path/to/g++`. Do not reuse a CMake build directory after changing the compiler.

Vanda timing environment: GCC 12.3.0, Open MPI 4.1.8, CMake 3.26.3, Release `-O3 -DNDEBUG`, one node, 16 assigned physical cores of an Intel Xeon Platinum 8452Y. Numerical verification is portable; performance conclusions apply to that allocation, placement, and workload.

## 3. Quick verification: serial

```sh
cmake -S . -B build-serial -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_MPI=OFF -DENABLE_OPENMP=OFF
cmake --build build-serial --parallel 2
ctest --test-dir build-serial --output-on-failure
python3 scripts/run_acceptance.py --exe build-serial/poisson_serial \
  --config configs/acceptance_serial.json --output build-serial-acceptance
```

Expected: 6 CTest groups pass; the standalone acceptance suite passes 14 cases. CTest groups include additional numerical, CLI, oracle, and tooling checks; these are not six individual numerical examples.

A single solve:

```sh
build-serial/poisson_serial --n 127 --mode converge --problem continuous-sine \
  --iterations 200000 --tol 1e-8 --check-every 20
```

The program emits one JSON object with the actual iteration count, residual, errors, and solve time. Fixed mode performs exactly the requested number of sweeps. Convergence mode may stop early. A fixed-sweep large-grid performance run is not a converged PDE solution.

## 4. MPI, OpenMP, and hybrid builds

Both feature switches are explicit to avoid cached settings:

```sh
# MPI only
cmake -S . -B build-mpi -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_MPI=ON -DENABLE_OPENMP=OFF
cmake --build build-mpi --parallel 2

# OpenMP only (select an OpenMP-capable compiler as needed)
cmake -S . -B build-openmp -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_MPI=OFF -DENABLE_OPENMP=ON
cmake --build build-openmp --parallel 2

# Hybrid: builds all four executables
cmake -S . -B build-hybrid -DCMAKE_BUILD_TYPE=Release \
  -DENABLE_MPI=ON -DENABLE_OPENMP=ON
cmake --build build-hybrid --parallel 2
```

For correctness runs, set:

```sh
export OMP_DYNAMIC=FALSE
export OMP_WAIT_POLICY=PASSIVE
ctest --test-dir build-mpi --output-on-failure
ctest --test-dir build-openmp --output-on-failure
ctest --test-dir build-hybrid --output-on-failure
```

Expected CTest groups: MPI 7/7, OpenMP 8/8, hybrid 9/9. The current mixed matrix checks 390 oracle cases plus five negative cases; the MPI-only matrix checks 124 cases plus four negative cases. These suites overlap and should not be added into a count of independent mathematical problems. The historical Vanda pilot used 294 mixed cases; the later 390-case expansion was verified separately on Linux/CI.

The tests need permission to start up to four MPI ranks and use multiple threads. On a small Open MPI workstation or CI runner, correctness-only oversubscription can be enabled with `OMPI_MCA_rmaps_base_oversubscribe=1` and `OMPI_MCA_hwloc_base_binding_policy=none`. These settings are not suitable for reproducing the formal timing setup. Do not run MPI as root on a normal workstation.

Example executions:

```sh
OMP_NUM_THREADS=4 build-openmp/poisson_openmp --n 127 --iterations 100 \
  --mode fixed --problem discrete-mixed

mpiexec -n 3 build-mpi/poisson_mpi --n 127 --iterations 100 \
  --mode fixed --problem discrete-mixed --communication sendrecv

OMP_NUM_THREADS=2 mpiexec -n 2 build-hybrid/poisson_hybrid --n 127 \
  --iterations 100 --mode fixed --problem discrete-mixed --communication overlap
```

`poisson_mpi` always uses one thread per rank. `OMP_NUM_THREADS` selects threads only for OpenMP-enabled executables. Hybrid MPI calls run on the initializing thread with `MPI_THREAD_FUNNELED`; actual ranks and thread teams are checked. The number of ranks cannot exceed N.

For Linux, `bash scripts/verify_linux.sh NEW_DIRECTORY MODE` provides the complete build, CTest, serial acceptance, environment capture, source/binary hashes, and failure-log retention. MODE is `serial`, `mpi`, `openmp`, or `hybrid`; the output directory must not exist. The same entry point is used by the four-mode GitHub workflow.

## 5. Full-grid serial/parallel comparison

```sh
mkdir -p build-grid-check
build-serial/poisson_serial --n 7 --iterations 5 --problem discrete-mixed \
  --solution build-grid-check/serial.csv
mpiexec -n 3 build-mpi/poisson_mpi --n 7 --iterations 5 \
  --problem discrete-mixed --communication overlap \
  --solution build-grid-check/mpi.csv
python3 scripts/compare_grids.py --n 7 \
  --reference build-grid-check/serial.csv --candidate build-grid-check/mpi.csv \
  --report build-grid-check/comparison.json
```

The comparator validates all `(N+2)^2` points, unique coordinates, finite values, and zero physical boundaries. It reports maximum absolute error and relative L2 error; passing requires every point to satisfy `abs(candidate-reference) <= 1e-10 + 1e-10*abs(reference)`. Independent dense and modal references in the test suites avoid validating parallel code solely against the serial implementation.

## 6. Report figures and measurement notes

`report.pdf` and the figures in `report/figures/Vanda_1103/` were generated by `scripts/build_cluster_report.py` from the raw Vanda job output (performance job 1514382, validation job 1514325). That raw output is not included in this repository, so the report builder and `scripts/audit_vanda.py` cannot be rerun from this tree alone; the measured values they produce are reported in `report.pdf` and `report_facts.json`.

No timing sample was replaced or removed. Single-rank MPI and some thread layouts show substantial variability. Communication ranges overlap; the data do not establish a robust benefit from nonblocking exchange. All measurements are single-node CPU experiments.

## 7. New Vanda experiments (optional; not needed to inspect the submission)

Generic entry points are `scripts/cluster/vanda_cpu_pilot.pbs`, `vanda_cpu_measure.pbs`, and `prepare_vanda_experiments.py`. Review account paths, PBS allocation, pilot job ID, MPI placement, and uploaded helper filenames before submission under your own account. The historical measurement script refers to an uploaded helper named `prepare_vanda_experiments_v3.py`; create that copy if reusing it.

Formal measurements used ACTIVE OpenMP waiting, core binding, verified nonoverlapping physical-core placement, one warmup, and five measured repetitions. Runtime excludes initialization, process startup, gathering, and file I/O, while including halo exchanges and scheduled convergence reductions. Never interpret workstation verification times as new Vanda measurements.

## 8. File integrity and AI usage

`SUBMISSION_MANIFEST.json` lists every delivered file except itself, with SHA256 hashes and preparation provenance. The folder is runnable without Git or an internet connection once build dependencies are installed.

AI usage is disclosed in the AI usage section of `report.pdf`. The report uses actual recorded Vanda outputs.
