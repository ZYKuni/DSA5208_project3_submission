#include "mpi_backend.hpp"

#include <cmath>
#include <cstring>

namespace pcg {

MpiBackend::MpiBackend(MPI_Comm comm, const Params& p)
    : dec_(make_decomp(comm, p.dim, p.n, p.decomp)), halo_mode_(p.halo), cg_(p.cg) {
    halo_.reset(new Halo(dec_));
    const Block& b = dec_.block;
    full_ = full_range(b);
    // Shrink only the sides that receive data from a neighbour; physical-boundary ghosts are 0.
    inner_ = full_;
    for (int a = 0; a < 3; ++a) {
        if (dec_.nbr_lo[a] != MPI_PROC_NULL)
            inner_.lo[a] = 1;
        if (dec_.nbr_hi[a] != MPI_PROC_NULL)
            inner_.hi[a] = b.L[a] - 1;
    }
    nshell_ = shell_ranges(b, inner_, shell_);
}

MpiBackend::~MpiBackend() {
    halo_.reset();
    free_decomp(dec_);
}

double* MpiBackend::alloc() {
    const std::size_t m = dec_.block.size();
    double* v = new double[m];
    std::memset(v, 0, m * sizeof(double));
    return v;
}

void MpiBackend::release(double* v) {
    delete[] v;
}

void MpiBackend::rhs(double* b) {
    fill_rhs(dec_.block, b);
}

double MpiBackend::error_l2(const double* x) {
    double loc = local_err_sq(dec_.block, x), glob = 0.0;
    MPI_Allreduce(&loc, &glob, 1, MPI_DOUBLE, MPI_SUM, dec_.comm);
    return std::sqrt(std::pow(dec_.block.h, dec_.block.dim) * glob);
}

void MpiBackend::stencil(const double* in, double* out, const Range& r) {
    apply_laplacian(dec_.block, in, out, r);
}

double MpiBackend::local_dot_hook(const double* x, const double* y) {
    return local_dot(dec_.block, x, y);
}

void MpiBackend::local_dot2_hook(const double* a, const double* b, const double* c, const double* d,
                                 double out[2]) {
    local_dot2(dec_.block, a, b, c, d, out);
}

void MpiBackend::apply(double* in, double* out) {
    if (halo_mode_ == "overlap") {
        timer_.start(Phase::Halo);
        halo_->start(in);
        timer_.stop(Phase::Halo);

        timer_.start(Phase::Stencil);
        stencil(in, out, inner_);
        timer_.stop(Phase::Stencil);

        timer_.start(Phase::Halo);
        halo_->finish();
        timer_.stop(Phase::Halo);

        timer_.start(Phase::Stencil);
        for (int s = 0; s < nshell_; ++s)
            stencil(in, out, shell_[s]);
        timer_.stop(Phase::Stencil);
    } else {
        timer_.start(Phase::Halo);
        halo_->exchange(in);
        timer_.stop(Phase::Halo);

        timer_.start(Phase::Stencil);
        stencil(in, out, full_);
        timer_.stop(Phase::Stencil);
    }
}

double MpiBackend::dot(const double* x, const double* y) {
    double loc = local_dot_hook(x, y), glob = 0.0;
    MPI_Allreduce(&loc, &glob, 1, MPI_DOUBLE, MPI_SUM, dec_.comm);
    return glob;
}

void MpiBackend::dot2(const double* a, const double* b, const double* c, const double* d,
                      double out[2]) {
    double loc[2];
    local_dot2_hook(a, b, c, d, loc);
    MPI_Allreduce(loc, out, 2, MPI_DOUBLE, MPI_SUM, dec_.comm);
}

void MpiBackend::axpy(double* __restrict y, double alpha, const double* __restrict x) {
    const std::size_t m = dec_.block.size();
    for (std::size_t q = 0; q < m; ++q)
        y[q] += alpha * x[q];
}

void MpiBackend::xpay(double* __restrict y, double beta, const double* __restrict x) {
    const std::size_t m = dec_.block.size();
    for (std::size_t q = 0; q < m; ++q)
        y[q] = x[q] + beta * y[q];
}

void MpiBackend::copy(double* dst, const double* src) {
    std::memcpy(dst, src, dec_.block.size() * sizeof(double));
}

void MpiBackend::zero(double* v) {
    std::memset(v, 0, dec_.block.size() * sizeof(double));
}

double MpiBackend::max_over_ranks(double v) {
    double m = 0.0;
    MPI_Allreduce(&v, &m, 1, MPI_DOUBLE, MPI_MAX, dec_.comm);
    return m;
}

Result MpiBackend::describe() const {
    Result r;
    r.impl = "mpi";
    r.dim = dec_.block.dim;
    r.n = dec_.block.n;
    r.ranks = dec_.size;
    r.threads = 1;
    r.gpus = 0;
    r.decomp = dec_.kind;
    r.halo = halo_mode_;
    r.cg = cg_;
    return r;
}

} // namespace pcg
