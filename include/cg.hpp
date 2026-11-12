// Conjugate gradient driver shared by every implementation (owner: A).
//
// The CG algorithm is written once, here, against the abstract Backend below. Each
// implementation (serial, MPI, MPI+OpenMP, MPI+CUDA) only provides a Backend: vector storage,
// the matrix-free operator with its halo exchange, dot products with their reductions, and
// vector updates. The driver never dereferences vector pointers, so a CUDA backend can hand
// out device memory.
//
// Timing contract (see CONTRIBUTING.md):
//   - the driver charges dot()/dot2() to Phase::Reduce and axpy/xpay/copy/zero to Phase::Stencil;
//   - apply() must charge its own time: neighbour communication to Phase::Halo, the stencil
//     to Phase::Stencil (an overlapped implementation splits the two as it sees fit);
//   - a GPU backend should synchronise inside its methods if it wants an exact split.
#pragma once

#include "csv.hpp"
#include "params.hpp"
#include "timer.hpp"

#include <cstddef>
#include <string>

namespace pcg {

class Backend {
  public:
    virtual ~Backend() = default;

    // --- storage -----------------------------------------------------------------------
    virtual double* alloc() = 0; // one vector, ghosts included, zero-filled
    virtual void release(double* v) = 0;

    // --- problem -----------------------------------------------------------------------
    virtual void rhs(double* b) = 0;              // b = f on owned points, 0 elsewhere
    virtual double error_l2(const double* x) = 0; // global discrete L2 error vs exact u

    // --- CG building blocks ------------------------------------------------------------
    // out = A in. May overwrite the ghost layer of `in` (halo exchange).
    virtual void apply(double* in, double* out) = 0;
    // Global dot product (all ranks get the result).
    virtual double dot(const double* x, const double* y) = 0;
    // out[0] = (a, b), out[1] = (c, d), with ONE global reduction.
    virtual void dot2(const double* a, const double* b, const double* c, const double* d,
                      double out[2]) = 0;
    virtual void axpy(double* y, double alpha, const double* x) = 0; // y += alpha x
    virtual void xpay(double* y, double beta, const double* x) = 0;  // y = x + beta y
    virtual void copy(double* dst, const double* src) = 0;
    virtual void zero(double* v) = 0;

    // --- parallel environment (defaults are for a single process) ----------------------
    virtual bool is_root() const {
        return true;
    }
    virtual void barrier() {}
    virtual double max_over_ranks(double v) {
        return v;
    }

    // --- description for the CSV row ---------------------------------------------------
    virtual Result describe() const = 0; // impl, dim, n, ranks, threads, gpus, decomp, halo, cg

    PhaseTimer& timer() {
        return timer_;
    }

  protected:
    PhaseTimer timer_;
};

struct CGStats {
    int iters = 0;      // number of CG updates of x
    double rel_res = 0; // recursive ||r|| / ||b|| when the loop stopped
    bool converged = false;
    double solve_seconds = 0; // max-rank loop time, excluding allocation and initialisation
};

// Solves A x = b starting from x = 0 with standard CG (variant "std", two reductions per
// iteration) or Chronopoulos-Gear single-reduction CG (variant "pipe").
CGStats cg_solve(Backend& be, const double* b, double* x, const Params& p);

// Full run used by every main(): builds b, solves --repeat times (keeping the fastest),
// measures the true residual and the discretisation error, takes the max of the phase times
// over ranks, prints a summary on the root and appends to --csv on the root.
Result run_solver(Backend& be, const Params& p);

} // namespace pcg
