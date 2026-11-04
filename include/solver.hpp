#pragma once
#include "kernel.hpp"

namespace poisson {
// V0 only: operates on the complete grid (rows=n, offset=0).
// Resets solution to the agreed zero initial state. No MPI dependency.
SolveResult solve_serial(const Config& config, Grid& solution);
} // namespace poisson
