#include "mpi_solver.hpp"
#include <limits>
#include <stdexcept>

namespace poisson {
namespace {
struct Neighbors { int up, down, count; };
Neighbors neighbors(const Grid& u, MPI_Comm comm) {
    int rank = 0, size = 0;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    if (u.n > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::length_error("halo row exceeds MPI int count");
    return {rank == 0 ? MPI_PROC_NULL : rank - 1,
            rank + 1 == size ? MPI_PROC_NULL : rank + 1, static_cast<int>(u.n)};
}
constexpr int to_up = 10, to_down = 11;
}
void exchange_halo(Grid& u, MPI_Comm comm) {
    const auto v = neighbors(u, comm);
    MPI_Sendrecv(&u(1, 1), v.count, MPI_DOUBLE, v.up, to_up,
                 &u(u.rows + 1, 1), v.count, MPI_DOUBLE, v.down, to_up,
                 comm, MPI_STATUS_IGNORE);
    MPI_Sendrecv(&u(u.rows, 1), v.count, MPI_DOUBLE, v.down, to_down,
                 &u(0, 1), v.count, MPI_DOUBLE, v.up, to_down,
                 comm, MPI_STATUS_IGNORE);
}
std::array<MPI_Request, 4> begin_halo(Grid& u, MPI_Comm comm) {
    const auto v = neighbors(u, comm);
    std::array<MPI_Request, 4> requests{};
    MPI_Irecv(&u(0, 1), v.count, MPI_DOUBLE, v.up, to_down, comm, &requests[0]);
    MPI_Irecv(&u(u.rows + 1, 1), v.count, MPI_DOUBLE, v.down, to_up, comm, &requests[1]);
    MPI_Isend(&u(1, 1), v.count, MPI_DOUBLE, v.up, to_up, comm, &requests[2]);
    MPI_Isend(&u(u.rows, 1), v.count, MPI_DOUBLE, v.down, to_down, comm, &requests[3]);
    return requests;
}
void finish_halo(std::array<MPI_Request, 4>& requests) {
    MPI_Waitall(static_cast<int>(requests.size()), requests.data(), MPI_STATUSES_IGNORE);
}
} // namespace poisson
