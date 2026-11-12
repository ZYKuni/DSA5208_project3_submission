// Unified result format. One run = one CSV row. analysis/collect.py relies on these
// exact column names, so do not reorder or rename them without updating the scripts.
#pragma once

#include <string>

namespace pcg {

struct Result {
    std::string impl;     // serial | mpi | omp | cuda
    int dim = 2;
    long n = 0;           // interior points per side (global)
    int ranks = 1;        // MPI ranks
    int threads = 1;      // OpenMP threads per rank
    int gpus = 0;         // GPUs used in total
    std::string decomp;   // slab | cart | none
    std::string halo;     // block | overlap | none
    std::string cg;       // std | pipe
    int iters = 0;
    double t_total = 0;   // seconds, solve only (exclude setup and I/O); max over ranks
    double t_stencil = 0; // seconds, max over ranks
    double t_halo = 0;    // seconds, max over ranks
    double t_reduce = 0;  // seconds, max over ranks
    double rel_res = 0;   // final ||r|| / ||b||
    double err_l2 = 0;    // discrete L2 error against the manufactured solution
};

// Header line, matching the fields of Result in order.
const char* csv_header();

// Formats r as one CSV line (no trailing newline).
std::string csv_row(const Result& r);

// Appends r to path, writing the header first if the file is new or empty.
// Call from ONE process only (rank 0).
void csv_append(const std::string& path, const Result& r);

} // namespace pcg
