#pragma once
#include <cstddef>
#include <string>

namespace poisson {
enum class Mode { Fixed, Converge };
enum class Problem { ContinuousSine, DiscreteSine, Zero, DiscreteMixed };
struct Config {
    std::size_t n = 31;            // Global interior points in each direction.
    std::size_t iterations = 1000; // Exact count (fixed) or upper bound (converge).
    std::size_t check_every = 1;
    double tolerance = 1e-10;
    Mode mode = Mode::Fixed;
    Problem problem = Problem::ContinuousSine;
};
struct SolveResult {
    std::size_t actual_iterations = 0;
    std::size_t residual_checks = 0; // Timed checks, excluding final diagnostics.
    double solve_seconds = 0;
    double final_absolute_residual = 0;
    double rhs_l2 = 0;
    double final_relative_residual = 0; // Absolute fallback when rhs_l2 == 0.
    double exact_max_abs_error = 0;
    double exact_relative_l2_error = 0;
    bool converged = false;
    std::string stop_reason;
};
void validate_config(const Config& config);
const char* name(Mode mode);
const char* name(Problem problem);
} // namespace poisson
