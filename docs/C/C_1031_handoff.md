# C_1031：正式 MPI/OpenMP 集成与下一阶段交接

日期：2026-10-31。当前交付分支 `c-openmp-integration`（远程由原 `codex/c-openmp-integration` 改名，已跟随）。本次按 C 的任务顺序保存已有成果、接入 A/B、重跑本地验收并准备正式集群实验。10/27 的历史证据与 PDF 保留，不改写成当前版本的集群性能结论。

## 已完成的交付

- C 原有 OpenMP、独立集成验证、实验框架和进度稿已提交为 `5e29ae6` 并推送 C 分支。
- 最新主分支包含 A_1031（`89fd8d5`，main 合并 `24ae1b4`）；已接入 C 分支，保留 A 的 Linux/GCC 验证和 CI。
- 接入 B_mpi_local（`d590e2e`）：B 的 `LocalKernels` 直接调用 C 的三个 OpenMP 行内核。`src/hybrid_main.cpp` 复用 B 的 solve_mpi，支持 Sendrecv 和 overlap；C 不再维护第二套分布式求解逻辑。
- `src/c_hybrid_main.cpp` 现在只构建独立 OpenMP 入口；串行、MPI-only、OpenMP-only 和混合四个目标可按独立选项构建。
- 公共 CLI 增加可选 OpenMP kernel 选择；公共 JSON 增加 communication/kernel/driver/MPI 线程支持/OpenMP 版本。B 的 MPI-only variant 保持原值，避免破坏 B 原有采集器。
- C 采集器改用 B 的 MPI-only 程序，混合用新入口，核对实际通信方式、驱动来源及线程数。支持显式 `{ranks}` 的 launcher，避免重复添加进程参数。
- 更新正式矩阵，增加混合 sendrecv/overlap 配比对照；集群 launcher 留占位符，需核实资源、绑定、目标环境验收和工作量后启用。没有擅自登录、提交作业或编造集群数据。

## 实际验证结果

环境来自本机现有 Docker 镜像：Debian ARM64、GCC 12.2.0、OpenMPI 4.1.4、OpenMP 4.5、Python 3.11.2。它是本地 Linux VM，不是 Atlas/Vanda 或 x86_64 测量。

| 验证 | 实测结果 | 证据 |
|---|---|---|
| 全功能 Release CTest | 9/9 组通过 | results/C_1031/release_ctest.log |
| C OpenMP/混合完整场验收 | 19 配置，294/294 次数值案例执行；5/5 错误测试正确拒绝 | release_parallel_evidence.json / summary |
| B 独立 MPI 验证 | 124/124 次数值案例，4/4 错误测试正确拒绝 | release_mpi_evidence.json / summary |
| ASan/UBSan Debug | core、OpenMP contract、parallel acceptance 3/3 组通过；混合矩阵同为 294 次及 5 项错误测试 | sanitize_ctest.log、sanitize_parallel_evidence.json |
| 默认串行构建 | CTest 6/6 通过 | default_ctest.log |
| 仅 OpenMP 构建 | CTest 8/8 通过，包含独立线程验收 | openmp_only_ctest.log |
| 仅 MPI 构建 | ENABLE_MPI=ON、ENABLE_OPENMP=OFF 编译成功；2 rank overlap 小例子执行成功 | mpi_only_smoke.json |
| 新采集/汇总/绘图流程 | 串行、MPI 两种通信、OpenMP、混合两种通信，6 配置 ×（1 预热 + 3 重复）=24 次全部成功；汇总及图生成成功 | pipeline_smoke_evidence.json |
| 采集器/指标单元验证 | 6 个测试方法通过，覆盖 MPI/混合启动和失败样本排除 | experiment_metrics.log |

294 次验收包含 3 组独立 OpenMP 配置，以及 16 组混合入口的 rank/thread/kernel/communication 配置；并非 294 个不同数学问题。与 B 的 124 次及 sanitizer 的重复矩阵存在覆盖重叠，不相加宣称独立案例总数。相对独立有限步参考的最大逐点误差为 6.661338147750939e-16。

覆盖 sendrecv/overlap、1/2/3/4 ranks、实际 1/2/4 threads、非整除划分、每 rank 1/2 行、N=127、四类 RHS、奇偶迭代、K=0、收敛/未收敛退出及检查间隔。错误测试包含过多进程、非法 kernel/communication、N=0 和根进程输出失败。

ASAN_OPTIONS=detect_leaks=0 用于排除 MPI 运行时泄漏报告；没有 MPI runtime 泄漏、ThreadSanitizer 或任意输入正确性的声明。内核每次建立并行区，overlap 的内部/边界回调可能增加线程区启动开销；这里只确认正确性，不预设更快。

## 证据与复现

紧凑归档在 `docs/C/results/C_1031/`：保留每次命令、数值结果、独立误差/残差、判定和原始 stdout/stderr；完整 candidate/reference 场保留在本机被忽略的 build-c-integrated 与 build-c-sanitize-1031，可按 README 的 CTest 重新生成。`scripts/export_c_evidence.py` 提供相同归档入口。

测试时正处于 B 合并中的修改状态，基点不是最终提交。source_manifest 记录检查后快照，逐套验收保留自身 manifest，pipeline manifest 保留运行时源码哈希；Release 二进制哈希及实际编译命令一并归档，不用基点 commit 替代修改后的源码身份。

本地正确性使用允许超额订阅/无绑定设置；pipeline smoke 的 N=31、K=10 是流程验证，不用于扩展效率或“混合/overlap 更快”的结论。10/27 的性能结果对应旧 C 独立驱动，也不能与新后端数据混用。

## 主分支同步补充

本次完成后 main 更新至 `7729bfc`，已合入 B 并增加 A 的 Linux MPI 验收记录。C 已同步该提交，保留 A 的首次 MPICH 环境失败与 OpenMPI 成功证据。此次同步只增补 README 和 A 的验证归档，C 的 src/include/CMake/scripts/tests/configs 与已验收版本相同，无需将同一数值矩阵重复运行。A 的该记录验证 V0/V1/V3，不替代 C 的混合验收或团队人工审查。

## 下一步职责

- C：拿到真实 Atlas/Vanda 使用信息后，完成计算节点小作业、绑定核对和工作量校准，再采集强/弱扩展、配比和实际求解；更新图表、性能正文与最终 PDF。
- B：复核新 hybrid 入口的 FUNNELED、同步回调和布局，使用相同集成版本独立推进 MPI-only/通信/跨节点数据，交回完整原始目录。
- A：复核接口及独立验收结果，在目标环境重新验证，确认成员姓名学号、Canvas 截止时刻，完成最终提交包复现。

当前还缺真实集群访问、模块/队列/资源规则、成功作业、正式运行数据和团队人工审稿。具体接入材料见 [cluster_handoff.md](cluster_handoff.md)。C 的英文方法与设计草稿在 `report/source/C_integration_1031.md`；它不是最终 PDF，性能结论待实测后补充。
