// MPI + OpenMP backend: MpiBackend with threaded compute kernels.
// Decomposition, halo exchange (block|overlap), reductions and the CG variants (std|pipe) are
// inherited unchanged. MPI is called only by the master thread, outside parallel regions
// (MPI_THREAD_FUNNELED).
#pragma once

#include "mpi_backend.hpp"

namespace pcg {

class OmpBackend : public MpiBackend {
  public:
    OmpBackend(MPI_Comm comm, const Params& p);

    void axpy(double* y, double alpha, const double* x) override;
    void xpay(double* y, double beta, const double* x) override;
    void copy(double* dst, const double* src) override;
    void zero(double* v) override;
    Result describe() const override;

  protected:
    void stencil(const double* in, double* out, const Range& r) override;
    double local_dot_hook(const double* x, const double* y) override;
    void local_dot2_hook(const double* a, const double* b, const double* c, const double* d,
                         double out[2]) override;

  private:
    int threads_ = 1;
};

} // namespace pcg
