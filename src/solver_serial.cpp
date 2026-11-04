#include "solver.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <stdexcept>

namespace poisson {
const char* name(Mode mode) { return mode == Mode::Fixed ? "fixed" : "converge"; }
const char* name(Problem problem) {
    switch (problem) {
        case Problem::ContinuousSine: return "continuous-sine";
        case Problem::DiscreteSine: return "discrete-sine";
        case Problem::Zero: return "zero";
        case Problem::DiscreteMixed: return "discrete-mixed";
    }
    throw std::invalid_argument("unknown problem");
}
void validate_config(const Config& c) {
    if (c.n == 0 || c.check_every == 0 || !std::isfinite(c.tolerance) || c.tolerance <= 0)
        throw std::invalid_argument("n/check-every must be positive; tolerance must be finite and positive");
    if (c.problem == Problem::DiscreteMixed && c.n < 3)
        throw std::invalid_argument("discrete-mixed requires n >= 3 to resolve both modes");
    if (c.mode == Mode::Converge && c.iterations == 0)
        throw std::invalid_argument("converge mode requires a positive iteration limit");
}
SolveResult solve_serial(const Config& c, Grid& u) {
    validate_config(c);
    if (u.n != c.n || u.rows != c.n || u.row_offset != 0)
        throw std::invalid_argument("serial solver requires the complete global grid");
    Grid next(c.n, c.n), rhs(c.n, c.n);
    std::fill(u.values.begin(), u.values.end(), 0.0);
    initialize_rhs(rhs, c.problem);
    SolveResult result;
    result.rhs_l2 = std::sqrt(squared_norm_rows(rhs, 1, c.n + 1));
    const double denominator = result.rhs_l2 > 0 ? result.rhs_l2 : 1.0;
    auto measure_residual = [&]() {
        result.final_absolute_residual = std::sqrt(residual_squared_rows(u, rhs, 1, c.n + 1));
        result.final_relative_residual = result.final_absolute_residual / denominator;
        if (!std::isfinite(result.final_relative_residual))
            throw std::runtime_error("non-finite residual");
        result.converged = result.final_relative_residual <= c.tolerance;
    };
    // Allocation, initialization and ||f|| are outside the solve interval.
    const auto start = std::chrono::steady_clock::now();
    if (c.mode == Mode::Converge) {
        measure_residual();
        ++result.residual_checks;
    }
    while (result.actual_iterations < c.iterations &&
           (c.mode == Mode::Fixed || !result.converged)) {
        jacobi_rows(u, next, rhs, 1, c.n + 1);
        u.values.swap(next.values);
        ++result.actual_iterations;
        if (result.actual_iterations % c.check_every == 0 || result.actual_iterations == c.iterations) {
            measure_residual();
            ++result.residual_checks;
        }
    }
    const auto end = std::chrono::steady_clock::now();
    result.solve_seconds = std::chrono::duration<double>(end - start).count();
    // Always compute final diagnostics outside timing (including K=0).
    measure_residual();
    double error2 = 0, exact2 = 0;
    for (std::size_t i = 1; i <= c.n; ++i) {
        for (std::size_t j = 1; j <= c.n; ++j) {
            const double exact = exact_value(i, j, c.n, c.problem);
            const double diff = u(i, j) - exact;
            result.exact_max_abs_error = std::max(result.exact_max_abs_error, std::abs(diff));
            error2 += diff * diff;
            exact2 += exact * exact;
        }
    }
    result.exact_relative_l2_error = std::sqrt(error2) / (exact2 > 0 ? std::sqrt(exact2) : 1.0);
    result.stop_reason = c.mode == Mode::Fixed ? "fixed_iterations"
                        : result.converged ? "tolerance" : "max_iterations";
    return result;
}
} // namespace poisson
