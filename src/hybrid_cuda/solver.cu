#include "../hybrid_omp/domain.hpp"
#include "csv.hpp"
#include "kernels.cuh"
#include "params.hpp"
#include "problem.hpp"
#include "timer.hpp"
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <cuda_runtime.h>
#include <iostream>
#include <vector>

namespace pcg {
namespace {
struct Halo {
    Buffer send, recv;
    std::vector<double> hs, hr;
    bool direct;
    Halo(std::size_t n, bool device)
        : send(n), recv(n), hs(device ? 0 : n), hr(device ? 0 : n), direct(device) {}
    void exchange(const Domain& d, double* p) {
        const auto t = d.tile;
        const int lengths[]{t.nz, t.ny, t.nx};
        for (int a = 0; a < d.dim; ++a) {
            const int axis = 3 - d.dim + a;
            const auto count = t.size() / lengths[axis];
            if (count > INT_MAX)
                throw std::runtime_error("MPI face exceeds count range");
            for (int side = 0; side < 2; ++side) {
                int dest = side ? d.hi[a] : d.lo[a], src = side ? d.lo[a] : d.hi[a];
                if (dest == MPI_PROC_NULL && src == MPI_PROC_NULL)
                    continue;
                if (dest != MPI_PROC_NULL) {
                    face_copy<<<blocks(count), width>>>(
                        t, axis, count, side ? d.high_send[a] : d.low_send[a], p, send.ptr, false);
                    check(cudaDeviceSynchronize());
                    if (!direct)
                        check(cudaMemcpy(hs.data(), send.ptr, count * sizeof(double),
                                         cudaMemcpyDeviceToHost));
                }
                MPI_Sendrecv(direct ? send.ptr : hs.data(), count, MPI_DOUBLE, dest, side,
                             direct ? recv.ptr : hr.data(), count, MPI_DOUBLE, src, side, d.comm,
                             MPI_STATUS_IGNORE);
                if (src != MPI_PROC_NULL) {
                    if (!direct)
                        check(cudaMemcpy(recv.ptr, hr.data(), count * sizeof(double),
                                         cudaMemcpyHostToDevice));
                    face_copy<<<blocks(count), width>>>(
                        t, axis, count, side ? d.low_recv[a] : d.high_recv[a], p, recv.ptr, true);
                    check(cudaDeviceSynchronize());
                }
            }
        }
    }
};

Result run(const Params& p, const Domain& d, bool direct, int rank, double stop_tol) {
    const auto t = d.tile;
    const auto n = t.size(), padded = std::size_t(t.nz + 2) * (t.ny + 2) * (t.nx + 2);
    const double h = grid_h(p.n);
    const int nb = blocks(n);
    Buffer u(n), r(n), ap(n), dir(padded), parts(nb), scalar(1);
    Halo halo(std::max({n / t.nx, n / t.ny, p.dim == 3 ? n / t.nz : std::size_t(0)}), direct);
    std::vector<double> host(n), exact(n);
    for (std::size_t i = 0; i < n; ++i) {
        double x = (d.origin[2] + i % t.nx + 1) * h, y = (d.origin[1] + i / t.nx % t.ny + 1) * h,
               z = (d.origin[0] + i / t.nx / t.ny + 1) * h;
        exact[i] = exact_u(p.dim, x, y, z);
        host[i] = rhs_f(p.dim, x, y, z);
    }
    check(cudaMemset(u.ptr, 0, n * sizeof(double)));
    check(cudaMemset(dir.ptr, 0, padded * sizeof(double)));
    check(cudaMemcpy(r.ptr, host.data(), n * sizeof(double), cudaMemcpyHostToDevice));
    direction<<<nb, width>>>(t, n, 0, r.ptr, dir.ptr);
    auto global_dot = [&](double* a, double* b, bool ghost) {
        dot<<<nb, width>>>(t, n, a, b, ghost, parts.ptr);
        dot<<<1, width>>>(t, nb, parts.ptr, nullptr, false, scalar.ptr); // sum the block partials
        double local, total;
        check(cudaMemcpy(&local, scalar.ptr, sizeof(double), cudaMemcpyDeviceToHost));
        MPI_Allreduce(&local, &total, 1, MPI_DOUBLE, MPI_SUM, d.comm);
        return total;
    };
    double initial = global_dot(r.ptr, r.ptr, false), rho = initial;
    PhaseTimer timer;
    Result row;
    check(cudaDeviceSynchronize());
    MPI_Barrier(d.comm);
    double start = MPI_Wtime();
    while (row.iters < p.maxit && std::sqrt(rho / initial) >= stop_tol) {
        timer.start(Phase::Halo);
        halo.exchange(d, dir.ptr);
        timer.stop(Phase::Halo);
        timer.start(Phase::Stencil);
        stencil<<<nb, width>>>(t, p.dim, n, 1 / (h * h), dir.ptr, ap.ptr);
        check(cudaDeviceSynchronize());
        timer.stop(Phase::Stencil);
        timer.start(Phase::Reduce);
        double alpha = rho / global_dot(dir.ptr, ap.ptr, true);
        timer.stop(Phase::Reduce);
        timer.start(Phase::Stencil);
        update<<<nb, width>>>(t, n, alpha, dir.ptr, ap.ptr, u.ptr, r.ptr);
        check(cudaDeviceSynchronize());
        timer.stop(Phase::Stencil);
        timer.start(Phase::Reduce);
        double next = global_dot(r.ptr, r.ptr, false);
        timer.stop(Phase::Reduce);
        timer.start(Phase::Stencil);
        direction<<<nb, width>>>(t, n, next / rho, r.ptr, dir.ptr);
        check(cudaDeviceSynchronize());
        timer.stop(Phase::Stencil);
        rho = next;
        ++row.iters;
        if (rank == 0 && p.verbose)
            std::cerr << row.iters << " " << std::sqrt(rho / initial) << "\n";
    }
    check(cudaDeviceSynchronize());
    MPI_Barrier(d.comm);
    double times[]{MPI_Wtime() - start, timer.get(Phase::Stencil), timer.get(Phase::Halo),
                   timer.get(Phase::Reduce)};
    double maxima[4];
    MPI_Allreduce(times, maxima, 4, MPI_DOUBLE, MPI_MAX, d.comm);
    check(cudaMemcpy(host.data(), u.ptr, n * sizeof(double), cudaMemcpyDeviceToHost));
    double local = 0, err;
    for (std::size_t i = 0; i < n; ++i)
        local += (host[i] - exact[i]) * (host[i] - exact[i]);
    MPI_Allreduce(&local, &err, 1, MPI_DOUBLE, MPI_SUM, d.comm);
    // Recompute the true residual outside the timed solve, as the CPU driver does.
    // Reuse the ghosted search-direction buffer for x, then apply A to it.
    direction<<<nb, width>>>(t, n, 0, u.ptr, dir.ptr);
    check(cudaDeviceSynchronize());
    halo.exchange(d, dir.ptr);
    stencil<<<nb, width>>>(t, p.dim, n, 1 / (h * h), dir.ptr, ap.ptr);
    check(cudaMemcpy(host.data(), ap.ptr, n * sizeof(double), cudaMemcpyDeviceToHost));
    local = 0;
    for (std::size_t i = 0; i < n; ++i) {
        const double x = (d.origin[2] + i % t.nx + 1) * h;
        const double y = (d.origin[1] + i / t.nx % t.ny + 1) * h;
        const double z = (d.origin[0] + i / t.nx / t.ny + 1) * h;
        const double residual = rhs_f(p.dim, x, y, z) - host[i];
        local += residual * residual;
    }
    double residual_sq;
    MPI_Allreduce(&local, &residual_sq, 1, MPI_DOUBLE, MPI_SUM, d.comm);
    MPI_Comm_size(d.comm, &row.ranks);
    row.gpus = row.ranks;
    row.impl = "cuda";
    row.dim = p.dim;
    row.n = p.n;
    row.decomp = p.decomp;
    row.halo = p.halo;
    row.cg = p.cg;
    row.t_total = maxima[0];
    row.t_stencil = maxima[1];
    row.t_halo = maxima[2];
    row.t_reduce = maxima[3];
    row.rel_res = std::sqrt(residual_sq / initial);
    row.err_l2 = std::sqrt(err * std::pow(h, p.dim));
    return row;
}
} // namespace

int cuda_main(const Params& p, int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank, status = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    try {
        // --tol remains the true-residual acceptance threshold. A tighter
        // recursive stopping target can leave room for accumulated roundoff.
        double stop_tol = p.tol;
        if (const char* text = std::getenv("PCG_CUDA_STOP_TOL")) {
            char* end;
            stop_tol = std::strtod(text, &end);
            if (end == text || *end || !std::isfinite(stop_tol) || stop_tol <= 0 ||
                stop_tol > p.tol)
                throw std::runtime_error("PCG_CUDA_STOP_TOL must be finite, positive and <= --tol");
        }
        const char* env = std::getenv("PCG_CUDA_HALO");
        std::string mode = env ? env : "staged";
        if ((mode != "device" && mode != "staged") || p.cg != "std" || p.halo != "block")
            throw std::runtime_error("use --cg std --halo block and PCG_CUDA_HALO=staged|device");
        MPI_Comm node;
        MPI_Comm_split_type(MPI_COMM_WORLD, MPI_COMM_TYPE_SHARED, rank, MPI_INFO_NULL, &node);
        int local, count;
        MPI_Comm_rank(node, &local);
        check(cudaGetDeviceCount(&count));
        // Schedulers may expose a single assigned device per process.
        int device = count == 1 ? 0 : local;
        if (device >= count)
            throw std::runtime_error("no GPU for this local rank");
        check(cudaSetDevice(device));
        cudaDeviceProp prop;
        check(cudaGetDeviceProperties(&prop, device));
        auto uuid = prop.uuid;
        int peers;
        MPI_Comm_size(node, &peers);
        std::vector<cudaUUID_t> ids(peers);
        MPI_Allgather(&uuid, sizeof(uuid), MPI_BYTE, ids.data(), sizeof(uuid), MPI_BYTE, node);
        for (int i = 0; i < local; ++i)
            if (std::memcmp(&ids[i], &uuid, sizeof(uuid)) == 0)
                throw std::runtime_error("two ranks assigned the same GPU");
        MPI_Comm_free(&node);
        Domain d(p.n, p.dim, p.decomp == "slab");
        Result best;
        for (int i = 0; i < p.repeat; ++i) {
            auto row = run(p, d, mode == "device", rank, stop_tol);
            if (!i || row.t_total < best.t_total)
                best = row;
        }
        if (!rank) {
            std::cout << csv_header() << "\n" << csv_row(best) << "\n";
            if (!p.csv.empty())
                csv_append(p.csv, best);
        }
        status = !(best.rel_res < p.tol);
    } catch (const std::exception& e) {
        std::cerr << "rank " << rank << ": " << e.what() << "\n";
        MPI_Abort(MPI_COMM_WORLD, 1);
    }
    MPI_Finalize();
    return status;
}
} // namespace pcg
