#pragma once
#include "kernel.hpp"
namespace poisson {
// Same contract as kernel.hpp. No MPI calls or buffer swaps.
void jacobi_rows_openmp(const Grid&, Grid&, const Grid&, std::size_t, std::size_t);
double residual_squared_rows_openmp(const Grid&, const Grid&, std::size_t, std::size_t);
double squared_norm_rows_openmp(const Grid&, std::size_t, std::size_t);
// Probe a real team, not omp_get_max_threads(). Driver disables dynamic teams.
int openmp_team_size();
}
