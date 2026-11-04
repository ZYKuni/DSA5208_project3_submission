#include "mpi_solver.hpp"
#include "decomposition.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

namespace poisson {
const char* name(Communication c) {
    return c == Communication::Sendrecv ? "mpi-sendrecv" : "mpi-overlap";
}
namespace {
double global_sum(double local, MPI_Comm comm) {
    double sum = 0;
    MPI_Allreduce(&local, &sum, 1, MPI_DOUBLE, MPI_SUM, comm);
    return sum;
}
}
SolveResult solve_mpi(const Config& c, Grid& u, Communication communication,
                      MPI_Comm comm, const LocalKernels& kernels) {
    validate_config(c);
    int rank = 0, size = 0;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    const auto slab = decompose(c.n, size, rank);
    if (u.n != c.n || u.rows != slab.rows || u.row_offset != slab.offset)
        throw std::invalid_argument("MPI solver requires the rank's assigned slab");
    if (c.n > static_cast<std::size_t>(std::numeric_limits<int>::max()))
        throw std::length_error("n exceeds MPI int count");
    if (!kernels.update || !kernels.residual || !kernels.norm)
        throw std::invalid_argument("null local kernel");
    Grid next(c.n, u.rows, u.row_offset), rhs(c.n, u.rows, u.row_offset);
    std::fill(u.values.begin(), u.values.end(), 0.0);
    initialize_rhs(rhs, c.problem);
    SolveResult result;
    result.rhs_l2 = std::sqrt(global_sum(kernels.norm(rhs, 1, u.rows + 1), comm));
    const double denominator = result.rhs_l2 > 0 ? result.rhs_l2 : 1.0;
    auto measure_residual = [&]() {
        // Swapping leaves stale ghosts: synchronize the CURRENT solution first.
        exchange_halo(u, comm);
        result.final_absolute_residual = std::sqrt(global_sum(kernels.residual(u, rhs, 1, u.rows + 1), comm));
        result.final_relative_residual = result.final_absolute_residual / denominator;
        if (!std::isfinite(result.final_relative_residual))
            throw std::runtime_error("non-finite residual");
        result.converged = result.final_relative_residual <= c.tolerance;
    };
    MPI_Barrier(comm);
    const double start = MPI_Wtime();
    if (c.mode == Mode::Converge) {
        measure_residual();
        ++result.residual_checks;
    }
    while (result.actual_iterations < c.iterations &&
           (c.mode == Mode::Fixed || !result.converged)) {
        if (communication == Communication::Sendrecv) {
            exchange_halo(u, comm);
            kernels.update(u, next, rhs, 1, u.rows + 1);
        } else {
            auto requests = begin_halo(u, comm);
            if (u.rows > 2) kernels.update(u, next, rhs, 2, u.rows);
            finish_halo(requests); // Includes sends: old storage can safely be reused.
            kernels.update(u, next, rhs, 1, 2);
            if (u.rows > 1) kernels.update(u, next, rhs, u.rows, u.rows + 1);
        }
        u.values.swap(next.values);
        ++result.actual_iterations;
        if (result.actual_iterations % c.check_every == 0 || result.actual_iterations == c.iterations) {
            measure_residual();
            ++result.residual_checks;
        }
    }
    const double elapsed = MPI_Wtime() - start;
    MPI_Allreduce(&elapsed, &result.solve_seconds, 1, MPI_DOUBLE, MPI_MAX, comm);
    // Final diagnostics and optional gathering are outside solve timing.
    measure_residual();
    double error2 = 0, exact2 = 0, max_error = 0;
    for (std::size_t i = 1; i <= u.rows; ++i) {
        for (std::size_t j = 1; j <= c.n; ++j) {
            const double exact = exact_value(u.row_offset + i, j, c.n, c.problem);
            const double diff = u(i, j) - exact;
            max_error = std::max(max_error, std::abs(diff));
            error2 += diff * diff;
            exact2 += exact * exact;
        }
    }
    MPI_Allreduce(&max_error, &result.exact_max_abs_error, 1, MPI_DOUBLE, MPI_MAX, comm);
    error2 = global_sum(error2, comm);
    exact2 = global_sum(exact2, comm);
    result.exact_relative_l2_error = std::sqrt(error2) / (exact2 > 0 ? std::sqrt(exact2) : 1.0);
    result.stop_reason = c.mode == Mode::Fixed ? "fixed_iterations"
                        : result.converged ? "tolerance" : "max_iterations";
    return result;
}
std::unique_ptr<Grid> gather_solution(const Grid& local, MPI_Comm comm) {
    int rank = 0, size = 0;
    MPI_Comm_rank(comm, &rank);
    MPI_Comm_size(comm, &size);
    const auto limit = static_cast<std::size_t>(std::numeric_limits<int>::max());
    // Deliberate small-output limit; ordinary solves do not impose a global count.
    if (local.n > limit / local.stride)
        throw std::length_error("solution gathering exceeds MPI_Gatherv int range");
    std::vector<int> counts(size), offsets(size);
    for (int r = 0; r < size; ++r) {
        const auto slab = decompose(local.n, size, r);
        counts[r] = static_cast<int>(slab.rows * local.stride);
        offsets[r] = static_cast<int>(slab.offset * local.stride);
    }
    std::unique_ptr<Grid> global;
    if (rank == 0) global = std::make_unique<Grid>(local.n, local.n);
    MPI_Gatherv(&local.values[local.stride], counts[rank], MPI_DOUBLE,
                rank == 0 ? &global->values[global->stride] : nullptr,
                counts.data(), offsets.data(), MPI_DOUBLE, 0, comm);
    return global;
}
} // namespace poisson
