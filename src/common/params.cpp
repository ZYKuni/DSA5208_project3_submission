#include "params.hpp"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

namespace pcg {

void print_usage(const char* prog) {
    std::fprintf(stderr,
                 "Usage: %s [options]\n"
                 "  --dim 2|3               problem dimension (default 2)\n"
                 "  --n N                   interior grid points per side (default 256)\n"
                 "  --tol T                 relative residual tolerance (default 1e-8)\n"
                 "  --maxit M               maximum CG iterations (default 10000)\n"
                 "  --decomp slab|cart      MPI decomposition (default cart)\n"
                 "  --halo block|overlap    halo exchange strategy (default block)\n"
                 "  --cg std|pipe           CG variant (default std)\n"
                 "  --repeat R              repeat solve R times, report fastest (default 1)\n"
                 "  --csv FILE              append result row to FILE\n"
                 "  --verbose               print residual history\n"
                 "  --help                  show this message\n",
                 prog);
}

static void fail(const char* prog, const std::string& msg) {
    std::fprintf(stderr, "error: %s\n", msg.c_str());
    print_usage(prog);
    std::exit(1);
}

Params parse_args(int argc, char** argv) {
    Params p;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) fail(argv[0], "missing value for " + a);
            return argv[++i];
        };
        if (a == "--help" || a == "-h") {
            print_usage(argv[0]);
            std::exit(0);
        } else if (a == "--dim") {
            p.dim = std::atoi(next().c_str());
        } else if (a == "--n") {
            p.n = std::atol(next().c_str());
        } else if (a == "--tol") {
            p.tol = std::atof(next().c_str());
        } else if (a == "--maxit") {
            p.maxit = std::atoi(next().c_str());
        } else if (a == "--decomp") {
            p.decomp = next();
        } else if (a == "--halo") {
            p.halo = next();
        } else if (a == "--cg") {
            p.cg = next();
        } else if (a == "--repeat") {
            p.repeat = std::atoi(next().c_str());
        } else if (a == "--csv") {
            p.csv = next();
        } else if (a == "--verbose") {
            p.verbose = true;
        } else {
            fail(argv[0], "unknown option " + a);
        }
    }
    if (p.dim != 2 && p.dim != 3) fail(argv[0], "--dim must be 2 or 3");
    if (p.n < 2) fail(argv[0], "--n must be >= 2");
    if (p.tol <= 0) fail(argv[0], "--tol must be > 0");
    if (p.maxit < 1) fail(argv[0], "--maxit must be >= 1");
    if (p.repeat < 1) fail(argv[0], "--repeat must be >= 1");
    if (p.decomp != "slab" && p.decomp != "cart") fail(argv[0], "--decomp must be slab|cart");
    if (p.halo != "block" && p.halo != "overlap") fail(argv[0], "--halo must be block|overlap");
    if (p.cg != "std" && p.cg != "pipe") fail(argv[0], "--cg must be std|pipe");
    return p;
}

} // namespace pcg
