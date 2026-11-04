#pragma once
#include <cstddef>

namespace poisson {
struct Slab { std::size_t rows, offset; };
Slab decompose(std::size_t n, int ranks, int rank);
} // namespace poisson
