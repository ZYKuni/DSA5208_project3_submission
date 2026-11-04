#include "kernel.hpp"
#include <stdexcept>

namespace poisson {
namespace {
void check_range(const Grid& grid, std::size_t begin, std::size_t end) {
    if (begin < 1 || begin > end || end > grid.rows + 1)
        throw std::invalid_argument("row range must lie within [1, rows+1)");
}
void check_pair(const Grid& a, const Grid& b) {
    if (!same_layout(a, b)) throw std::invalid_argument("incompatible grid layouts");
}
}
void jacobi_rows(const Grid& old, Grid& next, const Grid& rhs,
                 std::size_t begin, std::size_t end) {
    check_range(old, begin, end);
    check_pair(old, next);
    check_pair(old, rhs);
    if (&old == &next || &rhs == &next)
        throw std::invalid_argument("Jacobi output must not alias its inputs");
    const double h = 1.0 / (static_cast<double>(old.n) + 1.0);
    const double h2 = h * h;
    for (std::size_t i = begin; i < end; ++i)
        for (std::size_t j = 1; j <= old.n; ++j)
            next(i, j) = 0.25 * (old(i-1, j) + old(i+1, j)
                               + old(i, j-1) + old(i, j+1) + h2 * rhs(i, j));
}
double residual_squared_rows(const Grid& u, const Grid& rhs,
                             std::size_t begin, std::size_t end) {
    check_range(u, begin, end);
    check_pair(u, rhs);
    const double inv_h = static_cast<double>(u.n) + 1.0;
    const double inv_h2 = inv_h * inv_h;
    double sum = 0;
    for (std::size_t i = begin; i < end; ++i) {
        for (std::size_t j = 1; j <= u.n; ++j) {
            const double au = (4.0 * u(i, j) - u(i-1, j) - u(i+1, j)
                               - u(i, j-1) - u(i, j+1)) * inv_h2;
            const double r = rhs(i, j) - au;
            sum += r * r;
        }
    }
    return sum;
}
double squared_norm_rows(const Grid& grid, std::size_t begin, std::size_t end) {
    check_range(grid, begin, end);
    double sum = 0;
    for (std::size_t i = begin; i < end; ++i)
        for (std::size_t j = 1; j <= grid.n; ++j) sum += grid(i, j) * grid(i, j);
    return sum;
}
} // namespace poisson
