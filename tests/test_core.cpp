#include "solver.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

namespace {
void require(bool ok, const char* message) {
    if (!ok) throw std::runtime_error(message);
}
void near(double actual, double expected, double tol, const char* message) {
    require(std::isfinite(actual) && std::abs(actual - expected) <= tol, message);
}
template<class F> void rejects(F action) {
    bool thrown = false;
    try { action(); } catch (const std::exception&) { thrown = true; }
    require(thrown, "invalid contract was accepted");
}
}
int main() {
    try {
        using namespace poisson;
        // Hand-solvable 2x2 interior with f=4, zero initial and boundary values.
        Grid old(2, 2), next(2, 2), rhs(2, 2);
        for (std::size_t i=1; i<=2; ++i)
            for (std::size_t j=1; j<=2; ++j) rhs(i,j)=4;
        jacobi_rows(old, next, rhs, 1, 3);
        for (std::size_t i=1; i<=2; ++i)
            for (std::size_t j=1; j<=2; ++j) near(next(i,j), 1.0/9, 1e-15, "first hand step");
        old.values.swap(next.values);
        jacobi_rows(old, next, rhs, 1, 3);
        for (std::size_t i=1; i<=2; ++i)
            for (std::size_t j=1; j<=2; ++j) near(next(i,j), 1.0/6, 1e-15, "second hand step");
        near(std::sqrt(residual_squared_rows(next, rhs, 1, 3)), 2, 1e-14, "hand residual");
        for (std::size_t j=0; j<4; ++j) {
            near(next(0,j),0,0,"top boundary"); near(next(3,j),0,0,"bottom boundary");
            near(next(j,0),0,0,"left boundary"); near(next(j,3),0,0,"right boundary");
        }
        rejects([&]{ jacobi_rows(old, old, rhs, 1, 3); });
        rejects([&]{ jacobi_rows(old, rhs, rhs, 1, 3); });
        rejects([&]{ jacobi_rows(old, next, rhs, 0, 3); });
        rejects([&]{ residual_squared_rows(old, rhs, 2, 4); });
        rejects([]{ Grid bad(7,0); });
        rejects([]{ Grid bad(7,2,6); });
        rejects([]{ Grid bad(static_cast<std::size_t>(-1),1); });
        Grid different(3,3);
        rejects([&]{ jacobi_rows(old,next,different,1,3); });

        // Arbitrary, asymmetric values expose row/column and offset mistakes.
        Grid global(7,7), output(7,7), forcing(7,7);
        for (std::size_t i=1; i<=7; ++i)
            for (std::size_t j=1; j<=7; ++j) {
                global(i,j) = static_cast<double>(i*i + 3*j + i*j) / 100;
                forcing(i,j) = static_cast<double>(2*i + j*j);
            }
        jacobi_rows(global,output,forcing,1,8);
        // Emulate a one-row slab, two-row slab and remainder slab, without MPI.
        double slab_residual = 0;
        std::size_t offset = 0;
        for (std::size_t count : {1u,2u,4u}) {
            Grid slab(7,count,offset), local_next(7,count,offset), local_rhs(7,count,offset);
            for (std::size_t i=0; i<=count+1; ++i)
                for (std::size_t j=0; j<=8; ++j) slab(i,j)=global(offset+i,j);
            for (std::size_t i=1; i<=count; ++i)
                for (std::size_t j=1; j<=7; ++j) local_rhs(i,j)=forcing(offset+i,j);
            // Split rows as the overlap driver would; empty ranges are valid.
            jacobi_rows(slab,local_next,local_rhs,1,2);
            jacobi_rows(slab,local_next,local_rhs,2,count+1);
            for (std::size_t i=1; i<=count; ++i)
                for (std::size_t j=1; j<=7; ++j)
                    near(local_next(i,j),output(offset+i,j),1e-15,"slab result mismatch");
            slab_residual += residual_squared_rows(slab,local_rhs,1,count+1);
            Grid sine_rhs(7,count,offset), whole_rhs(7,7);
            for (Problem problem : {Problem::DiscreteSine, Problem::DiscreteMixed}) {
                initialize_rhs(sine_rhs,problem);
                initialize_rhs(whole_rhs,problem);
                for (std::size_t i=1; i<=count; ++i)
                    for (std::size_t j=1; j<=7; ++j)
                        near(sine_rhs(i,j),whole_rhs(offset+i,j),0,"global coordinate mismatch");
            }
            offset += count;
        }
        const double global_residual = residual_squared_rows(global,forcing,1,8);
        near(slab_residual,global_residual,global_residual*1e-14,"sum local squared residuals");
        // Independent manufactured discrete solution residual.
        initialize_rhs(forcing,Problem::DiscreteSine);
        for (std::size_t i=0; i<=8; ++i)
            for (std::size_t j=0; j<=8; ++j)
                global(i,j)=exact_value(i,j,7,Problem::DiscreteSine);
        require(std::sqrt(residual_squared_rows(global,forcing,1,8)) < 1e-11,"exact discrete residual");
        initialize_rhs(forcing,Problem::DiscreteMixed);
        for (std::size_t i=0; i<=8; ++i)
            for (std::size_t j=0; j<=8; ++j)
                global(i,j)=exact_value(i,j,7,Problem::DiscreteMixed);
        require(std::sqrt(residual_squared_rows(global,forcing,1,8)) < 1e-11,"mixed exact residual");
        require(std::abs(global(2,3)-global(3,2)) > 0.1,"mixed field must distinguish transpose");
        std::cout << "PASS: hand steps, boundaries, alias/range checks, uneven slabs, analytic residual\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL: " << e.what() << '\n';
        return 1;
    }
}
