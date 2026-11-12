// Pure MPI matrix-free CG backend (owner: A).
//
// Run-time variants (see Params):
//   --decomp slab|cart     domain decomposition (decomp.hpp)
//   --halo   block|overlap MPI_Sendrecv before the stencil, or Isend/Irecv overlapped with the
//                          interior stencil and the boundary shell computed after Waitall
//   --cg     std|pipe      two MPI_Allreduce per iteration, or one (cg.hpp)
//
// Extending it (B): the compute kernels are virtual. MPI+OpenMP can derive from MpiBackend and
// override stencil(), local_dot(), local_dot2(), axpy(), xpay(), copy(), zero() with threaded
// loops, keeping the decomposition, halo exchange, reductions and timing as they are.
#pragma once

#include "cg.hpp"
#include "decomp.hpp"
#include "grid.hpp"
#include "halo.hpp"

#include <memory>
#include <mpi.h>
#include <string>

namespace pcg {

class MpiBackend : public Backend {
  public:
    MpiBackend(MPI_Comm comm, const Params& p);
    ~MpiBackend() override;

    double* alloc() override;
    void release(double* v) override;
    void rhs(double* b) override;
    double error_l2(const double* x) override;
    void apply(double* in, double* out) override;
    double dot(const double* x, const double* y) override;
    void dot2(const double* a, const double* b, const double* c, const double* d,
              double out[2]) override;
    void axpy(double* y, double alpha, const double* x) override;
    void xpay(double* y, double beta, const double* x) override;
    void copy(double* dst, const double* src) override;
    void zero(double* v) override;

    bool is_root() const override {
        return dec_.rank == 0;
    }
    void barrier() override {
        MPI_Barrier(dec_.comm);
    }
    double max_over_ranks(double v) override;
    Result describe() const override;

    const Decomp& decomp() const {
        return dec_;
    }
    const Block& block() const {
        return dec_.block;
    }

  protected:
    // Compute hooks for derived (hybrid) backends.
    virtual void stencil(const double* in, double* out, const Range& r);
    virtual double local_dot_hook(const double* x, const double* y);
    virtual void local_dot2_hook(const double* a, const double* b, const double* c, const double* d,
                                 double out[2]);

    Decomp dec_;
    std::unique_ptr<Halo> halo_;
    std::string halo_mode_;
    std::string cg_;
    Range full_;     // all owned points
    Range inner_;    // owned points whose stencil needs no received ghost
    Range shell_[6]; // full_ minus inner_
    int nshell_ = 0;
};

} // namespace pcg
