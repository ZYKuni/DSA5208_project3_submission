#include "grid.hpp"

#include "problem.hpp"

namespace pcg {

Block make_block(int dim, long n, const long L[3], const long off[3]) {
    Block b;
    b.dim = dim;
    b.n = n;
    b.h = grid_h(n);
    for (int a = 0; a < 3; ++a) {
        const bool active = (dim == 3) || a > 0;
        b.L[a] = active ? L[a] : 1;
        b.off[a] = active ? off[a] : 0;
        b.G[a] = active ? 1 : 0;
        b.E[a] = b.L[a] + 2 * b.G[a];
    }
    b.sy = b.E[2];
    b.sz = b.E[1] * b.E[2];
    return b;
}

Block make_global_block(int dim, long n) {
    const long L[3] = {n, n, n};
    const long off[3] = {0, 0, 0};
    return make_block(dim, n, L, off);
}

Range full_range(const Block& b) {
    Range r;
    for (int a = 0; a < 3; ++a) {
        r.lo[a] = 0;
        r.hi[a] = b.L[a];
    }
    return r;
}

Range inner_range(const Block& b, unsigned axis_mask) {
    Range r = full_range(b);
    for (int a = 0; a < 3; ++a) {
        if (b.G[a] == 0 || !(axis_mask & (1u << a)))
            continue;
        r.lo[a] = 1;
        r.hi[a] = b.L[a] - 1;
    }
    return r;
}

int shell_ranges(const Block& b, const Range& inner, Range out[6]) {
    Range cur = full_range(b);
    if (inner.empty()) {
        out[0] = cur;
        return cur.empty() ? 0 : 1;
    }
    int m = 0;
    for (int a = 0; a < 3; ++a) {
        if (inner.lo[a] > cur.lo[a]) {
            Range s = cur;
            s.hi[a] = inner.lo[a];
            out[m++] = s;
            cur.lo[a] = inner.lo[a];
        }
        if (inner.hi[a] < cur.hi[a]) {
            Range s = cur;
            s.lo[a] = inner.hi[a];
            out[m++] = s;
            cur.hi[a] = inner.hi[a];
        }
    }
    return m;
}

void apply_laplacian(const Block& b, const double* __restrict in, double* __restrict out,
                     const Range& r) {
    if (r.empty())
        return;
    const double ih2 = 1.0 / (b.h * b.h);
    const long sy = b.sy, sz = b.sz;
    if (b.dim == 2) {
        const double diag = 4.0 * ih2;
        for (long j = r.lo[1]; j < r.hi[1]; ++j) {
            const long base = b.idx(0, j, 0);
            const double* c = in + base;
            double* o = out + base;
            for (long i = r.lo[2]; i < r.hi[2]; ++i) {
                o[i] = diag * c[i] - ih2 * (c[i - 1] + c[i + 1] + c[i - sy] + c[i + sy]);
            }
        }
    } else {
        const double diag = 6.0 * ih2;
        for (long k = r.lo[0]; k < r.hi[0]; ++k) {
            for (long j = r.lo[1]; j < r.hi[1]; ++j) {
                const long base = b.idx(k, j, 0);
                const double* c = in + base;
                double* o = out + base;
                for (long i = r.lo[2]; i < r.hi[2]; ++i) {
                    o[i] = diag * c[i] - ih2 * (c[i - 1] + c[i + 1] + c[i - sy] + c[i + sy] +
                                                c[i - sz] + c[i + sz]);
                }
            }
        }
    }
}

double local_dot(const Block& b, const double* __restrict x, const double* __restrict y) {
    double s = 0.0;
    for (long k = 0; k < b.L[0]; ++k) {
        for (long j = 0; j < b.L[1]; ++j) {
            const long base = b.idx(k, j, 0);
            const double* xr = x + base;
            const double* yr = y + base;
            for (long i = 0; i < b.L[2]; ++i)
                s += xr[i] * yr[i];
        }
    }
    return s;
}

void local_dot2(const Block& b, const double* __restrict a, const double* __restrict bb,
                const double* __restrict c, const double* __restrict d, double out[2]) {
    double s0 = 0.0, s1 = 0.0;
    for (long k = 0; k < b.L[0]; ++k) {
        for (long j = 0; j < b.L[1]; ++j) {
            const long base = b.idx(k, j, 0);
            for (long i = 0; i < b.L[2]; ++i) {
                s0 += a[base + i] * bb[base + i];
                s1 += c[base + i] * d[base + i];
            }
        }
    }
    out[0] = s0;
    out[1] = s1;
}

void fill_rhs(const Block& b, double* rhs) {
    for (std::size_t q = 0; q < b.size(); ++q)
        rhs[q] = 0.0;
    const double h = b.h;
    for (long k = 0; k < b.L[0]; ++k) {
        const double z = (b.off[0] + k + 1) * h;
        for (long j = 0; j < b.L[1]; ++j) {
            const double y = (b.off[1] + j + 1) * h;
            for (long i = 0; i < b.L[2]; ++i) {
                const double x = (b.off[2] + i + 1) * h;
                rhs[b.idx(k, j, i)] = rhs_f(b.dim, x, y, z);
            }
        }
    }
}

double local_err_sq(const Block& b, const double* u) {
    const double h = b.h;
    double s = 0.0;
    for (long k = 0; k < b.L[0]; ++k) {
        const double z = (b.off[0] + k + 1) * h;
        for (long j = 0; j < b.L[1]; ++j) {
            const double y = (b.off[1] + j + 1) * h;
            for (long i = 0; i < b.L[2]; ++i) {
                const double x = (b.off[2] + i + 1) * h;
                const double e = u[b.idx(k, j, i)] - exact_u(b.dim, x, y, z);
                s += e * e;
            }
        }
    }
    return s;
}

} // namespace pcg
