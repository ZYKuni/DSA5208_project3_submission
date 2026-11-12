// MPI domain decomposition (owner: A). Reused by the hybrid versions (B).
//
//   slab : 1D split along the slowest axis (z in 3D, y in 2D). Each halo face is contiguous,
//          but the face area does not shrink as ranks grow.
//   cart : MPI_Dims_create + MPI_Cart_create over all active axes (2D blocks in 2D, 3D blocks
//          in 3D). Smaller surface-to-volume ratio, more neighbours, strided x faces.
// The n points of an axis split as evenly as possible: the first n % P ranks get one extra.
#pragma once

#include "grid.hpp"

#include <mpi.h>
#include <string>

namespace pcg {

struct Decomp {
    MPI_Comm comm = MPI_COMM_NULL; // Cartesian communicator (use this one, not WORLD)
    int rank = 0;
    int size = 1;
    int pdims[3] = {1, 1, 1};  // processes per axis (axis 0 = z, 1 = y, 2 = x)
    int coords[3] = {0, 0, 0}; // this rank's position per axis
    int nbr_lo[3];             // neighbour towards lower index per axis, or MPI_PROC_NULL
    int nbr_hi[3];             // neighbour towards higher index per axis, or MPI_PROC_NULL
    std::string kind;          // "slab" or "cart"
    Block block;               // this rank's part of the grid
};

// Collective over `comm`. Aborts with a message if an axis has fewer points than ranks.
Decomp make_decomp(MPI_Comm comm, int dim, long n, const std::string& kind);

// Frees the Cartesian communicator.
void free_decomp(Decomp& d);

// Points of axis split for coordinate c of P: count and first global index.
void split_axis(long n, int P, int c, long& count, long& first);

} // namespace pcg
