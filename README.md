# Parallel Conjugate Gradient for the 2D/3D Poisson Equation (MPI + X)

DSA5208 Project 3, AY2026/27 Semester 1, National University of Singapore.

| Name | Student ID | Main responsibility |
| --- | --- | --- |
| Yikun Zhao | A0353894M | Serial and MPI solvers, validation, report |
| Jiahao Zhou | A0354090J | MPI + OpenMP and MPI + CUDA solvers |
| Zheke Chen | A0356140M | Cluster builds, experiments on Vanda, analysis and figures |

**Report:** [`DSA5208_Project3_Report.pdf`](DSA5208_Project3_Report.pdf). It covers the algorithm,
the parallelisation design, validation, serial/MPI/MPI+X scaling results and the discussion.

## Problem

We solve -Δu = f on the unit square (2D) and the unit cube (3D), with u = 0 on the boundary.
A 5-point (2D) or 7-point (3D) finite-difference stencil gives a sparse symmetric
positive-definite system Au = b, which we solve with the conjugate gradient (CG) method.
A is never stored: each matrix-vector product is a stencil sweep (matrix-free).
The right-hand side comes from the manufactured solution u(x) = Π x_k (1 − x_k) e^{x_k}, so
the discretisation error can be measured exactly. All input data are generated synthetically
by each process for the grid points it owns. No BLAS or LAPACK is used.

## Contents

```
DSA5208_Project3_Report.pdf  final report
CMakeLists.txt               build configuration
include/                     shared headers: CLI parameters, timers, CSV format, model problem,
                             grid block + stencil kernels (grid.hpp), CG driver + Backend interface (cg.hpp)
src/common/                  CG driver (cg.cpp), kernels, CLI parser, CSV writer
src/serial/                  serial backend
src/mpi/                     pure MPI backend: domain decomposition, halo exchange, reductions
src/hybrid_omp/              MPI + OpenMP backend
src/hybrid_cuda/             MPI + CUDA solver; checks/kernel_check.cu tests the GPU kernels
apps/                        one main() per executable
tests/                       validation tests (run by ctest)
scripts/build.sh             configure, build and test
scripts/vanda/               Vanda environment and the PBS jobs used for all reported measurements
scripts/run_*_scaling.py     experiment drivers called by the PBS jobs
scripts/smoke/               small CPU/GPU placement and CUDA-aware MPI probes run before the experiments
```

## Requirements

- C++17 compiler and CMake >= 3.18
- An MPI implementation providing `mpicxx` (Open MPI, MPICH or NVIDIA HPC-X)
- OpenMP support in the compiler (for `poisson_omp`)
- CUDA toolkit and an NVIDIA GPU (only for `poisson_cuda`)
- Python 3.9+ (only for the experiment drivers)

## Build

```bash
bash scripts/build.sh                     # serial + MPI + MPI/OpenMP, then runs the tests
PCG_CUDA_ARCH=86 bash scripts/build.sh cuda   # also MPI/CUDA (86 = compute capability of an A40)
```

`PCG_CUDA_ARCH` must be the compute capability of the GPU you run on
(`nvidia-smi --query-gpu=compute_cap --format=csv,noheader`, without the dot).
Or build manually:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=mpicxx [-DENABLE_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=86]
cmake --build build -j
ctest --test-dir build --output-on-failure
```

Executables are written to `build/bin/`.

On Vanda, compile on a compute node (login nodes are virtual machines):

```bash
qsub -I -l select=1:ncpus=4 -l walltime=00:20:00
cd $PBS_O_WORKDIR
source scripts/vanda/env.sh               # CMake + NVIDIA HPC SDK 26.1 / HPC-X (Open MPI 4.1)
bash scripts/build.sh
```

## Run

All executables accept the same options:

```
--dim 2|3               problem dimension (default 2)
--n N                   interior grid points per side (default 256)
--tol T                 relative residual tolerance (default 1e-8)
--maxit M               maximum CG iterations (default 10000)
--decomp slab|cart      MPI decomposition (default cart)
--halo block|overlap    halo exchange: blocking, or overlapped with interior computation (default block)
--cg std|pipe           standard CG, or single-reduction (Chronopoulos-Gear) CG (default std)
--repeat R              repeat the solve R times and report the fastest (default 1)
--csv FILE              append one result row to FILE
--verbose               print the residual history
```

Examples:

```bash
build/bin/poisson_serial --dim 2 --n 512
mpirun -np 16 build/bin/poisson_mpi --dim 3 --n 256 --decomp cart --halo overlap
OMP_NUM_THREADS=4 mpirun -np 4 --map-by slot:PE=4 build/bin/poisson_omp --dim 3 --n 256
PCG_CUDA_HALO=staged mpirun -np 2 build/bin/poisson_cuda --dim 3 --n 256   # one GPU per rank
```

For hybrid runs, give each rank its own set of cores (Open MPI: `--map-by ppr:R:node:PE=T`, or
`--bind-to none` with `OMP_PLACES=cores OMP_PROC_BIND=close`); the default `--bind-to core` puts
all threads of a rank on one core. For `poisson_cuda`, `PCG_CUDA_HALO=staged|device` selects
whether halo faces are copied to host memory before MPI or passed to MPI as device pointers
(CUDA-aware MPI). The 2D CG needs about 3n iterations, so raise `--maxit` for n > 3300.

Each run prints a summary and, with `--csv`, appends one row:

```
impl,dim,n,ranks,threads,gpus,decomp,halo,cg,iters,t_total,t_stencil,t_halo,t_reduce,rel_res,err_l2
```

Times are in seconds, cover the CG iterations only (not setup, validation or I/O), and are the
maximum over ranks. `t_stencil`, `t_halo` and `t_reduce` are the per-phase maxima (computation,
neighbour communication, global reductions); they can come from different ranks and need not add
up to `t_total`. `rel_res` is the true residual ‖b − Ax‖/‖b‖ recomputed after the solve, and
`err_l2` is the discrete L2 error against the manufactured solution.

## Validation

`ctest --test-dir build --output-on-failure` runs seven test groups:

| Test | What it checks |
| --- | --- |
| `common` | CLI parser, CSV format, manufactured solution |
| `serial` | A is symmetric positive definite; err_l2 falls as O(h²) (observed order 2.00 in 2D and 3D); standard and single-reduction CG give the same iterations and error |
| `mpi_np1`, `mpi_np3`, `mpi_np4` | every `--decomp` × `--halo` × `--cg` combination, 2D and 3D, uneven splits and one-point-thick blocks: same iteration count as serial (±1), same err_l2 (1e-6 relative), and every grid point equal to the serial solution |
| `omp_np1`, `omp_np2` | the same checks for the MPI+OpenMP solver with 2 threads per rank |

With Open MPI on a machine with fewer cores than ranks, configure with
`-DPCG_MPIEXEC_EXTRA="--oversubscribe"`. The CUDA kernels (stencil, dot product, halo-face
packing) are checked against CPU results on a GPU node with:

```bash
nvcc -std=c++17 -arch=sm_86 src/hybrid_cuda/checks/kernel_check.cu -o kernel_check && ./kernel_check
```

## Reproducing the measurements

All measurements in the report were produced on the Vanda cluster by two PBS jobs, submitted from
this directory:

```bash
chmod +x scripts/vanda/pbs_rsh.py                  # used by mpiexec as the remote launcher
qsub -P YOUR_PROJECT scripts/vanda/scaling_cpu.pbs   # 4 exclusive 72-core nodes: serial sweep, strong/weak scaling to 288/256 cores, MPI variants, MPI x OpenMP splits
qsub -P YOUR_PROJECT scripts/vanda/scaling_gpu.pbs   # 2 A40 nodes: 1 and 2 GPUs, staged and device halo transport
```

Each job builds the code, runs the tests, then runs every configuration as one warm-up plus three
independent processes. Every run must have a true residual below 1e-8 and match a serial run on the
same mesh in iteration count and error. Inter-node CPU communication used Open MPI's TCP transport
(`--mca pml ob1 --mca btl self,vader,tcp`, HCOLL/UCC disabled) with each rank pinned to its own
physical cores (`scripts/vanda/pin_rank.py`).

## Use of AI

Generative AI tools (Anthropic Claude and OpenAI Codex) assisted in drafting code, tests, job
scripts and the report; all output was reviewed, tested and validated by the authors.
