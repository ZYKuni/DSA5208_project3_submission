// Standalone OpenMP solver. Distributed execution uses B's solve_mpi.
#include "solver.hpp"
#include "cli.hpp"
#include "kernel_openmp.hpp"
#include <omp.h>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

int main(int argc, char** argv) {
    using namespace poisson;
    try {
        const auto options = parse_cli(argc, argv, false, true);
        if (options.help) return 0;
        const auto& c = options.config;
        const bool threaded = options.kernel == "openmp";
        omp_set_dynamic(0);
        const int threads = threaded ? openmp_team_size() : 1;
        const auto update = threaded ? jacobi_rows_openmp : jacobi_rows;
        const auto residual = threaded ? residual_squared_rows_openmp : residual_squared_rows;
        const auto norm = threaded ? squared_norm_rows_openmp : squared_norm_rows;
        Grid u(c.n, c.n), next(c.n, c.n), rhs(c.n, c.n);
        initialize_rhs(rhs, c.problem);
        SolveResult result;
        result.rhs_l2 = std::sqrt(norm(rhs, 1, c.n + 1));
        auto measure = [&]() {
            result.final_absolute_residual = std::sqrt(residual(u, rhs, 1, c.n + 1));
            result.final_relative_residual = result.final_absolute_residual /
                (result.rhs_l2 > 0 ? result.rhs_l2 : 1.0);
            if (!std::isfinite(result.final_relative_residual)) throw std::runtime_error("nonfinite residual");
            result.converged = result.final_relative_residual <= c.tolerance;
        };
        const double start = omp_get_wtime();
        if (c.mode == Mode::Converge) { measure(); ++result.residual_checks; }
        while (result.actual_iterations < c.iterations &&
               (c.mode == Mode::Fixed || !result.converged)) {
            update(u, next, rhs, 1, c.n + 1);
            u.values.swap(next.values);
            ++result.actual_iterations;
            if (result.actual_iterations % c.check_every == 0 || result.actual_iterations == c.iterations) {
                measure(); ++result.residual_checks;
            }
        }
        result.solve_seconds = omp_get_wtime() - start;
        measure(); // Final diagnostics and output are outside solve timing.
        double error2 = 0, exact2 = 0, maxerror = 0;
        for (std::size_t i = 1; i <= c.n; ++i) for (std::size_t j = 1; j <= c.n; ++j) {
            const double exact = exact_value(i, j, c.n, c.problem), diff = u(i,j) - exact;
            maxerror = std::max(maxerror, std::abs(diff)); error2 += diff*diff; exact2 += exact*exact;
        }
        result.exact_max_abs_error = maxerror;
        result.exact_relative_l2_error = std::sqrt(error2) / (exact2 > 0 ? std::sqrt(exact2) : 1.0);
        result.stop_reason = c.mode == Mode::Fixed ? "fixed_iterations" : result.converged ? "tolerance" : "max_iterations";
        if (!options.solution_path.empty()) write_solution(options.solution_path, u);
        print_result(c, result, threaded ? "openmp" : "serial_kernel_driver", 1, threads,
                     "none", options.kernel.c_str(), "openmp", 0, _OPENMP);
        return c.mode == Mode::Converge && !result.converged ? 2 : 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << '\n';
        return 1;
    }
}
