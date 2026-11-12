#include "omp_backend.hpp"

#include <omp.h>

namespace pcg {

OmpBackend::OmpBackend(MPI_Comm comm, const Params& p) : MpiBackend(comm, p) {
    threads_ = omp_get_max_threads();
}

// Rows (k, j) are distributed over threads; the contiguous x loop stays inside one thread so
// the compiler can vectorise it, exactly as in the serial kernel.
void OmpBackend::stencil(const double* __restrict in, double* __restrict out, const Range& r) {
    if (r.empty())
        return;
    const Block& b = dec_.block;
    const double ih2 = 1.0 / (b.h * b.h);
    const long sy = b.sy, sz = b.sz;
    const bool d3 = b.dim == 3;
    const double diag = (d3 ? 6.0 : 4.0) * ih2;
#pragma omp parallel for collapse(2) schedule(static)
    for (long k = r.lo[0]; k < r.hi[0]; ++k) {
        for (long j = r.lo[1]; j < r.hi[1]; ++j) {
            const long base = b.idx(k, j, 0);
            const double* c = in + base;
            double* o = out + base;
            if (d3) {
                for (long i = r.lo[2]; i < r.hi[2]; ++i)
                    o[i] = diag * c[i] - ih2 * (c[i - 1] + c[i + 1] + c[i - sy] + c[i + sy] +
                                                c[i - sz] + c[i + sz]);
            } else {
                for (long i = r.lo[2]; i < r.hi[2]; ++i)
                    o[i] = diag * c[i] - ih2 * (c[i - 1] + c[i + 1] + c[i - sy] + c[i + sy]);
            }
        }
    }
}

double OmpBackend::local_dot_hook(const double* __restrict x, const double* __restrict y) {
    const Block& b = dec_.block;
    double s = 0.0;
#pragma omp parallel for collapse(2) schedule(static) reduction(+ : s)
    for (long k = 0; k < b.L[0]; ++k)
        for (long j = 0; j < b.L[1]; ++j) {
            const long base = b.idx(k, j, 0);
            for (long i = 0; i < b.L[2]; ++i)
                s += x[base + i] * y[base + i];
        }
    return s;
}

void OmpBackend::local_dot2_hook(const double* __restrict a, const double* __restrict bb,
                                 const double* __restrict c, const double* __restrict d,
                                 double out[2]) {
    const Block& b = dec_.block;
    double s0 = 0.0, s1 = 0.0;
#pragma omp parallel for collapse(2) schedule(static) reduction(+ : s0, s1)
    for (long k = 0; k < b.L[0]; ++k)
        for (long j = 0; j < b.L[1]; ++j) {
            const long base = b.idx(k, j, 0);
            for (long i = 0; i < b.L[2]; ++i) {
                s0 += a[base + i] * bb[base + i];
                s1 += c[base + i] * d[base + i];
            }
        }
    out[0] = s0;
    out[1] = s1;
}

void OmpBackend::axpy(double* __restrict y, double alpha, const double* __restrict x) {
    const long m = static_cast<long>(dec_.block.size());
#pragma omp parallel for simd schedule(static)
    for (long q = 0; q < m; ++q)
        y[q] += alpha * x[q];
}

void OmpBackend::xpay(double* __restrict y, double beta, const double* __restrict x) {
    const long m = static_cast<long>(dec_.block.size());
#pragma omp parallel for simd schedule(static)
    for (long q = 0; q < m; ++q)
        y[q] = x[q] + beta * y[q];
}

void OmpBackend::copy(double* __restrict dst, const double* __restrict src) {
    const long m = static_cast<long>(dec_.block.size());
#pragma omp parallel for simd schedule(static)
    for (long q = 0; q < m; ++q)
        dst[q] = src[q];
}

void OmpBackend::zero(double* v) {
    const long m = static_cast<long>(dec_.block.size());
#pragma omp parallel for simd schedule(static)
    for (long q = 0; q < m; ++q)
        v[q] = 0.0;
}

Result OmpBackend::describe() const {
    Result r = MpiBackend::describe();
    r.impl = "omp";
    r.threads = threads_;
    return r;
}

} // namespace pcg
