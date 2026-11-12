// MPI + OpenMP matrix-free CG for the 2D/3D Poisson problem (owner: B).
//   OMP_NUM_THREADS=18 mpirun -np 4 build/bin/poisson_omp --dim 3 --n 256 --halo overlap
// Accepts every option of poisson_mpi (--decomp, --halo, --cg).
#include "cg.hpp"
#include "omp_backend.hpp"
#include "params.hpp"

#include <cstdio>
#include <mpi.h>

int main(int argc, char** argv) {
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);
    pcg::Params p = pcg::parse_args(argc, argv);
    if (provided < MPI_THREAD_FUNNELED) {
        std::fprintf(stderr, "error: MPI library does not provide MPI_THREAD_FUNNELED\n");
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    {
        pcg::OmpBackend be(MPI_COMM_WORLD, p);
        pcg::run_solver(be, p);
    }
    MPI_Finalize();
    return 0;
}
