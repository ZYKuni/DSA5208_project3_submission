// Model problem shared by all implementations (owner: A).
//   -Laplace(u) = f  on (0,1)^d,  u = 0 on the boundary, d = 2 or 3.
// Manufactured solution: u(x) = prod_k g(x_k) with g(t) = t (1 - t) e^t.
//   g''(t) = -t (t + 3) e^t, so f = -Laplace(u) = sum_k t_k (t_k + 3) e^{t_k} prod_{j != k} g(t_j).
// Why not prod sin(pi x_k)? That function is an exact eigenvector of the discrete Laplacian, so
// CG would converge in ONE iteration and the timing experiments would be meaningless. The
// right-hand side above excites all eigenmodes, so CG needs O(n) iterations as for a generic
// right-hand side, and its fourth derivative is non-zero, so the O(h^2) error is visible.
// Grid: n interior points per side, h = 1/(n+1), x_i = (i+1) h for i = 0..n-1.
// Discrete operator: standard 5-point (2D) / 7-point (3D) stencil scaled by 1/h^2.
// In 2D only x and y are used (z is ignored).
#pragma once

#include <cmath>

namespace pcg {

inline double grid_h(long n) {
    return 1.0 / static_cast<double>(n + 1);
}

inline double mms_g(double t) {
    return t * (1.0 - t) * std::exp(t);
}
inline double mms_minus_g2(double t) {
    return t * (t + 3.0) * std::exp(t);
} // -g''(t)

inline double exact_u(int dim, double x, double y, double z) {
    double u = mms_g(x) * mms_g(y);
    return dim == 3 ? u * mms_g(z) : u;
}

inline double rhs_f(int dim, double x, double y, double z) {
    const double gx = mms_g(x), gy = mms_g(y);
    if (dim == 2)
        return mms_minus_g2(x) * gy + gx * mms_minus_g2(y);
    const double gz = mms_g(z);
    return mms_minus_g2(x) * gy * gz + gx * mms_minus_g2(y) * gz + gx * gy * mms_minus_g2(z);
}

} // namespace pcg
