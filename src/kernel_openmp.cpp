#include "kernel_openmp.hpp"
#include <omp.h>
#include <stdexcept>

namespace poisson {
namespace {
void range(const Grid& g, std::size_t b, std::size_t e) {
    if (b < 1 || b > e || e > g.rows + 1)
        throw std::invalid_argument("row range must lie within [1, rows+1)");
}
void pair(const Grid& a, const Grid& b) {
    if (!same_layout(a,b)) throw std::invalid_argument("incompatible grid layouts");
}
}
int openmp_team_size() {
    int count=1;
    #pragma omp parallel default(none) shared(count)
    {
        #pragma omp single
        count=omp_get_num_threads();
    }
    return count;
}
void jacobi_rows_openmp(const Grid& old, Grid& next, const Grid& rhs,
                       std::size_t begin, std::size_t end) {
    range(old,begin,end); pair(old,next); pair(old,rhs);
    if (&old==&next || &rhs==&next)
        throw std::invalid_argument("Jacobi output must not alias its inputs");
    const double h=1.0/(static_cast<double>(old.n)+1.0), h2=h*h;
    #pragma omp parallel for schedule(static) default(none) shared(old,next,rhs) firstprivate(begin,end,h2)
    for (std::size_t i=begin;i<end;++i)
        for (std::size_t j=1;j<=old.n;++j)
            next(i,j)=0.25*(old(i-1,j)+old(i+1,j)+old(i,j-1)+old(i,j+1)+h2*rhs(i,j));
}
double residual_squared_rows_openmp(const Grid& u,const Grid& rhs,
                                   std::size_t begin,std::size_t end) {
    range(u,begin,end); pair(u,rhs);
    const double inv_h=static_cast<double>(u.n)+1.0, scale=inv_h*inv_h;
    double sum=0;
    #pragma omp parallel for schedule(static) reduction(+:sum) default(none) shared(u,rhs) firstprivate(begin,end,scale)
    for (std::size_t i=begin;i<end;++i)
        for (std::size_t j=1;j<=u.n;++j) {
            const double au=(4.0*u(i,j)-u(i-1,j)-u(i+1,j)-u(i,j-1)-u(i,j+1))*scale;
            const double r=rhs(i,j)-au;
            sum+=r*r;
        }
    return sum;
}
double squared_norm_rows_openmp(const Grid& g,std::size_t begin,std::size_t end) {
    range(g,begin,end);
    double sum=0;
    #pragma omp parallel for schedule(static) reduction(+:sum) default(none) shared(g) firstprivate(begin,end)
    for (std::size_t i=begin;i<end;++i)
        for (std::size_t j=1;j<=g.n;++j) sum+=g(i,j)*g(i,j);
    return sum;
}
}
