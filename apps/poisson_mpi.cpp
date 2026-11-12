// Pure MPI matrix-free CG for the 2D/3D Poisson problem (owner: A).
//   mpirun -np 16 build/bin/poisson_mpi --dim 3 --n 256 --decomp cart --halo overlap --cg pipe
#include "cg.hpp"
#include "mpi_backend.hpp"
#include "params.hpp"

#include <mpi.h>

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    pcg::Params p = pcg::parse_args(argc, argv);
    {
        pcg::MpiBackend be(MPI_COMM_WORLD, p);
        pcg::run_solver(be, p);
    } // backend frees its communicator and datatypes before MPI_Finalize
    MPI_Finalize();
    return 0;
}
