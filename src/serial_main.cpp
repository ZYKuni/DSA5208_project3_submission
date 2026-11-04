#include "solver.hpp"
#include "cli.hpp"
#include <iostream>
#include <exception>
int main(int argc, char** argv) {
    try {
        const auto options = poisson::parse_cli(argc, argv);
        if (options.help) return 0;
        const auto& c = options.config;
        poisson::Grid u(c.n, c.n);
        const auto r = poisson::solve_serial(c, u);
        if (!options.solution_path.empty()) poisson::write_solution(options.solution_path, u);
        poisson::print_result(c, r, "serial");
        return c.mode == poisson::Mode::Converge && !r.converged ? 2 : 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << '\n';
        return 1;
    }
}
