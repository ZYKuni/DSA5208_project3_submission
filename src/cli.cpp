#include "cli.hpp"
#include <cctype>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace poisson {
std::size_t parse_integer(const std::string& s) {
    if (s.empty()) throw std::invalid_argument("empty integer");
    for (unsigned char ch : s)
        if (!std::isdigit(ch)) throw std::invalid_argument("expected unsigned integer: " + s);
    std::size_t used = 0;
    const auto value = std::stoull(s, &used);
    if (used != s.size() || value > std::numeric_limits<std::size_t>::max())
        throw std::invalid_argument("integer out of range");
    return static_cast<std::size_t>(value);
}
void write_solution(const std::string& path, const poisson::Grid& u) {
    std::ofstream out(path);
    if (!out) throw std::runtime_error("cannot open solution file: " + path);
    out << "global_i,global_j,u\n" << std::setprecision(17);
    for (std::size_t i = 0; i <= u.n + 1; ++i)
        for (std::size_t j = 0; j <= u.n + 1; ++j)
            out << i << ',' << j << ',' << u(i, j) << '\n';
    out.close();
    if (!out) throw std::runtime_error("failed to write solution file: " + path);
}
CliOptions parse_cli(int argc, char** argv, bool mpi, bool openmp) {
    CliOptions options;
    if (openmp) options.kernel = "openmp";
    auto& c = options.config;
    auto& solution_path = options.solution_path;
        for (int a = 1; a < argc; ++a) {
            const std::string key = argv[a];
            if (key == "--help") {
                std::cout << (mpi ? (openmp ? "poisson_hybrid" : "poisson_mpi") : (openmp ? "poisson_openmp" : "poisson_serial")) << " [--n N] [--mode fixed|converge] [--iterations K]\n"
                          << "  [--problem continuous-sine|discrete-sine|zero|discrete-mixed] [--tol T]\n"
                          << "  [--check-every K] [--solution output.csv]\n"
                          << "Defaults: n=31, fixed, iterations=1000, continuous-sine, tol=1e-10, check-every=1\n";
                if (mpi) std::cout << "  [--communication sendrecv|overlap] (default: sendrecv)\n";
                if (openmp) std::cout << "  [--kernel serial|openmp] (default: openmp)\n";
                options.help = true; return options;
            }
            if (a + 1 == argc) throw std::invalid_argument("missing value for " + key);
            const std::string value = argv[++a];
            if (key == "--communication" && mpi) {
                if (value != "sendrecv" && value != "overlap") throw std::invalid_argument("unknown communication: " + value);
                options.communication = value;
            } else if (key == "--kernel" && openmp) {
                if (value != "serial" && value != "openmp") throw std::invalid_argument("unknown kernel: " + value);
                options.kernel = value;
            } else if (key == "--n") c.n = parse_integer(value);
            else if (key == "--iterations") c.iterations = parse_integer(value);
            else if (key == "--check-every") c.check_every = parse_integer(value);
            else if (key == "--tol") {
                std::size_t used = 0;
                c.tolerance = std::stod(value, &used);
                if (used != value.size()) throw std::invalid_argument("invalid tolerance");
            } else if (key == "--mode") {
                if (value == "fixed") c.mode = poisson::Mode::Fixed;
                else if (value == "converge") c.mode = poisson::Mode::Converge;
                else throw std::invalid_argument("unknown mode: " + value);
            } else if (key == "--problem") {
                if (value == "continuous-sine") c.problem = poisson::Problem::ContinuousSine;
                else if (value == "discrete-sine") c.problem = poisson::Problem::DiscreteSine;
                else if (value == "zero") c.problem = poisson::Problem::Zero;
                else if (value == "discrete-mixed") c.problem = poisson::Problem::DiscreteMixed;
                else throw std::invalid_argument("unknown problem: " + value);
            } else if (key == "--solution") solution_path = value;
            else throw std::invalid_argument("unknown option: " + key);
        }
    validate_config(c);
    return options;
}
void print_result(const Config& c, const SolveResult& r, const char* variant, int ranks, int threads,
                  const char* communication, const char* kernel, const char* driver,
                  int mpi_thread_provided, int openmp_version) {
        std::cout << std::setprecision(17) << std::boolalpha
            << "{\"schema_version\":1,\"variant\":\"" << variant << "\",\"n\":" << c.n
            << ",\"mode\":\"" << poisson::name(c.mode) << "\",\"problem\":\"" << poisson::name(c.problem)
            << "\",\"requested_iterations\":" << c.iterations
            << ",\"actual_iterations\":" << r.actual_iterations
            << ",\"tolerance\":" << c.tolerance << ",\"check_every\":" << c.check_every
            << ",\"ranks\":" << ranks << ",\"threads_per_rank\":" << threads << ",\"solve_seconds_max\":" << r.solve_seconds
            << ",\"seconds_per_iteration\":" << (r.actual_iterations ? r.solve_seconds / r.actual_iterations : 0)
            << ",\"timed_residual_checks\":" << r.residual_checks
            << ",\"rhs_l2\":" << r.rhs_l2 << ",\"final_absolute_residual\":" << r.final_absolute_residual
            << ",\"final_relative_residual\":" << r.final_relative_residual
            << ",\"residual_kind\":\"" << (r.rhs_l2 > 0 ? "relative_l2" : "absolute_l2")
            << "\",\"exact_max_abs_error\":" << r.exact_max_abs_error
            << ",\"exact_relative_l2_error\":" << r.exact_relative_l2_error
            << ",\"converged\":" << r.converged << ",\"stop_reason\":\"" << r.stop_reason
            << "\",\"communication\":\"" << communication << "\",\"kernel\":\"" << kernel
            << "\",\"driver\":\"" << driver << "\",\"mpi_thread_provided\":" << mpi_thread_provided
            << ",\"openmp_version\":" << openmp_version << "}\n";
}
} // namespace poisson
