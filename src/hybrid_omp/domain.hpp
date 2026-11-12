#pragma once
#include "local.hpp"
#include <algorithm>
#include <array>
#include <climits>
#include <mpi.h>
#include <stdexcept>

namespace pcg {
// MPI coordinates follow the in-memory axis order (z, y, x); in 2D use (y, x).
class Domain {
  public:
    MPI_Comm comm;
    Tile tile;
    int origin[3]{}, dim;
    MPI_Datatype face[3];
    int lo[3], hi[3];
    std::size_t low_send[3], high_send[3], low_recv[3], high_recv[3];
    Domain(long n, int d, bool slab) : dim(d) {
        int ranks, rank, dims[3]{}, periods[3]{}, coords[3]{};
        MPI_Comm_size(MPI_COMM_WORLD, &ranks);
        if (slab)
            std::fill(dims + 1, dims + d, 1);
        MPI_Dims_create(ranks, d, dims);
        if (n > INT_MAX - 2 || *std::max_element(dims, dims + d) > n)
            throw std::runtime_error("invalid local grid dimensions");
        MPI_Cart_create(MPI_COMM_WORLD, d, dims, periods, 0, &comm);
        MPI_Comm_rank(comm, &rank);
        MPI_Cart_coords(comm, rank, d, coords);
        int extent[3]{1, 1, 1};
        for (int a = 0; a < d; ++a) {
            const int ax = 3 - d + a;
            extent[ax] = n / dims[a] + (coords[a] < n % dims[a]);
            origin[ax] = coords[a] * (n / dims[a]) + std::min<long>(coords[a], n % dims[a]);
        }
        tile = {extent[2], extent[1], extent[0]};
        int padded[]{tile.nz + 2, tile.ny + 2, tile.nx + 2}, zero[3]{};
        const std::size_t strides[]{std::size_t(padded[1]) * padded[2], std::size_t(padded[2]), 1};
        for (int a = 0; a < d; ++a) {
            const int ax = 3 - d + a;
            int shape[]{extent[0], extent[1], extent[2]};
            shape[ax] = 1;
            MPI_Type_create_subarray(3, padded, shape, zero, MPI_ORDER_C, MPI_DOUBLE, &face[a]);
            MPI_Type_commit(&face[a]);
            low_send[a] = tile.ghost(0);
            high_send[a] = low_send[a] + (extent[ax] - 1) * strides[ax];
            low_recv[a] = low_send[a] - strides[ax];
            high_recv[a] = high_send[a] + strides[ax];
            MPI_Cart_shift(comm, a, 1, &lo[a], &hi[a]);
        }
    }
    ~Domain() {
        for (int a = 0; a < dim; ++a)
            MPI_Type_free(&face[a]);
        MPI_Comm_free(&comm);
    }
    void exchange(double* p) const {
        for (int a = 0; a < dim; ++a) {
            MPI_Sendrecv(p + low_send[a], 1, face[a], lo[a], 0, p + high_recv[a], 1, face[a], hi[a],
                         0, comm, MPI_STATUS_IGNORE);
            MPI_Sendrecv(p + high_send[a], 1, face[a], hi[a], 1, p + low_recv[a], 1, face[a], lo[a],
                         1, comm, MPI_STATUS_IGNORE);
        }
    }
};
} // namespace pcg
