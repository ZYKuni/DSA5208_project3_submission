// Validation of the serial solver (owner: A).
//   1. A is symmetric: (A x, y) == (x, A y) for random x, y.
//   2. Second-order convergence: err_l2 falls by ~4x each time h halves (2D and 3D).
//   3. Standard and single-reduction CG agree (iterations +-1, err_l2 to 1e-6 relative).
#undef NDEBUG
#include "cg.hpp"
#include "serial_backend.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <random>

namespace {

int failures = 0;

void check(bool ok, const char* what) {
    std::printf("  [%s] %s\n", ok ? " ok " : "FAIL", what);
    if (!ok)
        ++failures;
}

struct Run {
    int iters;
    double rel_res;
    double err;
};

Run solve(int dim, long n, const char* variant, double tol) {
    pcg::Params p;
    p.dim = dim;
    p.n = n;
    p.cg = variant;
    p.tol = tol;
    pcg::SerialBackend be(dim, n, variant);
    double* b = be.alloc();
    double* x = be.alloc();
    be.rhs(b);
    pcg::CGStats s = pcg::cg_solve(be, b, x, p);
    Run r{s.iters, s.rel_res, be.error_l2(x)};
    be.release(b);
    be.release(x);
    return r;
}

void symmetry(int dim, long n) {
    pcg::SerialBackend be(dim, n, "std");
    const pcg::Block& blk = be.block();
    double *x = be.alloc(), *y = be.alloc(), *ax = be.alloc(), *ay = be.alloc();
    std::mt19937 gen(42);
    std::uniform_real_distribution<double> u(-1.0, 1.0);
    for (long k = 0; k < blk.L[0]; ++k)
        for (long j = 0; j < blk.L[1]; ++j)
            for (long i = 0; i < blk.L[2]; ++i) {
                x[blk.idx(k, j, i)] = u(gen);
                y[blk.idx(k, j, i)] = u(gen);
            }
    be.apply(x, ax);
    be.apply(y, ay);
    const double a = be.dot(ax, y), b = be.dot(x, ay), xax = be.dot(x, ax);
    char msg[128];
    std::snprintf(msg, sizeof msg, "%dD symmetric: |(Ax,y)-(x,Ay)|/|(Ax,y)| = %.1e, (x,Ax) > 0",
                  dim, std::abs(a - b) / std::abs(a));
    check(std::abs(a - b) <= 1e-12 * std::abs(a) && xax > 0, msg);
    be.release(x);
    be.release(y);
    be.release(ax);
    be.release(ay);
}

void convergence(int dim, const long ns[3]) {
    std::printf("%dD convergence (tol 1e-10):\n", dim);
    double prev = 0;
    for (int q = 0; q < 3; ++q) {
        Run r = solve(dim, ns[q], "std", 1e-10);
        std::printf("    n=%4ld  iters=%4d  err_l2=%.4e", ns[q], r.iters, r.err);
        if (q > 0)
            std::printf("  order=%.3f", std::log2(prev / r.err));
        std::printf("\n");
        check(r.rel_res < 1e-10, "converged to tolerance");
        if (q > 0) {
            const double order = std::log2(prev / r.err);
            check(order > 1.9 && order < 2.1, "observed order of accuracy in [1.9, 2.1]");
        }
        prev = r.err;
    }
}

void variants(int dim, long n) {
    Run a = solve(dim, n, "std", 1e-8), b = solve(dim, n, "pipe", 1e-8);
    char msg[160];
    std::snprintf(msg, sizeof msg, "%dD n=%ld std vs pipe: iters %d vs %d, err %.6e vs %.6e", dim,
                  n, a.iters, b.iters, a.err, b.err);
    check(std::abs(a.iters - b.iters) <= 1 && std::abs(a.err - b.err) <= 1e-6 * a.err &&
              b.rel_res < 1e-8,
          msg);
}

} // namespace

int main() {
    symmetry(2, 20);
    symmetry(3, 9);
    const long n2[3] = {15, 31, 63}; // h = 1/16, 1/32, 1/64
    const long n3[3] = {7, 15, 31};
    convergence(2, n2);
    convergence(3, n3);
    variants(2, 100);
    variants(3, 40);
    std::printf("test_serial: %s\n", failures ? "FAILED" : "OK");
    return failures ? 1 : 0;
}
