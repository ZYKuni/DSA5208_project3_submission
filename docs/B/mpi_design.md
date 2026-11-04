# B：MPI 设计、计时与 C 接入接口

日期：2026-10-31。已实现 V1/V3，当前调用 A 的串行局部内核；不是 MPI+OpenMP 的 V2。本文的算法说明可作为 B 报告正文初稿；性能结论必须补充 Atlas/Vanda 实测。

## 1. 域分解（domain decomposition）

N 为全局每方向内点数，P 为 MPI 进程数，r 为从 0 开始的 rank（进程编号）。令 q=N/P（整数除法），m=N%P。进程 r 拥有 q+[r<m] 行，前面共有 r*q+min(r,m) 行。由此前 m 个进程多一行，每个内点仅属于一个进程，负载最多差一行。P>N 明确拒绝，不建立空子域。

每个进程只分配局部 old、next、rhs 三个 Grid。局部 i 映射到全局 offset+i；局部拥有行是 [1,rows]，0 和 rows+1 为 halo（邻居边界副本）。左右边界列为 0 和 N+1。RHS（右端项）由全局坐标本地生成，不广播完整网格。

以 N=7、P=3 为例：

```text
全局上边界：0
rank 0: offset=0，拥有行 1,2,3；下 halo 接收全局行 4
                         ⇅ 交换行 3 / 4
rank 1: offset=3，拥有行 4,5；上 halo 接收行 3，下 halo 接收行 6
                         ⇅ 交换行 5 / 6
rank 2: offset=5，拥有行 6,7；上 halo 接收行 5
全局下边界：8
```

首尾邻居为 MPI_PROC_NULL（空进程），接收不改变对应物理边界；边界初始为零且从不更新。每次只发送 N 个内点值，不传左右两列。

## 2. V1：Sendrecv 阻塞交换

先把第一行发送到上邻居，同时从下邻居接收其第一行；再把最后一行发送到下邻居，同时从上邻居接收其最后一行。两个方向使用不同 tag（消息标签）。MPI_Sendrecv 将发送与接收组合，不依赖系统恰好有足够的消息缓冲。交换完成后更新全部拥有行，再交换 old/next。

## 3. V3：非阻塞交换与计算重叠

先启动两次 MPI_Irecv，再启动两次 MPI_Isend；此时 old 的拥有行只读，接收缓冲是 old 的两个 halo，更新目标是独立 next。

1. rows>=3 时更新内部行 [2,rows)，它们不读取接收中的 halo。
2. MPI_Waitall 等待全部四个请求（包括发送）完成。
3. 更新第一行；rows>1 时再更新最后一行。
4. 交换 old/next。之前发送使用的存储已释放给应用，可在下一轮安全写入。

rows=1 时只更新一次第一行；rows=2 时更新两条边界行，没有内部计算可用于重叠。收发未完成前不写发送缓冲、不读取接收缓冲。非阻塞仅提供重叠机会，不保证实际传输与计算并行推进，效果依赖 MPI 实现和硬件，须据实测判断。[MPI 非阻塞通信规范](https://www.mpi-forum.org/docs/mpi-4.1/mpi41-report/node71.htm)

## 4. 全局残差、停止和结果回收

局部计算残差平方和，MPI_Allreduce + MPI_SUM（全局求和）后再开平方；分母同样由全局 RHS 平方和计算。不能把各进程的局部相对残差直接相加。RHS 为零时使用绝对残差。

每次残差检查前重新同步**当前解**的 halo，避免交换缓冲后使用上一轮邻居值。两个版本统一使用 Sendrecv 做残差同步，使对照仅改变更新阶段的通信方式。此实现每轮更新前都有交换，检查轮另外有一次交换；没有缓存 halo 有效性来省略下一轮交换，比较时必须说明这一实现选择。

fixed（固定步数）和 converge（收敛停止）的初始检查、check-every、末轮强制检查、零步及退出码均遵循 A 的语义。全局残差使所有 rank 在同一迭代停止。计时后重新计算最终诊断，不把最终诊断混入核心时间。

仅用户给出 `--solution` 时调用 MPI_Gatherv（可变长度汇集）：按每个 slab 的行数和 offset，把拥有行连同左右零边界收集至 rank 0；全局上下边界仍为零。只有 rank 0 分配全局网格并写 CSV。[MPI_Gatherv 接口](https://www.mpich.org/static/docs/latest/www3/MPI_Gatherv.html)

采用 int 计数的可移植 MPI 接口，halo 计数和全局回收计数都做越界检查；大规模普通求解不受全局回收计数限制。参数、内存或文件错误由 MPI_Abort 结束整个任务，避免一个进程抛出异常后其他进程永久等待。

## 5. 计时和通信成本

初始化和 RHS 范数在计时外；一次 MPI_Barrier（进程同步）后用 MPI_Wtime 开始计时。时间覆盖更新、缓冲交换、halo、既定残差检查和全局归约。结束后取所有 rank 耗时的最大值。计时归约、最终诊断、gather（回收）与文件输出不在计时内；没有每轮额外 barrier。

每轮局部更新工作量约 O(N²/P)，每次 halo 交换每个内部 rank 向两个邻居各发送 N 个 double，即共 16N 字节，另接收同样大小。两端 rank 各只有一个真实邻居。检查轮额外增加一次 halo 交换和一次全局残差求和。强扩展时 N 固定、局部行数下降，通信/计算比例提高；当只剩一两行时，V3 没有内部计算可覆盖通信等待。

这些是算法成本分析，不是已测瓶颈。当前只提供整体求解时间，未单独测通信阶段；不能据此报告“通信占比为 X%”或证明 MPI 异步进度有效。正式对照固定 N、K、check-every、核数、节点布局、绑定与编译选项，分别预热并重复至少三次，报告中位数和范围。

## 6. C 的 OpenMP 接入

`include/mpi_solver.hpp` 的 LocalKernels 包含 update、residual、norm 三个函数指针，默认 A 的串行内核。C 提供同签名 OpenMP 内核后可以注入，不需要改写 halo、分解或停止逻辑。

```cpp
poisson::LocalKernels kernels{
    jacobi_rows_openmp, residual_squared_rows_openmp, squared_norm_rows_openmp
};
auto result = poisson::solve_mpi(config, local_grid,
    poisson::Communication::Sendrecv, MPI_COMM_WORLD, kernels);
```

上面是待 C 实现后的接入示例，不是现有可编译的 OpenMP 代码。三个回调都必须同步完成后返回，使用 [begin,end) 行范围，不调用 MPI，不换缓冲，不改物理边界；两个平方和使用线程 reduction（归约）。本版本使用 MPI_THREAD_FUNNELED，仅初始化 MPI 的线程执行 MPI 调用。[MPI 线程支持说明](https://www.mpich.org/static/docs/latest/www3/MPI_Init_thread.html)

C 还需增加 OpenMP 构建选项/链接、V2 入口或明确的内核选择参数、真实线程数探测与 JSON 输出。不能只设置 OMP_NUM_THREADS 后仍报告或假定已使用线程。B 会复核该接入及绑定；A 使用原验收器独立验收。
