# C_1027：实现、实测证据与交接

日期：2026-10-27。本地分支：`codex/c-openmp-integration`，基于 `a93b614`。修改尚未提交或推送。A 的历史记录保持原样。此交接说明取代 [实施前任务清单](C_1027_current_tasks.md) 的“尚未交付”状态，不将该清单改写成历史完成证据。

## 五项任务的实际完成边界

| 任务 | 本轮已完成 | 仍缺少的外部条件/工作 |
|---|---|---|
| 1. 环境与接口 | 本机原有 Docker 中安装隔离 GCC/OpenMPI/OpenMP/CMake 工具链；确认 A 的契约并写入 C 设计 | A/B 人工接口复核；Atlas/Vanda 账号及实际工具链 |
| 2. C1 线程内核 | 三个内核、实际 1/2/4 线程测试、CMake 可选目标、设计/环境/AI 记录 | 目标集群复验与成员代码阅读 |
| 3. C3 实验框架 | 配置、采集、失败保留、统计、四类图、集群 allocation wrapper、PBS pilot 草案、分析依赖 | 集群队列/账号/模块/资源规则核实；PBS 草案未远程提交 |
| 4. C2 混合集成 | 因 B 未交 V1，新建独立 C 阻塞集成驱动；MPI-only/混合路径实际验收；106 oracle 执行通过 | 与 B 正式驱动合并、V3、真实计算节点/跨节点验收 |
| 5. C4/C5 数据与报告 | 60 次本地预实验、45 个正式重复样本、汇总 CSV/图、六页英文 PDF 进度草稿及 Markdown/生成源 | Atlas/Vanda 实测替换性能部分；身份信息、A/B 正文、人工审稿及最终提交 |

**不能把这五项描述为课程层面的全部完成。** 当前软件与本地证据完整；指定集群实验与最终报告仍受真实登录/资源信息缺失阻塞。没有伪造 job ID、集群时间或成员确认。

## 关键代码和复现入口

- `include/kernel_openmp.hpp`、`src/kernel_openmp.cpp`：三种无 MPI 的线程内核，B 可直接调用。
- `src/c_hybrid_main.cpp`：独立 C 集成驱动，编译为 `poisson_openmp` 和 `poisson_hybrid`。不占用 B 规划的 `mpi_main/decomposition/halo` 文件。
- `CMakeLists.txt`：可选 `ENABLE_OPENMP` / `ENABLE_MPI`，默认仍纯串行；MPI 集成需要开启 OpenMP。
- `tests/test_openmp.cpp`、`tests/test_parallel.py`、`tests/test_experiments.py`：真实线程、独立全场 oracle、统计公式/失败抑制。
- `scripts/run_experiments.py`、`summarize_results.py`、`plot_results.py`：独立于小网格验收的性能流水线。
- `configs/experiments_local.json`：已执行的本地矩阵；`experiments_cluster.template.json`：故意未激活的正式模板。
- `scripts/cluster/run_job.sh`、`vanda_cpu.pbs.example`：分配内执行器和未远程验证的 PBS 草案，不默认集群模块/队列。
- `report/source/C_progress.md`、`scripts/build_report.py`：英文进度稿源与 PDF 生成器。生成器只接收完整的 local-container 汇总，不能直接冒充集群报告。
- 根 README：完整构建、测试、运行和图表复现命令。

## 已保存的验证结果

证据目录：`docs/C/results/C_1027/`。

- `configure.log`、`build.log`、`ctest.log`：GCC Release 编译无本轮源码 warning，7/7 CTest 组通过。
- `parallel_acceptance/summary.json`：8 配置、106/106 独立数学 oracle 执行通过；按配置保存命令、场、参考、残差与日志。
- `parallel_acceptance/too-many-ranks.json`：ranks>N 被实际 MPI 程序拒绝。
- `sanitize-ctest.log`：Debug ASan/UBSan 的 core/OpenMP contract 2/2 通过；无 MPI sanitizer/ThreadSanitizer 声明。
- `serial_validation_summary.json`：37 数值案例、16 非法参数案例，包含二阶加密。
- `packages.txt`：实际工具链包版本；`environment.md` 记录镜像标识和运行边界。
- `serial-only-ctest.log`、`openmp-only-ctest.log`：默认串行及无 MPI 线程路径的独立构建复验。
- `pbs-pilot-local-acceptance/`：PBS 示例所用 2 rank x 2 thread 配置的本地验收；不表示实际 PBS/Vanda 作业。

并行 oracle 执行的 106 个案例复用了 14 种数学案例，不等同 106 个不同数学问题；各测试层覆盖也有重叠。

## 本地预实验

原始运行：`results/raw/c_local_1027/`。每个配置一次预热、三次正式重复，15 配置共 60 次；全部成功。每条运行保存原文 stdout/stderr、argv、环境和 verdict；manifest 保存源代码/可执行哈希、编译工具信息、dirty 状态与计时范围。源码是在工作区修改状态下运行，不能只用 base commit 代表执行版本。

汇总：`results/summary/c_local_1027/summary.csv`；图：`results/figures/c_local_1027/`。结果是本地容器真实测量，不是模拟数据，也不是课程指定集群数据。MPI CPU affinity 成功、内存 affinity 警告均在日志中。运行区间较短，正式实测应先扩大工作量。

PDF：`output/pdf/Project3_C_progress.pdf`，六页全部渲染检查。内容明确标为本地进度稿，包含算法、设计、验证、方法、本地观察、限制、剩余工作及 AI 使用；没有声称团队身份或集群结果齐备。

## 给 A/B 的交接

给 A：复核行范围契约、验收、残差/停止/计时语义、公共 CMake 修改和报告数学表述。A 原有纯串行入口与 oracle 未更改。

给 B：可直接链接 `poisson_openmp_core` 调用三内核。若采用 B 正式驱动，保留统一 CLI/JSON/CSV 与 FUNNELED 保证；先重跑同一验收，再用同矩阵对比。C 当前驱动只有阻塞 Sendrecv，尚未实现通信重叠。避免两个驱动的同名 variant 被混为一个版本，后续实验应记录驱动来源/源码哈希。

给 C：阅读生成代码并确认设计；提供真实集群入口与使用说明后，可继续执行远程构建、作业和实验。无需重写采集/统计；需要按真实环境调整 launcher、模块、配额和运行长度。全员身份及正文齐备后再形成最终报告。

此次未向其他成员发消息、未创建 PR、未推送仓库、未提交 Canvas。
