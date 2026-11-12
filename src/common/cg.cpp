#include "cg.hpp"

#include <cmath>
#include <cstdio>

namespace pcg {

namespace {

// Helpers that charge each call to its phase.
struct Timed {
    Backend& be;
    PhaseTimer& t;
    explicit Timed(Backend& b) : be(b), t(b.timer()) {}

    double dot(const double* x, const double* y) {
        t.start(Phase::Reduce);
        double v = be.dot(x, y);
        t.stop(Phase::Reduce);
        return v;
    }
    void dot2(const double* a, const double* b, const double* c, const double* d, double o[2]) {
        t.start(Phase::Reduce);
        be.dot2(a, b, c, d, o);
        t.stop(Phase::Reduce);
    }
    void axpy(double* y, double a, const double* x) {
        t.start(Phase::Stencil);
        be.axpy(y, a, x);
        t.stop(Phase::Stencil);
    }
    void xpay(double* y, double b, const double* x) {
        t.start(Phase::Stencil);
        be.xpay(y, b, x);
        t.stop(Phase::Stencil);
    }
    void copy(double* d, const double* s) {
        t.start(Phase::Stencil);
        be.copy(d, s);
        t.stop(Phase::Stencil);
    }
    void zero(double* v) {
        t.start(Phase::Stencil);
        be.zero(v);
        t.stop(Phase::Stencil);
    }
};

void report(Backend& be, const Params& p, int it, double rel) {
    if (p.verbose && be.is_root() && it % 100 == 0) {
        std::printf("  iter %6d  rel_res %.3e\n", it, rel);
    }
}

// Standard (Hestenes-Stiefel) CG: reductions (p, Ap) and (r, r) each iteration.
CGStats cg_standard(Backend& be, const double* b, double* x, const Params& p) {
    Timed T(be);
    double* r = be.alloc();
    double* d = be.alloc(); // search direction
    double* q = be.alloc(); // A d

    T.zero(x);
    T.copy(r, b); // r = b - A*0
    T.copy(d, r);
    double rr = T.dot(r, r);
    const double bb = rr;
    const double bnorm = std::sqrt(bb);

    CGStats s;
    s.rel_res = bnorm > 0 ? 1.0 : 0.0;
    if (bnorm == 0.0) {
        s.converged = true;
    }
    be.timer().reset();
    be.barrier();
    const double start = PhaseTimer::now();
    for (int it = 0; !s.converged && it < p.maxit; ++it) {
        be.apply(d, q);
        const double alpha = rr / T.dot(d, q);
        T.axpy(x, alpha, d);
        T.axpy(r, -alpha, q);
        const double rr_new = T.dot(r, r);
        s.iters = it + 1;
        s.rel_res = std::sqrt(rr_new) / bnorm;
        report(be, p, s.iters, s.rel_res);
        if (s.rel_res < p.tol) {
            s.converged = true;
            break;
        }
        T.xpay(d, rr_new / rr, r); // d = r + beta d
        rr = rr_new;
    }
    be.barrier();
    s.solve_seconds = be.max_over_ranks(PhaseTimer::now() - start);

    be.release(r);
    be.release(d);
    be.release(q);
    return s;
}

// Chronopoulos-Gear CG: (r, r) and (A r, r) fused into one reduction per iteration, at the
// cost of one extra vector recurrence s = A d. Same iterates as standard CG in exact
// arithmetic.
CGStats cg_single_reduction(Backend& be, const double* b, double* x, const Params& p) {
    Timed T(be);
    double* r = be.alloc();
    double* w = be.alloc(); // A r
    double* d = be.alloc(); // search direction
    double* s = be.alloc(); // A d (by recurrence)

    T.zero(x);
    T.zero(d);
    T.zero(s);
    T.copy(r, b);
    be.apply(r, w);

    CGStats st;
    double bnorm = 0.0; // ||b|| = ||r_0||, taken from the first reduction
    double start = 0.0;
    double gamma_old = 0.0, alpha_old = 0.0;
    for (int it = 0;; ++it) {
        double g[2];
        T.dot2(r, r, w, r, g); // gamma = (r, r), delta = (A r, r)
        const double gamma = g[0], delta = g[1];
        if (it == 0) {
            bnorm = std::sqrt(gamma);
            be.timer().reset();
            be.barrier();
            start = PhaseTimer::now();
        }
        st.iters = it;
        st.rel_res = bnorm > 0 ? std::sqrt(gamma) / bnorm : 0.0;
        if (it > 0)
            report(be, p, it, st.rel_res);
        if (st.rel_res < p.tol || bnorm == 0.0) {
            st.converged = true;
            break;
        }
        if (it >= p.maxit)
            break;
        double alpha, beta;
        if (it == 0) {
            beta = 0.0;
            alpha = gamma / delta;
        } else {
            beta = gamma / gamma_old;
            alpha = gamma / (delta - beta * gamma / alpha_old);
        }
        T.xpay(d, beta, r); // d = r + beta d
        T.xpay(s, beta, w); // s = w + beta s
        T.axpy(x, alpha, d);
        T.axpy(r, -alpha, s);
        be.apply(r, w);
        gamma_old = gamma;
        alpha_old = alpha;
    }
    be.barrier();
    st.solve_seconds = be.max_over_ranks(PhaseTimer::now() - start);

    be.release(r);
    be.release(w);
    be.release(d);
    be.release(s);
    return st;
}

} // namespace

CGStats cg_solve(Backend& be, const double* b, double* x, const Params& p) {
    return p.cg == "pipe" ? cg_single_reduction(be, b, x, p) : cg_standard(be, b, x, p);
}

Result run_solver(Backend& be, const Params& p) {
    double* b = be.alloc();
    double* x = be.alloc();
    be.rhs(b);

    Result best = be.describe();
    CGStats stats;
    best.t_total = -1.0;
    for (int rep = 0; rep < p.repeat; ++rep) {
        be.timer().reset();
        stats = cg_solve(be, b, x, p);
        const double t_total = stats.solve_seconds;
        const double ts = be.max_over_ranks(be.timer().get(Phase::Stencil));
        const double th = be.max_over_ranks(be.timer().get(Phase::Halo));
        const double tr = be.max_over_ranks(be.timer().get(Phase::Reduce));
        if (best.t_total < 0 || t_total < best.t_total) {
            best.t_total = t_total;
            best.t_stencil = ts;
            best.t_halo = th;
            best.t_reduce = tr;
        }
    }

    // True residual ||b - A x|| / ||b|| (not timed).
    double* ax = be.alloc();
    be.apply(x, ax);
    be.xpay(ax, -1.0, b); // ax = b - ax
    const double bn = std::sqrt(be.dot(b, b));
    best.rel_res = bn > 0 ? std::sqrt(be.dot(ax, ax)) / bn : 0.0;
    best.iters = stats.iters;
    best.err_l2 = be.error_l2(x);
    be.release(ax);
    be.release(b);
    be.release(x);

    if (be.is_root()) {
        if (!stats.converged) {
            std::fprintf(stderr, "warning: CG did not converge in %d iterations (rel_res %.3e)\n",
                         p.maxit, stats.rel_res);
        }
        std::printf("%s dim=%d n=%ld ranks=%d threads=%d gpus=%d decomp=%s halo=%s cg=%s\n"
                    "  iters=%d  rel_res=%.3e  err_l2=%.3e\n"
                    "  t_total=%.4fs  stencil=%.4fs  halo=%.4fs  reduce=%.4fs\n",
                    best.impl.c_str(), best.dim, best.n, best.ranks, best.threads, best.gpus,
                    best.decomp.c_str(), best.halo.c_str(), best.cg.c_str(), best.iters,
                    best.rel_res, best.err_l2, best.t_total, best.t_stencil, best.t_halo,
                    best.t_reduce);
        if (!p.csv.empty())
            csv_append(p.csv, best);
    }
    return best;
}

} // namespace pcg
