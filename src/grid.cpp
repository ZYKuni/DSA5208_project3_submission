#include "grid.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace poisson {
Grid::Grid(std::size_t global_n, std::size_t local_rows, std::size_t offset)
    : n(global_n), rows(local_rows), row_offset(offset), stride(0) {
    if (n == 0 || rows == 0 || rows > n || offset > n - rows)
        throw std::invalid_argument("invalid grid/slab dimensions");
    const auto max = std::numeric_limits<std::size_t>::max();
    if (n > max - 2 || rows > max - 2)
        throw std::length_error("grid dimensions overflow");
    stride = n + 2;
    if (rows + 2 > values.max_size() / stride)
        throw std::length_error("grid storage overflow");
    values.assign((rows + 2) * stride, 0.0);
}
bool same_layout(const Grid& a, const Grid& b) {
    return a.n == b.n && a.rows == b.rows && a.row_offset == b.row_offset;
}
double exact_value(std::size_t i, std::size_t j, std::size_t n, Problem problem) {
    if (problem == Problem::Zero || i == 0 || j == 0 || i == n + 1 || j == n + 1)
        return 0.0;
    const double pi = std::acos(-1.0);
    const double h = 1.0 / (static_cast<double>(n) + 1.0);
    if (problem == Problem::DiscreteMixed) {
        const double x = pi * static_cast<double>(j) * h;
        const double y = pi * static_cast<double>(i) * h;
        return std::sin(x) * std::sin(2.0 * y)
             + 0.35 * std::sin(2.0 * x) * std::sin(3.0 * y);
    }
    return std::sin(pi * static_cast<double>(i) * h)
         * std::sin(pi * static_cast<double>(j) * h);
}
void initialize_rhs(Grid& rhs, Problem problem) {
    if (problem == Problem::DiscreteMixed && rhs.n < 3)
        throw std::invalid_argument("discrete-mixed requires n >= 3");
    std::fill(rhs.values.begin(), rhs.values.end(), 0.0);
    const double pi = std::acos(-1.0);
    const double inv_h = static_cast<double>(rhs.n) + 1.0;
    // Analytic discrete eigenvalue, independent of residual stencil code.
    const double s = std::sin(pi / (2.0 * inv_h));
    const double lambda = problem == Problem::DiscreteSine
                        ? 8.0 * inv_h * inv_h * s * s : 2.0 * pi * pi;
    const auto eigenvalue = [pi, inv_h](double px, double py) {
        const double sx = std::sin(px * pi / (2.0 * inv_h));
        const double sy = std::sin(py * pi / (2.0 * inv_h));
        return 4.0 * inv_h * inv_h * (sx*sx + sy*sy);
    };
    const double lambda12 = eigenvalue(1.0, 2.0);
    const double lambda23 = eigenvalue(2.0, 3.0);
    for (std::size_t i = 1; i <= rhs.rows; ++i) {
        for (std::size_t j = 1; j <= rhs.n; ++j) {
            if (problem == Problem::DiscreteMixed) {
                const double x = pi * static_cast<double>(j) / inv_h;
                const double y = pi * static_cast<double>(rhs.row_offset + i) / inv_h;
                rhs(i, j) = lambda12 * std::sin(x) * std::sin(2.0*y)
                          + 0.35 * lambda23 * std::sin(2.0*x) * std::sin(3.0*y);
            } else {
                rhs(i, j) = lambda * exact_value(rhs.row_offset + i, j, rhs.n, problem);
            }
        }
    }
}
} // namespace poisson
