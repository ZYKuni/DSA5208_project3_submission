// Validation of the MPI solver against the serial reference (owner: A).
// For every decomp x halo x cg combination, in 2D and 3D, including grids that do not divide
// evenly and blocks one point thick, checks:
//   - iteration count equal to serial (+-1),
//   - err_l2 equal to serial to 1e-6 relative,
//   - every owned point equal to the serial solution at the same global index (max-norm).
// Run with: mpirun -np P build/bin/test_mpi
// The same file built with -DPCG_TEST_OMP becomes test_omp and checks the MPI+OpenMP backend.
#include "cg.hpp"
#include "mpi_backend.hpp"
#include "serial_backend.hpp"
#ifdef PCG_TEST_OMP
#include "omp_backend.hpp"
using ParallelBackend = pcg::OmpBackend;
static const char* const kName = "test_omp";
#else
using ParallelBackend = pcg::MpiBackend;
static const char* const kName = "test_mpi";
#endif

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <mpi.h>

namespace {

int failures = 0;

void one_case(int dim, long n, const char* decomp, const char* halo, const char* cg, int rank) {
    pcg::Params p;
    p.dim = dim;
    p.n = n;
    p.decomp = decomp;
    p.halo = halo;
    p.cg = cg;
    p.tol = 1e-10;

    // Serial reference, computed redundantly on every rank (small grids only).
    pcg::SerialBackend sb(dim, n, "std");
    double* bs = sb.alloc();
    double* xs = sb.alloc();
    sb.rhs(bs);
    pcg::Params ps = p;
    ps.cg = "std";
    pcg::CGStats ss = pcg::cg_solve(sb, bs, xs, ps);
    const double es = sb.error_l2(xs);

    ParallelBackend mb(MPI_COMM_WORLD, p);
    double* bm = mb.alloc();
    double* xm = mb.alloc();
    mb.rhs(bm);
    pcg::CGStats sm = pcg::cg_solve(mb, bm, xm, p);
    const double em = mb.error_l2(xm);

    // Point-by-point comparison on this rank's block.
    const pcg::Block& lb = mb.block();
    const pcg::Block& gb = sb.block();
    double loc_diff = 0.0, loc_max = 0.0;
    for (long k = 0; k < lb.L[0]; ++k)
        for (long j = 0; j < lb.L[1]; ++j)
            for (long i = 0; i < lb.L[2]; ++i) {
                const double vm = xm[lb.idx(k, j, i)];
                const double vs = xs[gb.idx(lb.off[0] + k, lb.off[1] + j, lb.off[2] + i)];
                loc_diff = std::max(loc_diff, std::abs(vm - vs));
                loc_max = std::max(loc_max, std::abs(vs));
            }
    double diff = 0.0, vmax = 0.0;
    MPI_Allreduce(&loc_diff, &diff, 1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD);
    MPI_Allreduce(&loc_max, &vmax, 1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD);

    const bool ok = sm.converged && std::abs(sm.iters - ss.iters) <= 1 &&
                    std::abs(em - es) <= 1e-6 * es && diff <= 1e-8 * vmax;
    if (!ok)
        ++failures;
    if (rank == 0) {
        const pcg::Decomp& d = mb.decomp();
        std::printf("  [%s] %dD n=%-3ld %-4s %-7s %-4s procs=%dx%dx%d  iters %4d/%4d  "
                    "err %.6e/%.6e  max|x-x_serial|/max|x| %.1e\n",
                    ok ? " ok " : "FAIL", dim, n, decomp, halo, cg, d.pdims[0], d.pdims[1],
                    d.pdims[2], sm.iters, ss.iters, em, es, diff / vmax);
    }
    mb.release(bm);
    mb.release(xm);
    sb.release(bs);
    sb.release(xs);
}

} // namespace

int main(int argc, char** argv) {
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);
    int rank = 0, size = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    if (rank == 0)
        std::printf("test_mpi on %d ranks\n", size);

    struct Grid {
        int dim;
        long n;
    };
    // n = 37, 13: uneven splits; n = size: slabs one point thick.
    const Grid grids[] = {{2, 37}, {3, 13}, {2, size}, {3, size < 2 ? 2 : size}};
    for (const Grid& g : grids)
        for (const char* decomp : {"slab", "cart"})
            for (const char* halo : {"block", "overlap"})
                for (const char* cg : {"std", "pipe"})
                    one_case(g.dim, g.n, decomp, halo, cg, rank);

    int total = 0;
    MPI_Allreduce(&failures, &total, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
    if (rank == 0)
        std::printf("test_mpi: %s\n", total ? "FAILED" : "OK");
    MPI_Finalize();
    return total ? 1 : 0;
}
