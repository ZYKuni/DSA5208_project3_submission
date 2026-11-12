// Local grid block and the matrix-free kernels shared by every implementation (owner: A).
//
// A Block describes the part of the global grid one process owns, plus one ghost (halo) layer.
// The serial solver uses a single Block covering the whole domain; the MPI solver gives each
// rank one Block. Hybrid versions (B) reuse the same layout and only replace the loops.
//
// Axes: 0 = z (slowest), 1 = y, 2 = x (fastest, contiguous in memory).
// In 2D, axis 0 is inactive: L[0] = 1, G[0] = 0, so a 2D block is one z-plane with no z ghosts.
// Owned point (k, j, i) in local coordinates (0 <= k < L[0], ...) is stored at idx(k, j, i);
// ghosts are at local coordinate -1 and L[a] along each active axis. Ghosts on the physical
// boundary hold the Dirichlet value 0 and are never written.
#pragma once

#include <cstddef>

namespace pcg {

struct Block {
    int dim = 2;  // 2 or 3
    long n = 0;   // global interior points per side
    double h = 0; // grid spacing 1/(n+1)
    long L[3];    // owned points per axis
    long off[3];  // global index of the first owned point per axis
    int G[3];     // ghost width per axis (1 on active axes, 0 on the inactive 2D z axis)
    long E[3];    // extended extents L + 2G
    long sy = 0;  // stride of axis 1 (= E[2])
    long sz = 0;  // stride of axis 0 (= E[1] * E[2])

    std::size_t size() const {
        return static_cast<std::size_t>(E[0] * E[1] * E[2]);
    }
    long owned() const {
        return L[0] * L[1] * L[2];
    }
    long idx(long k, long j, long i) const {
        return (k + G[0]) * sz + (j + G[1]) * sy + (i + G[2]);
    }
};

// Sub-box of owned points, half-open [lo, hi) in local coordinates.
struct Range {
    long lo[3];
    long hi[3];
    bool empty() const {
        return lo[0] >= hi[0] || lo[1] >= hi[1] || lo[2] >= hi[2];
    }
};

// Block with the given owned extents and offsets (axis 0 ignored in 2D).
Block make_block(int dim, long n, const long L[3], const long off[3]);

// Block covering the whole domain (serial solver).
Block make_global_block(int dim, long n);

// All owned points.
Range full_range(const Block& b);

// Owned points not adjacent to any ghost on the given axes (for overlapping communication).
// axis_mask bit a set = shrink along axis a. Returns an empty range if nothing is left.
Range inner_range(const Block& b, unsigned axis_mask);

// The owned points in full_range(b) minus `inner`, as at most 6 disjoint boxes.
// Returns the number of boxes written to out.
int shell_ranges(const Block& b, const Range& inner, Range out[6]);

// out = A in on the points of r, where A = -Laplace_h (5-point / 7-point stencil / h^2).
// Reads the ghosts of `in`; writes only owned points of `out`.
void apply_laplacian(const Block& b, const double* in, double* out, const Range& r);

// Sum over owned points of a*b (ghosts excluded).
double local_dot(const Block& b, const double* x, const double* y);

// out[0] = sum a*b, out[1] = sum c*d over owned points, in one sweep when possible.
void local_dot2(const Block& b, const double* a, const double* bb, const double* c, const double* d,
                double out[2]);

// b = f at owned points, 0 at ghosts.
void fill_rhs(const Block& b, double* rhs);

// Sum over owned points of (x - u_exact)^2.
double local_err_sq(const Block& b, const double* x);

} // namespace pcg
