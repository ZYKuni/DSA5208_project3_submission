# C：OpenMP 与混合集成设计

**当前状态（2026-10-31）：** 正式混合入口为 `src/hybrid_main.cpp`，注入 B 的 `LocalKernels`，同时支持 Sendrecv/overlap。`src/c_hybrid_main.cpp` 现仅提供独立 OpenMP 入口，并复用公共 CLI/JSON。最新验收和边界见 [C_1031 交接](C_1031_handoff.md)。下面保留 10/27 历史实现说明，不能将其中的独立 MPI 驱动或旧测试数量作为现行接口。

日期：2026-10-27。入口：`src/kernel_openmp.cpp`、`src/c_hybrid_main.cpp`。这是已实际编译测试的 C 集成实现；不替代 B 后续正式驱动和 V3 的责任。

## 内核

三个入口声明在 `include/kernel_openmp.hpp`，与 A 的行范围/布局契约一致：更新、残差平方和、普通平方和。区间 `[begin,end)` 支持空区间；所有布局/行范围/别名检查在线程区外完成。每次调用建立一个 OpenMP team，外层按行 `schedule(static)`，内层连续列访问。`default(none)` 显式列出共享和 firstprivate 数据，两个平方和用 `reduction(+:sum)`。

更新从 old/rhs 读取，只写 next 的指定内点，不更新 halo、物理边界或交换缓冲。残差计算使用全局 `N` 的步长。返回局部平方和，驱动全局 SUM 后再开平方和归一化。求和顺序改变允许既定浮点容差，未使用 fast-math。

## 驱动与线程支持

同一份 C 驱动编译为无 MPI 的 `poisson_openmp` 和有 MPI 的 `poisson_hybrid`。`--kernel serial` 选择原串行行内核，形成 MPI-only 路径；默认 `--kernel openmp`。A 的 `poisson_serial` 保持独立。

MPI 初始化请求并检查 FUNNELED，所有 MPI 调用由初始化线程在 OpenMP 区外发起。驱动关闭动态 team，使用真实并行区的 `omp_get_num_threads` 探测 team 大小，并核对各 rank 的 team 大小一致；没有将 `omp_get_max_threads` 当作实际执行数量。实际线程创建也由内核测试验证。探测在求解计时之外，后续各次 team 以动态关闭的相同配置运行；未对每个循环额外加入计数 instrumentation。

MPI 按商/余数分配拥有行，前余数个 rank 多一行。Grid 不支持空所有权，因此 ranks>N 明确拒绝。两次 Sendrecv 完成上下 halo 交换，物理边界通过 MPI_PROC_NULL 保持零。每轮先同步 old，再更新和交换；计划内残差检查重新同步当前解。当前简单版本会在相邻阶段重复交换相同 halo，保留这个开销便于验证，不将其描述为优化后的通信实现。

全局 RHS 范数在计时外建立；收敛模式初始残差在计时内；fixed 精确执行 K 轮；最终独立诊断在计时外。开始有一次 barrier，最终上报各 rank 墙钟最大值；不逐轮额外增加计时 barrier。完整场只有显式 `--solution` 时才 gather 并由 rank 0 写 CSV；stdout 只由 rank 0 写一个 JSON。

## 验证与限制

实测 1/2/4 线程内核、8 组真实进程/线程配置、106 个独立数学 oracle 执行均通过；包含仅一行/两行、非对称场、非整除划分、空区间、奇偶/K=0、检查间隔和零 RHS。另测 ranks>N 拒绝。ASan/UBSan 检查通过 core 与 OpenMP contract；未运行 ThreadSanitizer。

首版每次调用创建线程区，未实现持久并行区、SIMD 指令或 NUMA 并行 first-touch。Grid 分配/清零由串行初始化完成；这些是未来可研究项，不宣称收益。B 的非阻塞 V3 可继续调用相同行区间内核，窄子域需避免边界行重复更新。

## 原始规范

- [OpenMP reduction](https://www.openmp.org/spec-html/5.1/openmpsu117.html)
- [OpenMP places](https://www.openmp.org/spec-html/5.1/openmpse62.html)
- [OpenMP binding](https://www.openmp.org/spec-html/5.1/openmpse61.html)
- [MPI_Init_thread](https://docs.open-mpi.org/en/main/man-openmpi/man3/MPI_Init_thread.3.html)
- [CMake FindOpenMP](https://cmake.org/cmake/help/latest/module/FindOpenMP.html)

参考 OpenMP 5.1 的基础语义不表示使用了 5.1 runtime；本地实际为 OpenMP 4.5。
