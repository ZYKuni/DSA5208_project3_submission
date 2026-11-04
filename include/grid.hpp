#pragma once
#include "config.hpp"
#include <vector>

namespace poisson {
// Owned rows: [1, rows]. Ghost/physical rows: 0 and rows+1.
// Owned columns: [1, n]. Physical columns: 0 and n+1.
// Local row i maps to global interior index row_offset+i.
struct Grid {
    std::size_t n;
    std::size_t rows;
    std::size_t row_offset; // Number of global interior rows before this slab.
    std::size_t stride;
    std::vector<double> values;
    Grid(std::size_t global_n, std::size_t local_rows, std::size_t offset = 0);
    double& operator()(std::size_t i, std::size_t j) { return values[i * stride + j]; }
    double operator()(std::size_t i, std::size_t j) const { return values[i * stride + j]; }
};
bool same_layout(const Grid& a, const Grid& b);
double exact_value(std::size_t global_i, std::size_t j, std::size_t n, Problem problem);
void initialize_rhs(Grid& rhs, Problem problem);
} // namespace poisson
