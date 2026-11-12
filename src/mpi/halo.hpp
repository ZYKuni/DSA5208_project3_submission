// Halo (ghost layer) exchange for one Block (owner: A). Reused by the hybrid versions (B).
//
// Faces are described with MPI_Type_create_subarray on the extended array, so no manual
// packing is needed and the same code serves 2D and 3D. The 5/7-point stencil has no diagonal
// terms, so only face neighbours are exchanged (no edges or corners).
//
//   exchange(u)       blocking: one MPI_Sendrecv per direction per decomposed axis
//   start(u); finish() non-blocking: Irecv/Isend all faces, compute the interior, then Waitall
#pragma once

#include "decomp.hpp"

#include <mpi.h>
#include <vector>

namespace pcg {

class Halo {
  public:
    explicit Halo(const Decomp& d);
    ~Halo();
    Halo(const Halo&) = delete;
    Halo& operator=(const Halo&) = delete;

    void exchange(double* u);
    void start(double* u);
    void finish();

    // Bit a set = axis a has at least one real neighbour (used to size the inner region).
    unsigned comm_axes() const {
        return axes_mask_;
    }

  private:
    MPI_Comm comm_;
    int nbr_lo_[3], nbr_hi_[3];
    std::vector<int> axes_; // decomposed axes
    unsigned axes_mask_ = 0;
    MPI_Datatype send_lo_[3], send_hi_[3], recv_lo_[3], recv_hi_[3];
    std::vector<MPI_Request> reqs_;
};

} // namespace pcg
