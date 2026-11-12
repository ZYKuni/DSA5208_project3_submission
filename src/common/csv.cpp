#include "csv.hpp"

#include <cstdio>
#include <fstream>
#include <sstream>

namespace pcg {

const char* csv_header() {
    return "impl,dim,n,ranks,threads,gpus,decomp,halo,cg,iters,"
           "t_total,t_stencil,t_halo,t_reduce,rel_res,err_l2";
}

std::string csv_row(const Result& r) {
    char buf[512];
    std::snprintf(buf, sizeof(buf), "%s,%d,%ld,%d,%d,%d,%s,%s,%s,%d,%.6e,%.6e,%.6e,%.6e,%.6e,%.6e",
                  r.impl.c_str(), r.dim, r.n, r.ranks, r.threads, r.gpus, r.decomp.c_str(),
                  r.halo.c_str(), r.cg.c_str(), r.iters, r.t_total, r.t_stencil, r.t_halo,
                  r.t_reduce, r.rel_res, r.err_l2);
    return buf;
}

void csv_append(const std::string& path, const Result& r) {
    bool need_header = true;
    {
        std::ifstream in(path);
        if (in.good() && in.peek() != std::ifstream::traits_type::eof()) need_header = false;
    }
    std::ofstream out(path, std::ios::app);
    if (!out) {
        std::fprintf(stderr, "warning: cannot open %s for writing\n", path.c_str());
        return;
    }
    if (need_header) out << csv_header() << '\n';
    out << csv_row(r) << '\n';
}

} // namespace pcg
