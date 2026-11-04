#include "decomposition.hpp"
#include <algorithm>
#include <stdexcept>

namespace poisson {
Slab decompose(std::size_t n, int ranks, int rank) {
    if (ranks < 1 || rank < 0 || rank >= ranks || n < static_cast<std::size_t>(ranks))
        throw std::invalid_argument("require 1 <= ranks <= n and a valid rank");
    const auto p = static_cast<std::size_t>(ranks);
    const auto r = static_cast<std::size_t>(rank);
    return {n / p + (r < n % p ? 1 : 0), r * (n / p) + std::min(r, n % p)};
}
} // namespace poisson
