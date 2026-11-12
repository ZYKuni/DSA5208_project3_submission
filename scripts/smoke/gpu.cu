#include <cstdlib>
#include <cuda_runtime.h>
#include <iostream>
#include <mpi.h>
#include <vector>

static void check(cudaError_t code) {
    if (code != cudaSuccess) {
        std::cerr << cudaGetErrorString(code) << '\n';
        MPI_Abort(MPI_COMM_WORLD, 2);
    }
}
__global__ void fill(double* values, int n, int rank) {
    const int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n)
        values[i] = i + rank;
}
int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank, ranks, local_rank, count;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &ranks);
    MPI_Comm node;
    MPI_Comm_split_type(MPI_COMM_WORLD, MPI_COMM_TYPE_SHARED, rank, MPI_INFO_NULL, &node);
    MPI_Comm_rank(node, &local_rank);
    check(cudaGetDeviceCount(&count));
    const char* expected_count = std::getenv("PCG_EXPECT_GPU_COUNT");
    if (expected_count && count != std::atoi(expected_count)) {
        std::cerr << "GPU allocation mismatch: rank=" << rank << " visible=" << count << '\n';
        MPI_Abort(MPI_COMM_WORLD, 2);
    }
    if (count == 0 || (count > 1 && local_rank >= count))
        MPI_Abort(MPI_COMM_WORLD, 2);
    check(cudaSetDevice(count == 1 ? 0 : local_rank));
    cudaDeviceProp prop;
    check(cudaGetDeviceProperties(&prop, count == 1 ? 0 : local_rank));
    constexpr int n = 1024;
    double* device;
    check(cudaMalloc(reinterpret_cast<void**>(&device), n * sizeof(double)));
    fill<<<4, 256>>>(device, n, rank);
    check(cudaGetLastError());
    check(cudaDeviceSynchronize());
    std::vector<double> host(n);
    check(cudaMemcpy(host.data(), device, n * sizeof(double), cudaMemcpyDeviceToHost));
    int failed = 0;
    for (int i = 0; i < n; ++i)
        failed |= host[i] != i + rank;
    // Optional two-rank device-pointer transfer; only enable on verified CUDA-aware MPI.
    const bool direct = std::getenv("PCG_SMOKE_DEVICE_MPI") != nullptr;
    if (direct) {
        if (ranks != 2)
            MPI_Abort(MPI_COMM_WORLD, 2);
        MPI_Sendrecv_replace(device, n, MPI_DOUBLE, 1 - rank, 7, 1 - rank, 7, MPI_COMM_WORLD,
                             MPI_STATUS_IGNORE);
        check(cudaMemcpy(host.data(), device, n * sizeof(double), cudaMemcpyDeviceToHost));
        for (int i = 0; i < n; ++i)
            failed |= host[i] != i + 1 - rank;
    }
    std::cout << "rank=" << rank << " visible_gpus=" << count << " gpu=" << prop.name
              << " cc=" << prop.major << prop.minor << " device_mpi=" << direct << '\n';
    int any_failed;
    MPI_Allreduce(&failed, &any_failed, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
    if (!rank)
        std::cout << "GPU_SMOKE=" << (any_failed ? "FAIL" : "PASS") << '\n';
    check(cudaFree(device));
    MPI_Comm_free(&node);
    MPI_Finalize();
    return any_failed;
}
