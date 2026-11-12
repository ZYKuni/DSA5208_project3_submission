#include "halo.hpp"

namespace pcg {

namespace {

MPI_Datatype face_type(const Block& b, int axis, long start_along_axis) {
    int sizes[3], sub[3], starts[3];
    for (int a = 0; a < 3; ++a) {
        sizes[a] = static_cast<int>(b.E[a]);
        sub[a] = static_cast<int>(b.L[a]);
        starts[a] = b.G[a];
    }
    sub[axis] = 1;
    starts[axis] = static_cast<int>(start_along_axis);
    MPI_Datatype t;
    MPI_Type_create_subarray(3, sizes, sub, starts, MPI_ORDER_C, MPI_DOUBLE, &t);
    MPI_Type_commit(&t);
    return t;
}

} // namespace

Halo::Halo(const Decomp& d) : comm_(d.comm) {
    const Block& b = d.block;
    for (int a = 0; a < 3; ++a) {
        nbr_lo_[a] = d.nbr_lo[a];
        nbr_hi_[a] = d.nbr_hi[a];
        send_lo_[a] = send_hi_[a] = recv_lo_[a] = recv_hi_[a] = MPI_DATATYPE_NULL;
        if (d.pdims[a] <= 1)
            continue;
        axes_.push_back(a);
        if (nbr_lo_[a] != MPI_PROC_NULL || nbr_hi_[a] != MPI_PROC_NULL)
            axes_mask_ |= 1u << a;
        const long g = b.G[a], l = b.L[a];
        send_lo_[a] = face_type(b, a, g);         // first owned layer
        send_hi_[a] = face_type(b, a, g + l - 1); // last owned layer
        recv_lo_[a] = face_type(b, a, 0);         // lower ghost layer
        recv_hi_[a] = face_type(b, a, g + l);     // upper ghost layer
    }
    reqs_.reserve(4 * axes_.size());
}

Halo::~Halo() {
    for (int a : axes_) {
        MPI_Type_free(&send_lo_[a]);
        MPI_Type_free(&send_hi_[a]);
        MPI_Type_free(&recv_lo_[a]);
        MPI_Type_free(&recv_hi_[a]);
    }
}

void Halo::exchange(double* u) {
    for (int a : axes_) {
        // Upward: my top layer -> hi neighbour's lower ghost.
        MPI_Sendrecv(u, 1, send_hi_[a], nbr_hi_[a], 2 * a, u, 1, recv_lo_[a], nbr_lo_[a], 2 * a,
                     comm_, MPI_STATUS_IGNORE);
        // Downward: my bottom layer -> lo neighbour's upper ghost.
        MPI_Sendrecv(u, 1, send_lo_[a], nbr_lo_[a], 2 * a + 1, u, 1, recv_hi_[a], nbr_hi_[a],
                     2 * a + 1, comm_, MPI_STATUS_IGNORE);
    }
}

void Halo::start(double* u) {
    reqs_.clear();
    MPI_Request r;
    for (int a : axes_) {
        if (nbr_lo_[a] != MPI_PROC_NULL) {
            MPI_Irecv(u, 1, recv_lo_[a], nbr_lo_[a], 2 * a, comm_, &r);
            reqs_.push_back(r);
        }
        if (nbr_hi_[a] != MPI_PROC_NULL) {
            MPI_Irecv(u, 1, recv_hi_[a], nbr_hi_[a], 2 * a + 1, comm_, &r);
            reqs_.push_back(r);
        }
    }
    for (int a : axes_) {
        if (nbr_hi_[a] != MPI_PROC_NULL) {
            MPI_Isend(u, 1, send_hi_[a], nbr_hi_[a], 2 * a, comm_, &r);
            reqs_.push_back(r);
        }
        if (nbr_lo_[a] != MPI_PROC_NULL) {
            MPI_Isend(u, 1, send_lo_[a], nbr_lo_[a], 2 * a + 1, comm_, &r);
            reqs_.push_back(r);
        }
    }
}

void Halo::finish() {
    if (!reqs_.empty()) {
        MPI_Waitall(static_cast<int>(reqs_.size()), reqs_.data(), MPI_STATUSES_IGNORE);
    }
    reqs_.clear();
}

} // namespace pcg
