#pragma once
#include "grid.hpp"
#include <string>
namespace poisson {
struct CliOptions {
    Config config;
    std::string solution_path;
    std::string communication = "sendrecv";
    std::string kernel = "serial";
    bool help = false;
};
CliOptions parse_cli(int argc, char** argv, bool mpi = false, bool openmp = false);
void write_solution(const std::string& path, const Grid& u);
void print_result(const Config& c, const SolveResult& r, const char* variant,
                  int ranks = 1, int threads = 1, const char* communication = "none",
                  const char* kernel = "serial", const char* driver = "serial",
                  int mpi_thread_provided = 0, int openmp_version = 0);
}
