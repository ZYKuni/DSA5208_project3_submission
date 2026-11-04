# A 下一阶段计划：B 合入 main 后

> 当前计划已由 [A_1104 下一步安排](A_1104_next_steps.md) 更新：B/C 已整合、Vanda 数据与团队报告已交付；本文保留此前阶段规划。

## 当前状态更新（2026-10-31）

C 已推送 origin/c-openmp-integration（a1ee628），完成 B/C 集成，下文“尚未合入”和“B/C 集成必须处理的具体问题”中的前三项已由该分支处理，判定与剩余缺口见 [集成审查的复核小节](BC_integration_review.md)。该分支仍未合入 main。

## P0 状态更新（2026-11-01）

B/C 集成审查与 MPI CI 已完成，且已核实 44388a4 的远端串行/MPI 两 job 成功；本地和远端证据见 [P0 完成记录](P0_completion.md)。下表 P0 行保留为任务定义，不再表示未开始；下一项为混合集成验收。

## 依据与已完成边界

本计划替代此前仅检查 main、尚未检查 B/C 分支的版本。基准 main 为 7729bfc，已合入 B_mpi_local（d590e2e）。本次只更新规划，不合并 C、不执行新实现、不推送。

- A：串行 V0、独立 oracle、完整网格比较、统一验收及 Linux 验证已完成。
- B：V1 Sendrecv、V3 非阻塞重叠、域分解、全局残差/停止、完整场回收与实验采集器已合入。合并后 Ubuntu ARM64/GCC/Open MPI 实测 CTest 6/6、MPI 数值执行 124/124、错误处理 4/4；详见 [合并验证](B_merge_validation.md)。不再把 B 的上述交付列为等待项。
- C：已检查远端跟踪分支 origin/codex/c-openmp-integration，提交 5e29ae6。包含三种 OpenMP 内核、独立混合驱动、并行测试、采集/统计/绘图与报告草稿，尚未合入当前 main。其文档记录 106 次 oracle 执行通过等本地结果；本轮未重新运行，不能等同于 B/C 合并后验证。
- C 的交接文档还写着“尚未提交或推送”，这是写作时状态；现在远端已有提交。后续整合须追加当前交接状态，同时保留历史日志和 manifest。
- Atlas/Vanda 正式性能证据、最终报告和成员信息仍未在当前 main 验收。CI 当前默认仅运行串行构建；MPI 的这次成功来自人工发起的容器验证。

## 优先级与具体交付

| 优先级 | A 要做什么 | 交付与完成条件 | 是否依赖他人 |
|---|---|---|---|
| P0 | 审查 C 分支与 B 正式驱动的兼容性 | docs/A/BC_integration_review.md：列出构建选项、内核签名、CLI/JSON、计时/停止语义、测试与实验格式差异；给出唯一正式驱动方案和明确修改点 | 审查可立即独立完成；实际集成需按团队授权开展，B/C 人工复核 |
| P0 | 把现有 MPI 验证固化进 CI | 串行、MPI 两类 Linux job；MPI 显式安装配套 Open MPI、ENABLE_MPI=ON，调用现有 tests/validate_mpi.py；失败保存日志，成功保存 summary/源码/环境；确认远端运行后归档 x86_64 证据 | 不等待 C；远端结果需要可读取 Actions |
| P1 | 在统一驱动上验收 OpenMP 和混合路径 | 复用 A oracle 与 B/C 既有测试，新增缺少的 rank/thread × 通信方式组合；记录真实线程数与 MPI 支持级别；serial-only、MPI-only、OpenMP-only、hybrid 四种构建均通过 | 可先设计补充矩阵；执行依赖完成 C 集成 |
| P1 | 撰写算法和正确性报告正文 | docs/A/report_algorithm_validation.md：方程/离散/双缓冲/复杂度、连续与离散已知解、二阶网格加密、串行与 MPI 表格、环境失败与限制；每个数字追溯到日志 | 可立即独立做；混合和集群部分后补，C 统稿 |
| P1 | 审核 B/C 的实验数据接口与公平性 | docs/A/performance_evidence_review.md：对照现有两个采集器，核对 variant/driver、计时范围、重复/预热、基线、核数/绑定、版本/job ID 和验证状态；给出映射或最小修复，不再新增第三套采集系统 | 可先静态审查；真实性能结论依赖集群数据 |
| P2 | 提交包与材料完整性复现 | 从干净源码压缩包重建并运行验收，检查源码/配置/README/报告引用版本一致，身份信息与 AI 使用记录完整 | 可先做脚本；最终验收依赖混合代码、正式数据、最终 PDF |

建议执行顺序：先完成 B/C 集成审查，同时把 MPI CI 自动化；随后进行混合集成验收，再冻结正确性报告。不要再次从零编写 MPI 案例生成器：B 的 124 次执行已经覆盖基本边界矩阵。

## B/C 集成必须处理的具体问题

1. **CMake 选项冲突。** 当前 main 支持 ENABLE_MPI=ON、ENABLE_OPENMP 不存在，构建 poisson_mpi；C 分支要求 MPI 必须伴随 OpenMP。整合后必须保留 MPI-only，且默认串行构建仍不要求安装 MPI/OpenMP。
2. **统一正式 MPI 驱动。** 建议以 B 的 decomposition/halo/solve_mpi 和 LocalKernels 扩展点为基础，连接 C 的 jacobi_rows_openmp、residual_squared_rows_openmp、squared_norm_rows_openmp。B 的 Sendrecv/overlap 可共用线程内核，减少两套通信与停止逻辑长期分叉。是否保留 C 独立驱动作历史对照需在审查中明确。
3. **线程与输出必须真实。** 不能仅设置 OMP_NUM_THREADS 就将 B 的当前程序标成 hybrid；驱动需调用线程内核、检测实际团队大小、保持 MPI_THREAD_FUNNELED 和主线程 MPI 调用，输出正确 variant 与 threads_per_rank。
4. **保留证据身份。** C 的现有本地结果属于 C 独立驱动，B 的现有结果属于 B 驱动；不得更改标签后当作整合版结果。整合版需新日志、源码哈希与独立验收。
5. **性能可比性。** 重点核对两边初始化、初始残差、最终诊断、halo、归约的计时边界，以及固定 K 和收敛实验的区别。相同 variant 名称不意味着相同实现。

## 混合验收的最低补充范围

- 1 rank × 1 thread、1 rank × 2/4 threads、2/3 ranks × 1/2 threads；是否加入更多组合按可用资源决定。
- Sendrecv 与 overlap 均测试；N=7 的非整除分配、每 rank 1–2 行、mixed/zero RHS、K=0/1/2/5、check-every>1、收敛与未收敛、ranks>N 拒绝和输出失败。
- 完整网格对独立 oracle/V0 比较，独立重算残差，检查退出码、单根输出与无超时；仅有 checksum 或残差小不算完整通过。
- OpenMP 归约顺序变化按既定容差判断，不要求逐位相同；若失败先定位原因，不能直接放宽阈值。
- 无 MPI 的 OpenMP 路径仍应独立构建；合并后测试组数量可变化，不把现有 6/6 或 C 的历史数量机械设为新目标。

## 分工边界与真正的外部依赖

A 主责集成规范、正确性、CI、算法/验证正文及提交包。B 复核通信和混合中的 MPI 调用，负责 V0/V1/V3 的集群通信实验。C 复核线程内核和绑定，负责混合实验、统计图表与 PDF 统稿。已有采集工具可复用，A 不重复接管 B/C 的实现和绘图任务。

Atlas/Vanda 真实账号/资源、成功作业与绑定日志是正式性能实验的前提。建议下一次团队交接直接收集一次最小成功作业的完整记录，然后开展正式重复实验；本地容器时间不能替代指定平台数据。姓名学号、Canvas 精确截止时刻和最终人工审核由成员实际确认。

## 建议近期安排

- 第一批：B/C 兼容性审查 + MPI CI，交付可执行的修改清单和 CI 证据。
- 第二批：经授权整合 C，跑统一混合验收，修复真实失败；同步完成算法/正确性正文。
- 第三批：审查 Atlas/Vanda 数据与图表来源，冻结正文和实验参数，完成干净提交包复现。

V3 已有实现，不再列为待开发；V4 二维分解等新功能继续后置，优先完成 MPI+OpenMP、真实集群实验与最终 PDF 的课程必需项。
