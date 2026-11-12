// Serial matrix-free CG for the 2D/3D Poisson problem (owner: A).
//   build/bin/poisson_serial --dim 2 --n 512 [--cg std|pipe] [--csv out.csv]
#include "cg.hpp"
#include "params.hpp"
#include "serial_backend.hpp"

int main(int argc, char** argv) {
    pcg::Params p = pcg::parse_args(argc, argv);
    pcg::SerialBackend be(p.dim, p.n, p.cg);
    pcg::run_solver(be, p);
    return 0;
}
