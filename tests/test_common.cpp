// Smoke test for the shared interface (params parser + CSV format).
// Solver validation tests (convergence order, serial vs parallel agreement) go in this folder too.
#undef NDEBUG // keep assert() active in Release builds
#include "csv.hpp"
#include "params.hpp"
#include "problem.hpp"

#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>

int main() {
    const char* argv[] = {"t", "--dim", "3", "--n", "64", "--cg", "pipe", "--halo", "overlap"};
    pcg::Params p = pcg::parse_args(9, const_cast<char**>(argv));
    assert(p.dim == 3 && p.n == 64 && p.cg == "pipe" && p.halo == "overlap");

    pcg::Result r;
    r.impl = "serial";
    r.decomp = r.halo = "none";
    r.cg = "std";
    std::string row = pcg::csv_row(r);
    int commas_row = 0, commas_hdr = 0;
    for (char c : row)
        commas_row += (c == ',');
    for (const char* c = pcg::csv_header(); *c; ++c)
        commas_hdr += (*c == ',');
    assert(commas_row == commas_hdr);

    // u(0.5, 0.5) = (0.25 e^0.5)^2 = e / 16; u vanishes on the boundary.
    assert(std::abs(pcg::exact_u(2, 0.5, 0.5, 0.0) - std::exp(1.0) / 16.0) < 1e-12);
    assert(pcg::exact_u(3, 0.0, 0.3, 0.7) == 0.0 && pcg::exact_u(3, 0.3, 0.7, 1.0) == 0.0);
    std::printf("test_common: OK\n");
    return 0;
}
