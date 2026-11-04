#pragma once
#include "grid.hpp"

namespace poisson {
// Inclusive-exclusive local row range [row_begin, row_end).
// These functions never communicate, swap buffers or change boundary cells.
// Caller must make old/current halos valid before accessing dependent rows.
void jacobi_rows(const Grid& old, Grid& next, const Grid& rhs,
                 std::size_t row_begin, std::size_t row_end);
double residual_squared_rows(const Grid& current, const Grid& rhs,
                             std::size_t row_begin, std::size_t row_end);
double squared_norm_rows(const Grid& grid, std::size_t row_begin, std::size_t row_end);
} // namespace poisson
