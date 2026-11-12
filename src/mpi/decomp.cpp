#include "decomp.hpp"

#include <cstdio>

namespace pcg {

void split_axis(long n, int P, int c, long& count, long& first) {
    const long base = n / P, extra = n % P;
    count = base + (c < extra ? 1 : 0);
    first = c * base + (c < extra ? c : extra);
}

Decomp make_decomp(MPI_Comm comm, int dim, long n, const std::string& kind) {
    Decomp d;
    d.kind = kind;
    int world_size = 1;
    MPI_Comm_size(comm, &world_size);

    // Cartesian dimensions over the active axes only. In 2D the active axes are 1 (y), 2 (x).
    const int first_axis = (dim == 3) ? 0 : 1;
    int cdims[3] = {0, 0, 0};
    if (kind == "slab") {
        for (int c = 0; c < dim; ++c)
            cdims[c] = 1;
        cdims[0] = world_size; // slowest active axis
    } else {
        MPI_Dims_create(world_size, dim, cdims);
    }
    int periods[3] = {0, 0, 0};
    MPI_Cart_create(comm, dim, cdims, periods, /*reorder=*/1, &d.comm);
    MPI_Comm_rank(d.comm, &d.rank);
    MPI_Comm_size(d.comm, &d.size);
    int ccoords[3] = {0, 0, 0};
    MPI_Cart_coords(d.comm, d.rank, dim, ccoords);

    long L[3] = {1, 1, 1}, off[3] = {0, 0, 0};
    for (int a = 0; a < 3; ++a) {
        d.nbr_lo[a] = d.nbr_hi[a] = MPI_PROC_NULL;
        if (a < first_axis)
            continue;
        const int c = a - first_axis;
        d.pdims[a] = cdims[c];
        d.coords[a] = ccoords[c];
        MPI_Cart_shift(d.comm, c, 1, &d.nbr_lo[a], &d.nbr_hi[a]);
        if (n < d.pdims[a]) {
            if (d.rank == 0) {
                std::fprintf(stderr,
                             "error: n=%ld is smaller than %d processes along axis %d (%s)\n", n,
                             d.pdims[a], a, kind.c_str());
            }
            MPI_Abort(comm, 1);
        }
        split_axis(n, d.pdims[a], d.coords[a], L[a], off[a]);
    }
    d.block = make_block(dim, n, L, off);
    return d;
}

void free_decomp(Decomp& d) {
    if (d.comm != MPI_COMM_NULL)
        MPI_Comm_free(&d.comm);
    d.comm = MPI_COMM_NULL;
}

} // namespace pcg
