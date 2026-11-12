// Phase timer: every implementation accumulates time in the SAME three phases so
// that the communication analysis in the report compares like with like.
//   stencil : applying the Laplacian (matrix-vector product) and vector updates
//   halo    : exchanging ghost layers with neighbours (0 for serial)
//   reduce  : global dot products / MPI_Allreduce (local sum only for serial)
#pragma once

#include <chrono>

namespace pcg {

enum class Phase { Stencil = 0, Halo = 1, Reduce = 2 };

class PhaseTimer {
  public:
    static double now() {
        using clock = std::chrono::steady_clock;
        return std::chrono::duration<double>(clock::now().time_since_epoch()).count();
    }
    void start(Phase p) { t0_[idx(p)] = now(); }
    void stop(Phase p) { acc_[idx(p)] += now() - t0_[idx(p)]; }
    double get(Phase p) const { return acc_[idx(p)]; }
    void reset() { acc_[0] = acc_[1] = acc_[2] = 0.0; }

  private:
    static int idx(Phase p) { return static_cast<int>(p); }
    double t0_[3] = {0.0, 0.0, 0.0};
    double acc_[3] = {0.0, 0.0, 0.0};
};

} // namespace pcg
