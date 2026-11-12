#include "params.hpp"
namespace pcg {
int cuda_main(const Params& p, int argc, char** argv);
}
int main(int argc, char** argv) {
    return pcg::cuda_main(pcg::parse_args(argc, argv), argc, argv);
}
