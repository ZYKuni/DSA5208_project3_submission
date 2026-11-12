#!/bin/bash
# Source this on a Vanda COMPUTE node (login nodes are VMs; compile inside `qsub -I`).
#   qsub -I -l select=1:ncpus=4 -l walltime=00:20:00
#   source scripts/vanda/env.sh
# Owner: C. Modules below were listed on Vanda on 2026-11-08.
module purge
module load CMake/3.26.3-GCCcore-12.3.0
module load "${PCG_MPI_MODULE:-nvhpc-hpcx-cuda12/26.1}"
# Alternative: module load OpenMPI/4.1.4-NVHPC-22.7-CUDA-11.7.0
export OMP_DYNAMIC=FALSE
export OMP_PROC_BIND=close
export OMP_PLACES=cores
