// Tile layout used by the MPI+CUDA solver (src/hybrid_cuda).
#pragma once
#include <cstddef>

namespace pcg {
struct Tile {
    int nx, ny, nz; // 2D: nz = 1. Fastest index is x.
    std::size_t size() const {
        return std::size_t(nx) * ny * nz;
    }
    std::size_t ghost(std::size_t i) const {
        return ((i / nx / ny + 1) * (ny + 2) + i / nx % ny + 1) * (nx + 2) + i % nx + 1;
    }
};

} // namespace pcg
