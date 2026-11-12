#pragma once
#include "../hybrid_omp/local.hpp"
#include <algorithm>
#include <cuda_runtime.h>
#include <stdexcept>
namespace pcg {
namespace {
void check(cudaError_t code) {
    if (code != cudaSuccess)
        throw std::runtime_error(cudaGetErrorString(code));
}

struct Buffer {
    double* ptr = nullptr;
    explicit Buffer(std::size_t n) {
        check(cudaMalloc(&ptr, n * sizeof(double)));
    }
    ~Buffer() {
        cudaFree(ptr);
    }
    Buffer(const Buffer&) = delete;
};

constexpr int width = 256;
int blocks(std::size_t n) {
    return static_cast<int>(std::min<std::size_t>(1024, (n + width - 1) / width));
}
__device__ std::size_t index(Tile t, std::size_t i) {
    return ((i / t.nx / t.ny + 1) * (t.ny + 2) + i / t.nx % t.ny + 1) * (t.nx + 2) + i % t.nx + 1;
}

#define FOR_GRID(i, n)                                                                             \
    for (std::size_t i = blockIdx.x * blockDim.x + threadIdx.x; i < (n);                           \
         i += gridDim.x * blockDim.x)

__global__ void stencil(Tile t, int dim, std::size_t n, double scale, const double* p, double* ap) {
    const std::size_t sy = t.nx + 2, sz = sy * (t.ny + 2);
    FOR_GRID(i, n) {
        auto j = index(t, i);
        double v = 2 * dim * p[j] - p[j - 1] - p[j + 1] - p[j - sy] - p[j + sy];
        if (dim == 3)
            v -= p[j - sz] + p[j + sz];
        ap[i] = scale * v;
    }
}
__global__ void dot(Tile t, std::size_t n, const double* a, const double* b, bool padded,
                    double* parts) {
    __shared__ double sums[width];
    double value = 0;
    FOR_GRID(i, n) value += a[padded ? index(t, i) : i] * (b ? b[i] : 1.0);
    sums[threadIdx.x] = value;
    __syncthreads();
    for (int s = width / 2; s; s /= 2) {
        if (threadIdx.x < s)
            sums[threadIdx.x] += sums[threadIdx.x + s];
        __syncthreads();
    }
    if (!threadIdx.x)
        parts[blockIdx.x] = sums[0];
}
__global__ void update(Tile t, std::size_t n, double alpha, const double* p, const double* ap,
                       double* u, double* r) {
    FOR_GRID(i, n) {
        u[i] += alpha * p[index(t, i)];
        r[i] -= alpha * ap[i];
    }
}
__global__ void direction(Tile t, std::size_t n, double beta, const double* r, double* p) {
    FOR_GRID(i, n) {
        auto j = index(t, i);
        p[j] = r[i] + beta * p[j];
    }
}

// Logical face elements are ordered the same way on both neighbouring ranks.
__global__ void face_copy(Tile t, int axis, std::size_t count, std::size_t base, double* p,
                          double* packed, bool unpack) {
    const std::size_t sy = t.nx + 2, sz = sy * (t.ny + 2);
    FOR_GRID(i, count) {
        std::size_t offset;
        if (axis == 2)
            offset = (i / t.ny) * sz + (i % t.ny) * sy;
        else if (axis == 1)
            offset = (i / t.nx) * sz + i % t.nx;
        else
            offset = (i / t.nx) * sy + i % t.nx;
        if (unpack)
            p[base + offset] = packed[i];
        else
            packed[i] = p[base + offset];
    }
}
#undef FOR_GRID
} // namespace
} // namespace pcg
