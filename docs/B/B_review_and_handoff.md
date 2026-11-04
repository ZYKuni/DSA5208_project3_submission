# B 本地完成情况、检阅入口与交接需求

日期：2026-10-31；本地分支 B_mpi_local；起点 a93b614。本地验证完成后，组员 B 已指示提交并推送本分支；测试证据中的 dirty 状态描述测试时的工作区。sources/ 和 A 的历史证据均未改动。

## 1. 已同步的组员进度

本次已执行远程 fetch（获取最新提交）。可见远程分支为 main 与 A_1027；main 已包含 A_1027 的合并提交，没有发现 C 的远程分支、OpenMP 源码或集群日志。这只描述仓库可见状态，不代表 C 私下尚未开展工作。

| 成员 | 已可用材料 | 仍待交接 |
|---|---|---|
| A | 公共 Grid/Config/内核、V0、非对称离散已知解、完整网格比较、独立残差与统一验收入口 | 本次 MPI 实现的交叉审查与目标集群验收、最终打包复现和提交信息 |
| B | 本次 B1–B4 代码、真实本机 MPI 验证、B5 记录工具、MPI 设计正文初稿 | 正式集群通信/扩展实验与结果解释、对 C 混合实现的复核 |
| C | 当前远程未发现交付，不能标为已完成 | OpenMP 内核/V2、集群作业模板及实际环境、混合实验/图表 |

## 2. 本次完成与验收证据

| 任务 | 本地结果 | 主要文件 |
|---|---|---|
| B1 按行划分与余数分配 | 完成；N=1..129、所有合法 P 的覆盖/均衡检查通过 | src/decomposition.cpp、tests/test_decomposition.cpp |
| B2 Sendrecv halo | V1 完成；真实多进程小网格验证通过 | src/halo.cpp、src/mpi_main.cpp |
| B3 全局残差与小问题回收 | 完成；全局停止、零 RHS、非整除 Gatherv、仅根进程输出 | src/solver_mpi.cpp |
| B4 非阻塞重叠 | V3 完成；内部/边界行分离，等待全部请求再换缓冲 | src/halo.cpp、src/solver_mpi.cpp |
| B5 MPI 实验 | 采集工具、实验配置及本机流程试跑完成；正式集群数据未采集 | scripts/run_mpi_experiments.py、configs/mpi_experiments.example.json |

为了让两个入口的参数与 JSON 字段保持一致，把 A 原 serial_main 中的解析/输出提取为 src/cli.cpp，串行数值算法未改动。保留默认不依赖 MPI 的构建。LocalKernels 为 C 留出线程内核接入点，未替 C 实现 V2。

实际环境：macOS arm64、Apple M5（10 物理核）、AppleClang 21.0.0.21000334、CMake 4.4.5、MPICH 5.0.2、Python 3.9.6。本地工具安装于被 Git 忽略的 build-tools/；没有替换已有 Conda 环境。

| 验证 | Release | Debug + ASan/UBSan（内存/未定义行为检查） |
|---|---|---|
| 非 MPI CTest | 5/5 组通过 | 5/5 组通过 |
| MPI 数值矩阵 | 124/124 通过 | 同一 124/124 通过 |
| MPI 错误处理 | 4/4 按预期拒绝 | 同一 4/4 按预期拒绝 |
| 与独立有限步参考的最大逐点误差 | 6.661338147750939e-16 | 6.661338147750939e-16 |
| 与 V0 完整场的最大逐点误差 | 0 | 0 |

覆盖 1/2/3/4 ranks × Sendrecv/overlap、四类 RHS、N=1/2、每 rank 1–2 行、余数划分、N=127、K=0/1/2/5/16、收敛和未收敛退出、不同检查间隔、零 RHS。四项错误测试为进程过多、无效通信方式、N=0、根进程写文件失败；均有超时保护，未将挂起当作通过。两种构建测试的是同一批案例，不能把两遍计数说成 248 个独立数学案例。

证据位于 [results/B_1031](results/B_1031/)：release/sanitizer_mpi_evidence.json 保存每个案例的命令、原始 stdout/stderr、独立比较/残差、V0 对照和错误日志；两个 summary、两份 CTest 日志及 source_manifest 记录版本和源码哈希。完整逐点 CSV 可在本机 build*/mpi-validation 的运行目录查看，运行脚本可重新生成；仓库保存紧凑证据，避免提交数千份重复网格。

实验记录脚本实跑 V0/V1/V3 各 1 次预热 + 3 次正式运行，共 12 次，均成功生成日志和汇总，见 experiment_collector_smoke/。这是 N=31、K=10 的**采集流程检查**，时间太短且未绑核，不用于加速比、扩展性或“V3 更快”的结论。示例正式矩阵仅 dry-run（生成计划），没有把示例当实测。

## 3. 你现在如何检阅

1. 先读 [MPI 设计与 C 接口](mpi_design.md)，确认 B 的职责与解释。
2. 按 README 的 MPI 示例检查 V1/V3 输出和完整场。
3. 查看本目录结果表与两份 evidence.json 的 failures（应为空）。
4. 查看 git diff，重点为 halo 缓冲生命周期、残差同步、计时范围、CLI 提取和 C 接口。
5. 本次按组员 B 指示提交/推送 B_mpi_local，后续由团队审查后决定是否合入 main。

本机已有工具，可从仓库根目录使用 `build-tools/bin/cmake`、`build-tools/bin/ctest` 和 `build-tools/bin/mpiexec`；README 的通用命令假定工具已在 PATH 中。所有 build*/ 目录均不提交。

## 4. 剩余任务需要谁提供什么

### A：交叉验证与最终规范

- 复核 B 的全局行偏移、物理边界、halo 方向、全局范数和停止规则；交付审查意见、采用的 commit 或源码哈希。
- 在团队目标环境对 V0/V1/V3，以及 C 交付后的 V2 运行 A 的验收器；提供原始 stdout/stderr、配置、summary、失败案例的完整 CSV 和复现命令，不能只口头说“通过”。
- 确认最终报告使用的算法/容差/计时规范，以及 Canvas 精确截止时间、文件格式、成员姓名学号；完成最终复现和打包。A 已提供的数学接口足以完成本次 B 实现，当前不需要等待新的串行代码。

### C：混合集成和集群实验协作

- 交付 src/kernel_openmp.cpp 及声明，包含 update/residual/norm 三个匹配 LocalKernels 的函数；提供 CMake OpenMP 链接、实际线程数输出、线程绑定设置与 1/多 rank × 1/多 thread 的验收日志。B 收到后才能完成混合代码复核。
- 提供已实跑成功的 Atlas 或 Vanda 作业脚本、模块加载/编译/启动命令、调度器/队列、可用节点/核数与 MPI 版本。脚本必须包含 MPI rank（进程）和线程的资源分配/绑定，不能只给通用模板。
- 确认正式实验矩阵：N、K、check-every、重复次数、节点数、每节点 ranks、每 rank threads、基线与绑定。B 负责 MPI-only/通信日志，C 负责混合/强弱扩展和图表，防止比较条件不一致。
- 提供混合原始日志、CSV 和绘图脚本；每个图的数据点应能定位到实际 job ID、run ID、版本和原始文件。B 据此解释通信现象并复核 MPI 线程调用和布局。

### 集群访问：B5 的直接前提

本次会话没有已确认的 Atlas/Vanda 账号、计算节点分配或成功运行日志。需要你或已开通集群的组员提供：登录/使用方式（不要在仓库提交密码或令牌）、可用 CPU 节点资源、调度器、模块与一次成功的小作业记录。若由组员代跑，应传回完整输出目录，不能只给截图或一个平均耗时。

**MPI-only 的正式实验不依赖 C 的 OpenMP 代码。** 一旦 B 获得可用集群环境，就可以独立运行 V0/V1/V3；这是 B 的剩余工作，不应全部转交 C。跨节点实验还需要至少两个可分配节点；无法取得时如实写资源限制，不能伪造跨节点结果。

## 5. 正式数据交接格式

交付一次采集的整个输出目录，至少含 config.json、manifest.json、plan.json、每次 command/stdout/stderr/result/verdict、runs.csv、summary.json。另附实际提交脚本、作业 ID、节点清单及构建日志。失败/超时日志也保留，不混入成功统计。

必须可核实：cluster、job_id、node_count、cpu_model、每节点物理核数、compiler、flags、mpi_version、源码 commit/dirty/哈希、variant、N、mode、requested/actual_iterations、tol、check_every、ranks、threads_per_rank、ranks_per_node、rank_binding、OMP_PLACES、OMP_PROC_BIND、repeat、solve_seconds_max、最终残差、validation_status 及验证证据。MPI-only 的 threads_per_rank=1；混合配置必须记录实际线程数。

采集器把部分公共字段放在 config/manifest，逐次 JSON 保存求解字段；C 汇总 CSV 时按 run_id 关联这些文件，不丢失元数据。预热不入统计，至少三次正式重复；正式配置任何一次失败都应排查再用新的输出目录重跑，不能挑成功最快值。

尚不能完成的结论：Atlas/Vanda 上的加速比/效率与跨节点扩展、阻塞/非阻塞的真实性能优劣、V2 混合正确性/性能、最终带图表的 MPI 实验讨论。收到上述代码与实测数据后才能完成。
