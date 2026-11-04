// C OpenMP kernels injected into B's MPI solver; all MPI calls stay on main.
#include "mpi_solver.hpp"
#include "decomposition.hpp"
#include "cli.hpp"
#include "kernel_openmp.hpp"
#include <omp.h>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    int provided = 0;
    if (MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided) != MPI_SUCCESS) return 1;
    int rank = 0, size = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    try {
        if (provided < MPI_THREAD_FUNNELED)
            throw std::runtime_error("MPI_THREAD_FUNNELED support required");
        for (int a = 1; a < argc; ++a) {
            if (std::string(argv[a]) == "--help") {
                if (rank == 0) poisson::parse_cli(argc, argv, true, true);
                MPI_Finalize();
                return 0;
            }
        }
        const auto options = poisson::parse_cli(argc, argv, true, true);
        const auto& c = options.config;
        const auto slab = poisson::decompose(c.n, size, rank);
        omp_set_dynamic(0);
        const bool threaded = options.kernel == "openmp";
        const int threads = threaded ? poisson::openmp_team_size() : 1;
        int minimum = 0, maximum = 0;
        MPI_Allreduce(&threads, &minimum, 1, MPI_INT, MPI_MIN, MPI_COMM_WORLD);
        MPI_Allreduce(&threads, &maximum, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
        if (minimum != maximum) throw std::runtime_error("inconsistent thread teams across ranks");
        poisson::LocalKernels kernels;
        if (threaded) kernels = {poisson::jacobi_rows_openmp,
            poisson::residual_squared_rows_openmp, poisson::squared_norm_rows_openmp};
        poisson::Grid u(c.n, slab.rows, slab.offset);
        const auto communication = options.communication == "sendrecv"
            ? poisson::Communication::Sendrecv : poisson::Communication::Overlap;
        const auto result = poisson::solve_mpi(c, u, communication, MPI_COMM_WORLD, kernels);
        if (!options.solution_path.empty()) {
            const auto global = poisson::gather_solution(u, MPI_COMM_WORLD);
            if (rank == 0) poisson::write_solution(options.solution_path, *global);
        }
        if (rank == 0) poisson::print_result(c, result,
            threaded ? "mpi_openmp" : poisson::name(communication), size, threads,
            options.communication.c_str(), options.kernel.c_str(), "b-mpi", provided, _OPENMP);
        const int status = c.mode == poisson::Mode::Converge && !result.converged ? 2 : 0;
        MPI_Finalize();
        return status;
    } catch (const std::exception& e) {
        std::cerr << "rank " << rank << " error: " << e.what() << '\n';
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }
}
