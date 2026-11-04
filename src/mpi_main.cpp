#include "mpi_solver.hpp"
#include "decomposition.hpp"
#include "cli.hpp"
#include <exception>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    int provided = 0;
    if (MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided) != MPI_SUCCESS) return 1;
    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    try {
        if (provided < MPI_THREAD_FUNNELED)
            throw std::runtime_error("MPI_THREAD_FUNNELED support required");
        // Only rank zero prints help; all ranks exit together.
        for (int a = 1; a < argc; ++a) {
            if (std::string(argv[a]) == "--help") {
                if (rank == 0) poisson::parse_cli(argc, argv, true);
                MPI_Finalize();
                return 0;
            }
        }
        const auto options = poisson::parse_cli(argc, argv, true);
        const auto& c = options.config;
        const auto slab = poisson::decompose(c.n, size, rank);
        if (c.n > static_cast<std::size_t>(std::numeric_limits<int>::max()))
            throw std::length_error("n exceeds MPI int count");
        poisson::Grid u(c.n, slab.rows, slab.offset);
        const auto communication = options.communication == "sendrecv"
            ? poisson::Communication::Sendrecv : poisson::Communication::Overlap;
        const auto r = poisson::solve_mpi(c, u, communication, MPI_COMM_WORLD);
        if (!options.solution_path.empty()) {
            const auto global = poisson::gather_solution(u, MPI_COMM_WORLD);
            if (rank == 0) poisson::write_solution(options.solution_path, *global);
        }
        if (rank == 0) poisson::print_result(c, r, poisson::name(communication), size, 1,
            options.communication.c_str(), "serial", "b-mpi", provided);
        const int status = c.mode == poisson::Mode::Converge && !r.converged ? 2 : 0;
        MPI_Finalize();
        return status;
    } catch (const std::exception& e) {
        std::cerr << "rank " << rank << " error: " << e.what() << '\n';
        // A rank-local allocation/I/O failure must not strand peers in a collective.
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }
}
