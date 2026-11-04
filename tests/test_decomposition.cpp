#include "decomposition.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>

int main() {
    try {
        for (std::size_t n = 1; n <= 129; ++n) {
            for (int p = 1; p <= static_cast<int>(n); ++p) {
                std::size_t next = 0, min_rows = n, max_rows = 0;
                for (int r = 0; r < p; ++r) {
                    const auto s = poisson::decompose(n, p, r);
                    if (s.rows == 0 || s.offset != next) throw std::runtime_error("gap/overlap/empty slab");
                    next += s.rows;
                    min_rows = std::min(min_rows, s.rows);
                    max_rows = std::max(max_rows, s.rows);
                }
                if (next != n || max_rows - min_rows > 1) throw std::runtime_error("coverage/balance failure");
            }
        }
        const int cases[][3] = {{0,1,0}, {1,2,0}, {7,0,0}, {7,3,-1}, {7,3,3}};
        for (const auto& c : cases) {
            bool rejected = false;
            try { poisson::decompose(c[0], c[1], c[2]); }
            catch (const std::invalid_argument&) { rejected = true; }
            if (!rejected) throw std::runtime_error("invalid input accepted");
        }
        std::cout << "decomposition coverage, balance and rejection checks passed\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
