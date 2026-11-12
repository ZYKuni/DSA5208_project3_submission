// Serial matrix-free CG backend (owner: A). Reference implementation for all validation.
#pragma once

#include "cg.hpp"
#include "grid.hpp"

namespace pcg {

class SerialBackend : public Backend {
  public:
    SerialBackend(int dim, long n, const std::string& cg_variant);

    double* alloc() override;
    void release(double* v) override;
    void rhs(double* b) override;
    double error_l2(const double* x) override;
    void apply(double* in, double* out) override;
    double dot(const double* x, const double* y) override;
    void dot2(const double* a, const double* b, const double* c, const double* d,
              double out[2]) override;
    void axpy(double* y, double alpha, const double* x) override;
    void xpay(double* y, double beta, const double* x) override;
    void copy(double* dst, const double* src) override;
    void zero(double* v) override;
    Result describe() const override;

    const Block& block() const {
        return blk_;
    }

  private:
    Block blk_;
    std::string cg_;
};

} // namespace pcg
