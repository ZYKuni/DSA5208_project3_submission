# C：当前进度核对与近期任务清单

后续状态：用户随后授权实施，本地交付与实测结果见 [C_1027 交接](C_1027_handoff.md)。本文保留为实施前核对清单。

核对日期：2026-10-27（Asia/Singapore）。远程快照：`origin/main`，提交 `a93b614de41faeceef732f25a34c5d3dc28a88c2`。本清单依据团队分工、A 的交接文档、实际源码、构建配置、测试和已保存结果编写。它是 C 的执行建议，不替代原分工，也不表示其他成员已确认。

## 1. 当前实际进度

| 部分 | 仓库证据 | 对 C 的意义 |
|---|---|---|
| A：串行基线 | `src/serial_main.cpp`、`src/solver_serial.cpp`、`src/kernel_serial.cpp` | 可以立即作为线程内核的对照 |
| A：公共接口 | `include/config.hpp`、`include/grid.hpp`、`include/kernel.hpp` | 已明确局部行区间和平方和语义；交接仍标注 B/C 未人工确认 |
| A：独立验证 | `scripts/validation_oracle.py`、`scripts/compare_grids.py`、`scripts/run_acceptance.py` | 可直接复用，不必重新开发数学 oracle |
| A：本地结果 | `docs/A/results/A_1027/` | 提供串行正确性证据；不能用作集群性能数据 |
| B：MPI | 无 MPI 驱动、分解、halo 或 MPI 构建目标 | V2 集成和真实混合实验仍依赖 B 交付 |
| C：OpenMP | 无线程内核、线程测试或 OpenMP 构建目标 | C1 尚未在仓库交付 |
| C：实验与分析 | 无集群模板、性能采集、统计或绘图脚本 | C3 可以先做结构与协议；平台命令须实测 |
| 报告与集群 | 无正式报告、Atlas/Vanda 作业记录或性能图 | 尚不能形成扩展性结论 |

克隆时可见远程分支仅 `main` 与 `A_1027`，A_1027 已合入主分支；未见 B/C 远程开发分支。本判断仅覆盖该仓库快照，不推断他人未推送的工作。

### 本次独立复核

当前 shell 未找到 CMake，因此用 `/usr/bin/clang++` 直接编译，参数为 `-std=c++17 -O3 -DNDEBUG -Wall -Wextra -Wpedantic -I include`。使用本工作区 Python 3.12.11 运行现有测试入口：

- `tests/test_core.cpp`：通过；覆盖手算、边界、别名/行范围及模拟不均匀 slab。
- `tests/validate_serial.py`：37 个数值案例通过，16 个非法 CLI 案例按预期拒绝。
- `tests/test_compare_grids.py`：14 个测试方法通过。
- `tests/test_acceptance.py`：10 个测试方法通过，其中包含完整 14 案例验收及失败注入。

各测试计数存在覆盖重叠，不能相加为独立样本数。此次没有运行 CMake/CTest、sanitizer、MPI、OpenMP 或集群作业；A 保存的这些历史结果应与本次复核区分。临时构建与数值复核输出位于 `/private/tmp/dsa5208-proj3-review-20261027/`，不属于最终提交证据。

## 2. 现在应先完成的任务

### P0：确认环境与接口（立即做，可与 C1 并行推进）

- [ ] 与 B 确认选用 Atlas 或 Vanda、账号与计算节点访问；确认调度器、可用节点/物理核、队列、配额及 MPI/编译器/OpenMP runtime。
- [ ] 在真正使用的编译器下验证 OpenMP 能编译、链接，并实际启动多个线程。只设置环境变量不能证明已经并行。
- [ ] 记录工具版本、构建命令和实际线程数；可使用 `OMP_DYNAMIC=FALSE` 避免动态缩减影响首轮验证，但仍以实测 team 大小为准。
- [ ] 阅读 `docs/A/algorithm.md`、`docs/A/A_handoff.md`、`docs/A/A_1027_tools.md` 与公共头文件，给出 C 的接口接受或具体疑问记录。
- [ ] 与 B 对齐内核选择方式、线程元数据、计时边界和 JSON/CSV 输出。避免分别复制一套不一致的驱动逻辑。

本机当前 shell 未找到 `cmake`、`mpicxx`，常见 Homebrew 路径也未找到 `libomp`；这不是对整台机器所有安装位置的穷尽检查。不要假定 Apple Clang 已能直接使用 OpenMP，也不要套用 Project 1/2 的 Python 环境作为完整 C++ 工具链。

### P0 / C1：实现可独立验证的 OpenMP 内核

建议首批交付：

```text
src/kernel_openmp.cpp
include/kernel_openmp.hpp        # 或协调后向公共 kernel.hpp 增加声明
tests/test_openmp.cpp
docs/C/openmp_design.md
docs/C/environment.md
docs/C/ai_usage.md
CMakeLists.txt                  # 与 A/B 协调共享文件修改
```

建议提供与串行函数对应且符号独立的三个入口：

```cpp
void jacobi_rows_openmp(const Grid& old, Grid& next, const Grid& rhs,
                       std::size_t begin, std::size_t end);
double residual_squared_rows_openmp(const Grid& current, const Grid& rhs,
                                   std::size_t begin, std::size_t end);
double squared_norm_rows_openmp(const Grid& grid,
                               std::size_t begin, std::size_t end);
```

第三个函数用于 RHS 范数，虽在当前串行计时范围外，也应明确由哪个版本实现；可先保留串行路径并记录，不应遗漏接口设计。

必须保持以下契约：

- `N` 是全局每方向内点数，`h=1/(N+1)`；不能用本地 `rows` 计算步长。
- 局部拥有行是 `1..rows`，内核接收半开区间 `[begin,end)`；空区间合法。
- 行偏移只用于全局坐标含义，不应把全局索引直接当本地存储索引。
- old/rhs 只读，next 每个内点只有一个线程写；保持串行版布局、别名和行范围检查。
- 不写 halo、物理边界和指定范围外的行；不在内核中通信、交换缓冲或执行全局收敛判断。
- 以 `schedule(static)` 为首版；循环内临时量保持线程私有，平方和采用 `reduction(+:sum)`。
- 返回局部平方和，不先开平方、不先归一化；B 进行全局 SUM 后才计算范数。
- 通过 CMake 查找并链接 `OpenMP::OpenMP_CXX`；保留无需 MPI/OpenMP 的串行构建路径，避免影响 A 的基线。

**验收：** 使用真实 1/2/4 线程（以可用资源为限）与串行内核对照；覆盖非对称输入、非零 row_offset、仅 1/2 行的 slab、空区间、分段行更新及边界/halo 不被改写。平方和允许合理的浮点归约差异，不能为掩盖错误放宽标准。

独立内核测试不依赖 B；若需整程序验收，增加一个小型无 MPI 线程驱动或协调可选内核入口。当前 `serial_main.cpp` 固定调用 `solve_serial`，且写死 `variant=serial`、`threads_per_rank=1`，单纯设置 `OMP_NUM_THREADS` 不会调用新内核。

### P1 / C3：先建立实验记录与配置，暂不依赖 V2 完成

建议交付：

```text
configs/experiments.json
scripts/run_experiments.py
scripts/summarize_results.py
scripts/plot_results.py
scripts/cluster/                # 按目标平台实际调度器建立模板
docs/C/experiment_protocol.md
requirements-analysis.txt       # 实际使用第三方绘图库时再增加
```

立即可确定的协议：

- 强扩展：固定 N、K、problem、check_every；改变资源。
- 弱扩展：固定每核心工作量和 K，N 近似随总核心数平方根增加，记录取整偏差。
- 配比实验：固定总核心数、节点数、N、K，比较不同 ranks × threads。
- 预热一次，正式重复至少 3 次，资源允许时 5 次；记录全部样本，报告中位数和范围/IQR。
- 原始 stdout/stderr、argv、环境、退出码与时间戳保留；失败或超时单独记录，不计入成功样本。
- 性能输出默认不导出完整场；在计时外完成必要诊断并记录其范围。
- 不使用 mock 数据作性能结论；分析开发中的模拟输入必须标注，且不得混入正式结果。

记录字段至少包括：run_id、commit/dirty 或源码哈希、cluster、job_id、node_count、CPU、编译器/flags、MPI/OpenMP 版本、variant、N、mode、请求/实际迭代数、tol、check_every、ranks、实际 threads_per_rank、ranks_per_node、绑定设置、repeat、solve_seconds_max、最终残差与验证状态。

正式图表应能从原始运行记录重新生成。Python 绘图依赖与当前仅标准库的正确性工具分离；不要预先安装项目未使用的包。

## 3. B 交付后完成的集成任务

### C2：V2 与统一验收

- [ ] B 的 MPI 驱动能选择串行/线程内核，保持同一数学问题和停止逻辑。
- [ ] B 使用 `MPI_Init_thread` 请求并检查 `MPI_THREAD_FUNNELED`；MPI 调用由初始化 MPI 的主线程在 OpenMP 并行区之外执行。
- [ ] B 保证更新或残差计算所需的当前 halo 有效；C 不在内核里隐式刷新 halo。
- [ ] 统一 JSON 保持同名参数和字段，报告实际 rank/线程数；stdout 由一个 rank 输出单个 JSON 对象。
- [ ] 完整场由 B gather 后单点写出，含全部物理边界；日志走 stderr。
- [ ] 验证 1 rank × 1/多线程、多 rank × 1/多线程，覆盖非整除划分与窄子域。

**配置陷阱：** `acceptance_serial.json` 含 N=1/2。不能直接把全部案例改成 3 ranks；首版 `Grid` 不支持零行子域，B 应拒绝 ranks>N。单 rank 配置保留 N=1/2；3-rank 配置只保留 N>=3。可用 N=3,R=3 检查每 rank 一行，用 N=7,R=3 检查不均匀划分。过多 rank 的拒绝测试另做，当前统一入口只接受预期退出码 0/2。

**工具边界：** `run_acceptance.py` 限制 N<=255、逐案例导出完整网格并计算独立 oracle，仅用于正确性。不能把它直接当正式性能采集器。其线程元数据检查也不能独立证明程序真正启动了所报告的线程。

完整场比较的既定门槛为每点 `abs(a-b) <= 1e-10 + 1e-10*abs(reference)`，物理边界精确为零；同时报告 L2 误差。覆盖 discrete-mixed、K=0/1/2/5、fixed/converge、zero RHS、check_every>1 和未收敛退出。

### C4：集群试跑后再开展正式性能实验

- [ ] 先保存一次 Atlas/Vanda 真实计算节点小作业：job ID、分配资源、命令、绑定、实际线程数、JSON 和验证结果。
- [ ] 确认 rank 与线程没有挤到同一批核心，测试适用的 `OMP_PLACES=cores` 与 `OMP_PROC_BIND=close/spread`。
- [ ] 选择足够长且不超内存的 N/K，再冻结正式矩阵；计划中的 1024/2048/4096 只是候选值。
- [ ] 按已冻结口径采集强/弱扩展与配比；B 采集 MPI-only 和通信对照，C 负责汇总绘图。
- [ ] 报告最大 rank 墙钟耗时，计入必要通信与归约；初始化/输出另计，不逐轮额外加计时 barrier。
- [ ] 基线取同集群、相同任务的合理优化串行；若采用 P0 核相对基线，明确标注。
- [ ] 区分固定 K 的扩展性与同容差 time-to-solution；弱扩展变慢时同时考虑一维条带划分导致的 halo 增长。

## 4. 与 A/B 的依赖和职责边界

| 对象 | 需要的交付/确认 | C 现在能独立推进的内容 |
|---|---|---|
| A | 接受公共接口、共同修改 CMake/声明的方式、线程验收结果复核、基线计时口径 | 阅读并复用已有 oracle、内核对照、C 自己的设计与 AI 记录 |
| B | V1 驱动、halo、全局归约、gather、线程支持、内核选择、MPI 元数据及平台信息 | 线程内核、真实线程测试、日志协议、性能矩阵与分析结构 |
| 集群 | 账号、实际调度/模块/绑定和计算资源 | 本地正确性开发；正式集群命令及性能结论必须等实测 |

C 不承担 B 的域分解、halo、V1/V3 实现，也不需要重写 A 的数值 oracle。C 负责 OpenMP、混合实验、性能分析与 PDF 统稿；A/B 仍应分别提供自己负责的正文与证据。A 负责最终打包上传，C 核对报告与图表。

## 5. 近期完成顺序与第一轮交付

按 10/27 的仓库状态，原计划中 10/25–26 的 C1 尚未有交付证据，10/28 的完整 V2 里程碑存在风险，应以实际验收结果更新进度。

1. **10/27–28，优先：** 环境与接口确认、三个线程入口的范围设计、线程内核与实际线程测试、CMake 接入、C 的设计/环境/AI 记录。
2. **同一阶段并行准备：** 实验协议、元数据结构、配置草案，与 B 确认集群访问和第一条真实作业路径。
3. **B 的 V1 到位后：** 接 V2、拆分验收配置、完成真实多 rank × 多线程验证及集群小作业。
4. **10/30–11/06：** 正式强/弱扩展、配比、重复统计与图表；V3 完成后再加通信优化对比。
5. **11/07–12：** 性能正文与 PDF 整合、复现核对、提交前图表审查。

第一轮 C 的完成标准：别人能按文档构建线程目标，确认真实多线程执行，复现线程内核与串行的一致性，并将线程内核按现有行区间接口接入 B 的驱动；实验协议清楚，但不以尚未采集的数据填充图表。

若 10/28 仍无集群访问，应优先联系课程支持解决实测来源；继续独立内核开发。暂不扩展 CUDA/Kokkos、二维分解或新算法，优先完成 V0–V2、正确性和指定集群结果。

## 6. 参考入口

- [团队分工](../Project3_任务拆解与三人分工.md)
- [A 的算法/布局/停止/计时约定](../A/algorithm.md)
- [A → B/C 交接](../A/A_handoff.md)
- [统一验收与接入指南](../A/A_1027_tools.md)
- [A 第二阶段实际结果](../A/A_1027_results.md)

AI 使用记录：本清单由 OpenAI Codex 辅助完成仓库读取、源码与文档核对、现有串行测试复跑和任务整理。未实现线程/MPI 内核、未运行集群实验、未代替成员的人工接口确认。后续由 C 在自己的 AI 日志中按实际使用补充。
