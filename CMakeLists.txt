cmake_minimum_required(VERSION 3.18)
project(poisson_cg LANGUAGES CXX)

# ---------------------------------------------------------------------------
# Options (same names on laptop, Atlas and Vanda)
# ---------------------------------------------------------------------------
option(ENABLE_MPI    "Build MPI and hybrid executables" ON)
option(ENABLE_OPENMP "Build MPI+OpenMP executable"      ON)
option(ENABLE_CUDA   "Build MPI+CUDA executable"        OFF)
option(BUILD_TESTS   "Build validation tests"           ON)
option(BUILD_CLUSTER_SMOKE "Build standalone cluster probes" OFF)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# No BLAS / LAPACK anywhere in this project (course rule).

# ---------------------------------------------------------------------------
# Shared code: CLI parser, CSV writer, timers, model problem
# ---------------------------------------------------------------------------
file(GLOB COMMON_SRC CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/src/common/*.cpp)
add_library(pcg_common STATIC ${COMMON_SRC})
target_include_directories(pcg_common PUBLIC ${CMAKE_SOURCE_DIR}/include)
target_compile_options(pcg_common PRIVATE -Wall -Wextra)

# Serial backend (owner: A). A library so tests and other backends can link it.
file(GLOB SERIAL_SRC CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/src/serial/*.cpp)
add_library(pcg_serial STATIC ${SERIAL_SRC})
target_include_directories(pcg_serial PUBLIC ${CMAKE_SOURCE_DIR}/src/serial)
target_link_libraries(pcg_serial PUBLIC pcg_common)
target_compile_options(pcg_serial PRIVATE -Wall -Wextra)

# Helper: add an executable only once its main file exists, so the skeleton
# builds before every implementation is written.
#   pcg_add_app(<target> <main.cpp> <src subdir or ""> [libraries...])
# Sources in src/<subdir>/ (*.cpp, *.cu) are compiled into the executable.
function(pcg_add_app target main subdir)
  if(NOT EXISTS ${CMAKE_SOURCE_DIR}/apps/${main})
    message(STATUS "skip ${target}: apps/${main} not written yet")
    set(PCG_APP_ADDED FALSE PARENT_SCOPE)
    return()
  endif()
  set(SRC "")
  if(NOT "${subdir}" STREQUAL "")
    file(GLOB SRC CONFIGURE_DEPENDS
         ${CMAKE_SOURCE_DIR}/src/${subdir}/*.cpp
         ${CMAKE_SOURCE_DIR}/src/${subdir}/*.cu)
  endif()
  add_executable(${target} ${CMAKE_SOURCE_DIR}/apps/${main} ${SRC})
  if(NOT "${subdir}" STREQUAL "")
    target_include_directories(${target} PRIVATE ${CMAKE_SOURCE_DIR}/src/${subdir})
  endif()
  target_link_libraries(${target} PRIVATE pcg_common ${ARGN})
  target_compile_options(${target} PRIVATE $<$<COMPILE_LANGUAGE:CXX>:-Wall -Wextra>)
  set(PCG_APP_ADDED TRUE PARENT_SCOPE)
endfunction()

# Serial (owner: A)
pcg_add_app(poisson_serial poisson_serial.cpp "" pcg_serial)

if(ENABLE_MPI)
  find_package(MPI REQUIRED COMPONENTS CXX)

  # Pure MPI backend (owner: A): decomposition, halo exchange, MpiBackend.
  # The hybrid versions link it too and derive from MpiBackend.
  file(GLOB MPI_SRC CONFIGURE_DEPENDS ${CMAKE_SOURCE_DIR}/src/mpi/*.cpp)
  add_library(pcg_mpi STATIC ${MPI_SRC})
  target_include_directories(pcg_mpi PUBLIC ${CMAKE_SOURCE_DIR}/src/mpi)
  target_link_libraries(pcg_mpi PUBLIC pcg_common MPI::MPI_CXX)
  # Skip the deprecated MPI C++ bindings (we use the C API); silences their warnings.
  target_compile_definitions(pcg_mpi PUBLIC OMPI_SKIP_MPICXX MPICH_SKIP_MPICXX)
  target_compile_options(pcg_mpi PRIVATE -Wall -Wextra)

  pcg_add_app(poisson_mpi poisson_mpi.cpp "" pcg_mpi)

  # MPI + OpenMP (owner: B)
  if(ENABLE_OPENMP)
    find_package(OpenMP REQUIRED COMPONENTS CXX)
    pcg_add_app(poisson_omp poisson_omp.cpp hybrid_omp pcg_mpi OpenMP::OpenMP_CXX)
  endif()

  # MPI + CUDA (owner: B). On Vanda: module load nvhpc-hpcx-cuda12/26.1
  if(ENABLE_CUDA)
    if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
      message(FATAL_ERROR "Set CMAKE_CUDA_ARCHITECTURES to the allocated GPU compute capability")
    endif()
    enable_language(CUDA)
    pcg_add_app(poisson_cuda poisson_cuda.cpp hybrid_cuda pcg_mpi)
  endif()
endif()

# These probes exercise the toolchain independently of A/B's solver delivery.
if(BUILD_CLUSTER_SMOKE)
  if(NOT ENABLE_MPI OR NOT ENABLE_OPENMP)
    message(FATAL_ERROR "Cluster probes require ENABLE_MPI and ENABLE_OPENMP")
  endif()
  add_executable(cluster_cpu_smoke scripts/smoke/cpu.cpp)
  target_link_libraries(cluster_cpu_smoke PRIVATE MPI::MPI_CXX OpenMP::OpenMP_CXX)
  if(ENABLE_CUDA)
    add_executable(cluster_gpu_smoke scripts/smoke/gpu.cu)
    target_link_libraries(cluster_gpu_smoke PRIVATE MPI::MPI_CXX)
    set_target_properties(cluster_gpu_smoke PROPERTIES CUDA_STANDARD 17 CUDA_STANDARD_REQUIRED ON)
    # FindMPI may treat mpicxx's MPI libraries as implicit. Use that wrapper for
    # the final link even though this probe contains only a CUDA source file.
    set_target_properties(cluster_gpu_smoke PROPERTIES LINKER_LANGUAGE CXX)
  endif()
endif()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
if(BUILD_TESTS)
  enable_testing()
  add_executable(test_common ${CMAKE_SOURCE_DIR}/tests/test_common.cpp)
  target_link_libraries(test_common PRIVATE pcg_common)
  add_test(NAME common COMMAND test_common)

  # Serial solver: O(h^2) convergence, std vs pipe agreement.
  add_executable(test_serial ${CMAKE_SOURCE_DIR}/tests/test_serial.cpp)
  target_link_libraries(test_serial PRIVATE pcg_serial)
  add_test(NAME serial COMMAND test_serial)

  # MPI solver vs serial, every decomp x halo x cg variant, on 1, 3 and 4 ranks.
  # Extra launcher flags (e.g. --oversubscribe) via -DPCG_MPIEXEC_EXTRA="...".
  if(ENABLE_MPI)
    set(PCG_MPIEXEC_EXTRA "" CACHE STRING "Extra flags for mpiexec in tests")
    separate_arguments(_pcg_extra UNIX_COMMAND "${PCG_MPIEXEC_EXTRA}")
    add_executable(test_mpi ${CMAKE_SOURCE_DIR}/tests/test_mpi.cpp)
    target_link_libraries(test_mpi PRIVATE pcg_mpi pcg_serial)
    foreach(np 1 3 4)
      add_test(NAME mpi_np${np}
               COMMAND ${MPIEXEC_EXECUTABLE} ${MPIEXEC_NUMPROC_FLAG} ${np} ${_pcg_extra}
                       ${MPIEXEC_PREFLAGS} $<TARGET_FILE:test_mpi> ${MPIEXEC_POSTFLAGS})
    endforeach()

    # MPI+OpenMP backend, same checks, 2 threads per rank (np 2 x 2 threads fits a 4-core laptop).
    if(ENABLE_OPENMP AND EXISTS ${CMAKE_SOURCE_DIR}/src/hybrid_omp/omp_backend.cpp)
      add_executable(test_omp ${CMAKE_SOURCE_DIR}/tests/test_mpi.cpp
                              ${CMAKE_SOURCE_DIR}/src/hybrid_omp/omp_backend.cpp)
      target_include_directories(test_omp PRIVATE ${CMAKE_SOURCE_DIR}/src/hybrid_omp)
      target_compile_definitions(test_omp PRIVATE PCG_TEST_OMP)
      target_link_libraries(test_omp PRIVATE pcg_mpi pcg_serial OpenMP::OpenMP_CXX)
      foreach(np 1 2)
        add_test(NAME omp_np${np}
                 COMMAND ${MPIEXEC_EXECUTABLE} ${MPIEXEC_NUMPROC_FLAG} ${np} ${_pcg_extra}
                         ${MPIEXEC_PREFLAGS} $<TARGET_FILE:test_omp> ${MPIEXEC_POSTFLAGS})
        set_tests_properties(omp_np${np} PROPERTIES ENVIRONMENT OMP_NUM_THREADS=2)
      endforeach()
    endif()
  endif()
endif()
