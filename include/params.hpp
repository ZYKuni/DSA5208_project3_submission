// Shared command-line interface for every executable (serial, mpi, omp, cuda).
// All team members MUST use this parser so that every binary accepts the same flags.
#pragma once

#include <string>

namespace pcg {

struct Params {
    int dim = 2;                  // --dim 2|3        problem dimension
    long n = 256;                 // --n N            interior grid points per side (global)
    double tol = 1e-8;            // --tol T          stop when ||r||_2 / ||b||_2 < tol
    int maxit = 10000;            // --maxit M        iteration cap
    std::string decomp = "cart";  // --decomp slab|cart     MPI domain decomposition
    std::string halo = "block";   // --halo block|overlap   halo exchange strategy
    std::string cg = "std";       // --cg std|pipe          standard or single-reduction CG
    std::string csv = "";         // --csv FILE       append one result row (empty = stdout only)
    int repeat = 1;               // --repeat R       repeat the solve R times, report the minimum
    bool verbose = false;         // --verbose        print residual every 100 iterations
};

// Parses argv into Params. Unknown flags or bad values print usage and exit(1).
Params parse_args(int argc, char** argv);

// Prints usage to stderr.
void print_usage(const char* prog);

} // namespace pcg
