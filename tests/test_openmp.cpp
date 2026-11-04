#include "kernel_openmp.hpp"
#include <omp.h>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>
using namespace poisson;
namespace {
void require(bool b,const char* message) { if(!b) throw std::runtime_error(message); }
void near(double a,double b) { require(std::abs(a-b)<=1e-12*(1+std::abs(b)),"numerical mismatch"); }
template<class F> void rejects(F f) {
    bool caught=false; try{f();}catch(const std::invalid_argument&){caught=true;}
    require(caught,"invalid contract accepted");
}
}
int main() {
    try {
        omp_set_dynamic(0);
        for(int threads:{1,2,4}) {
            omp_set_num_threads(threads);
            require(openmp_team_size()==threads,"requested real team unavailable");
            for(std::size_t rows:{1u,2u,4u,7u}) {
                const std::size_t offset=7-rows;
                Grid old(7,rows,offset),rhs(7,rows,offset),a(7,rows,offset),b(7,rows,offset);
                for(std::size_t i=0;i<rows+2;++i) for(std::size_t j=0;j<9;++j) {
                    old(i,j)=(2*i*i+3*j+i*j+1)/73.0;
                    rhs(i,j)=(i+2*j*j+offset)/17.0;
                }
                for(std::size_t begin:{1u,static_cast<unsigned>(rows+1)}) {
                    for(std::size_t end:{static_cast<unsigned>(begin),static_cast<unsigned>(rows+1)}) {
                        std::fill(a.values.begin(),a.values.end(),987.0); b.values=a.values;
                        const auto old_copy=old.values,rhs_copy=rhs.values;
                        jacobi_rows(old,a,rhs,begin,end); jacobi_rows_openmp(old,b,rhs,begin,end);
                        for(std::size_t k=0;k<a.values.size();++k) near(b.values[k],a.values[k]);
                        require(old.values==old_copy && rhs.values==rhs_copy,"input modified");
                        near(residual_squared_rows_openmp(old,rhs,begin,end),residual_squared_rows(old,rhs,begin,end));
                        near(squared_norm_rows_openmp(rhs,begin,end),squared_norm_rows(rhs,begin,end));
                    }
                }
                // Partitioned calls must cover each row once; narrow slabs included.
                std::fill(a.values.begin(),a.values.end(),0); b.values=a.values;
                jacobi_rows(old,a,rhs,1,rows+1);
                jacobi_rows_openmp(old,b,rhs,1,2);
                jacobi_rows_openmp(old,b,rhs,2,rows+1);
                for(std::size_t k=0;k<a.values.size();++k) near(b.values[k],a.values[k]);
                rejects([&]{jacobi_rows_openmp(old,old,rhs,1,rows+1);});
                rejects([&]{jacobi_rows_openmp(old,rhs,rhs,1,rows+1);});
                rejects([&]{jacobi_rows_openmp(old,b,rhs,0,rows+1);});
                rejects([&]{residual_squared_rows_openmp(old,rhs,1,rows+2);});
                Grid wrong(8,1);
                rejects([&]{residual_squared_rows_openmp(old,wrong,1,rows+1);});
            }
            std::cout<<"PASS actual_threads="<<threads<<"; asymmetric/slab/empty/split/sentinel/contract tests\n";
        }
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
