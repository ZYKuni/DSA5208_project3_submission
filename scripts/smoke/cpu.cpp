#include <mpi.h>
#include <omp.h>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <set>
#include <string>
#include <vector>
#ifdef __linux__
#include <sched.h>
#endif

int main(int argc, char** argv) {
    int provided, rank, ranks;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &ranks);
    if (provided < MPI_THREAD_FUNNELED) MPI_Abort(MPI_COMM_WORLD, 2);
    const int expected_nodes = argc > 1 ? std::atoi(argv[1]) : 1;
    const int expected_threads = argc > 2 ? std::atoi(argv[2]) : 2;
    int threads = 0;
    long long sum = 0;
    std::vector<int> cpus(omp_get_max_threads(), -1);
#pragma omp parallel reduction(+:sum)
    {
#pragma omp single
        threads = omp_get_num_threads();
#ifdef __linux__
        cpus[omp_get_thread_num()] = sched_getcpu();
#endif
#pragma omp for schedule(static)
        for (int i = 0; i < 10000; ++i) sum += i + rank;
    }
    int failed = threads != expected_threads;
#ifdef __linux__
    std::set<int> distinct(cpus.begin(), cpus.begin() + threads);
    failed |= int(distinct.size()) != threads || distinct.count(-1);
#endif
    long long total;
    MPI_Allreduce(&sum, &total, 1, MPI_LONG_LONG_INT, MPI_SUM, MPI_COMM_WORLD);
    failed |= total != 49995000LL * ranks + 10000LL * ranks * (ranks - 1) / 2;
    char host[MPI_MAX_PROCESSOR_NAME]{};
    int length;
    MPI_Get_processor_name(host, &length);
    std::vector<char> hosts(ranks * MPI_MAX_PROCESSOR_NAME);
    MPI_Gather(host, MPI_MAX_PROCESSOR_NAME, MPI_CHAR, hosts.data(),
               MPI_MAX_PROCESSOR_NAME, MPI_CHAR, 0, MPI_COMM_WORLD);
    int nodes = 0;
    if (rank == 0) {
        std::set<std::string> unique;
        for (int r = 0; r < ranks; ++r) unique.insert(&hosts[r * MPI_MAX_PROCESSOR_NAME]);
        nodes = unique.size();
        failed |= nodes != expected_nodes;
        for (const auto& h : unique) std::cout << "host=" << h << '\n';
    }
    int any_failed;
    MPI_Allreduce(&failed, &any_failed, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
    if (!rank) std::cout << "CPU_SMOKE=" << (any_failed ? "FAIL" : "PASS")
                         << " ranks=" << ranks << " nodes=" << nodes
                         << " threads_per_rank=" << threads << " global_sum=" << total << '\n';
    MPI_Finalize();
    return any_failed;
}
