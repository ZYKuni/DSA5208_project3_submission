#pragma once
#include "kernel.hpp"
#include <mpi.h>
#include <array>
#include <memory>

namespace poisson {
enum class Communication { Sendrecv, Overlap };
const char* name(Communication communication);
// Extension point for C: functions execute synchronously and contain no MPI calls.
struct LocalKernels {
    decltype(&jacobi_rows) update = jacobi_rows;
    decltype(&residual_squared_rows) residual = residual_squared_rows;
    decltype(&squared_norm_rows) norm = squared_norm_rows;
};
void exchange_halo(Grid& u, MPI_Comm comm);
std::array<MPI_Request, 4> begin_halo(Grid& u, MPI_Comm comm);
void finish_halo(std::array<MPI_Request, 4>& requests);
SolveResult solve_mpi(const Config& config, Grid& solution, Communication communication,
                      MPI_Comm comm, const LocalKernels& kernels = {});
// Collective; only rank 0 allocates a global grid, only when explicitly requested.
std::unique_ptr<Grid> gather_solution(const Grid& local, MPI_Comm comm);
} // namespace poisson
