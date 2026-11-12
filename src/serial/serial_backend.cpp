#include "serial_backend.hpp"

#include <cmath>
#include <cstring>

namespace pcg {

SerialBackend::SerialBackend(int dim, long n, const std::string& cg_variant)
    : blk_(make_global_block(dim, n)), cg_(cg_variant) {}

double* SerialBackend::alloc() {
    double* v = new double[blk_.size()];
    std::memset(v, 0, blk_.size() * sizeof(double));
    return v;
}

void SerialBackend::release(double* v) {
    delete[] v;
}

void SerialBackend::rhs(double* b) {
    fill_rhs(blk_, b);
}

double SerialBackend::error_l2(const double* x) {
    return std::sqrt(std::pow(blk_.h, blk_.dim) * local_err_sq(blk_, x));
}

void SerialBackend::apply(double* in, double* out) {
    // Boundary ghosts are always 0 (Dirichlet), so no halo work is needed.
    timer_.start(Phase::Stencil);
    apply_laplacian(blk_, in, out, full_range(blk_));
    timer_.stop(Phase::Stencil);
}

double SerialBackend::dot(const double* x, const double* y) {
    return local_dot(blk_, x, y);
}

void SerialBackend::dot2(const double* a, const double* b, const double* c, const double* d,
                         double out[2]) {
    local_dot2(blk_, a, b, c, d, out);
}

// Vector updates sweep the whole array, ghosts included: ghosts of every vector stay 0 on the
// physical boundary, and a flat loop vectorises better than a nested one.
void SerialBackend::axpy(double* __restrict y, double alpha, const double* __restrict x) {
    const std::size_t m = blk_.size();
    for (std::size_t q = 0; q < m; ++q)
        y[q] += alpha * x[q];
}

void SerialBackend::xpay(double* __restrict y, double beta, const double* __restrict x) {
    const std::size_t m = blk_.size();
    for (std::size_t q = 0; q < m; ++q)
        y[q] = x[q] + beta * y[q];
}

void SerialBackend::copy(double* dst, const double* src) {
    std::memcpy(dst, src, blk_.size() * sizeof(double));
}

void SerialBackend::zero(double* v) {
    std::memset(v, 0, blk_.size() * sizeof(double));
}

Result SerialBackend::describe() const {
    Result r;
    r.impl = "serial";
    r.dim = blk_.dim;
    r.n = blk_.n;
    r.ranks = 1;
    r.threads = 1;
    r.gpus = 0;
    r.decomp = "none";
    r.halo = "none";
    r.cg = cg_;
    return r;
}

} // namespace pcg
