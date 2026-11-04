# B/C 集成兼容性审查（P0）

## 审查范围与结论

基准 main：7729bfc（B d590e2e 已合入）；C：origin/codex/c-openmp-integration 的 5e29ae6。本次阅读源码与配置，没有合并 C，也没有把 C 的历史测试视为统一驱动测试。

## 2026-10-31 复核：C 已完成集成（a1ee628）

本文下方是对 5e29ae6 的审查。此后 C 推送 origin/c-openmp-integration（a1ee628，已含 main 7729bfc），与本文件所在分支 `git merge-tree` 无冲突。本节逐项对照该提交的源码，**未运行** C 的测试，其 294/294 等数字仍只是 C 的记录（docs/C/C_1031_handoff.md）。

| 审查要求 | a1ee628 状态 | 判定 |
|---|---|---|
| 四种构建相互独立 | CMake 分别查找 MPI/OpenMP，已无互相绑定；poisson_hybrid 仅在两者都开时构建 | 已满足（静态） |
| 统一 solve_mpi | src/hybrid_main.cpp 把三个 OpenMP 内核注入 B 的 LocalKernels；c_hybrid_main.cpp 只剩无 MPI 入口 | 已满足 |
| 线程真实性 | 关闭动态团队，探测实际团队大小，Allreduce 检查各 rank 一致，保持 FUNNELED | 已满足 |
| 公共 CLI/JSON | 增加 --kernel 及 communication/kernel/driver/mpi_thread_provided/openmp_version；B 的 variant 未改名 | 已满足 |
| 采集器 | run_experiments.py 校验 variant、communication、driver；汇总按 study+label 分组，不会合并两种通信 | 已满足，label 必须写明通信方式 |

**方案变更：** 下文第 3 节建议的 mpi-openmp-sendrecv/overlap 未被采用。C 使用单一 variant `mpi_openmp`，再用 communication 字段区分。上述采集校验足以防止混淆，A 决定接受现状，撤销该命名建议，避免再次改动已验收的接口。

**仍未解决，转入 P1：**

1. 覆盖缺口：C 的 16 组混合配置缺少计划要求的 1 rank×4 threads、2 ranks×1 thread、3 ranks×1 thread（OpenMP 内核）。
2. 身份歧义：`poisson_hybrid --kernel serial` 与 poisson_mpi 输出相同的 variant 和 driver（b-mpi），只能靠 openmp_version 或程序哈希区分。正式实验不要用该组合，或由 C 改 driver 取值。
3. CI 缺口：现有 serial/mpi 两个 job 都不开 ENABLE_OPENMP。C 合入后需增加 hybrid job，否则 CI 不覆盖线程内核。
4. 独立验收：A 尚未在合并后的版本上重跑混合矩阵；C 的证据基于合并中的工作区，B/C 人工复核也未完成。

以下为 5e29ae6 的原审查内容，保留作历史记录。

## 5e29ae6 审查结论

**结论：C 三个 OpenMP 内核可按现有函数签名接入 B 的 LocalKernels；正式 MPI/混合路径建议统一在 B 的 solve_mpi 上。不能直接套用 C 的 CMake 或把 C 驱动的输出名称替换后当作同一版本。** 下述是下一阶段明确的实现方案，不代表本轮已实现。

## 已核查的兼容性

| 项目 | 源码核查结果 | 集成决定 |
|---|---|---|
| 行范围与网格 | B LocalKernels 与 C kernel_openmp.hpp 的 update/residual/norm 参数和返回类型匹配；均采用 [begin,end)，本地行 + 全局 row_offset；OpenMP 内核无 MPI、无缓冲交换 | 保留 B 网格和循环边界，直接注入三个 C 函数；加入编译期类型检查及运行期局部行测试 |
| 双缓冲与通信 | B 在 overlap 模式先启动收发、算内部行、等待全部请求、算边界行；C 更新函数返回前结束 parallel for，有隐式同步 | 保留 B 通信生命周期；线程核不访问 halo 接收缓冲作为写目标，不把 MPI 调用移入线程区 |
| 残差与停止 | 两驱动均先更新当前解 halo，再归约局部残差平方和；zero RHS 使用绝对范数；fixed 不提前停止，converge 有初始检查 | 统一复用 B solve_mpi；对零 RHS、K=0、check-every>1、未收敛退出重新验收 |
| 计时 | 两者均在初始化/RHS 范数后开始；同步起点；包含迭代、halo、计划内归约；时间取最大 rank；最终诊断/输出在计时后 | 数学计时口径大体一致，整合后按 B 实现冻结；C 历史时间不能直接移作新驱动基线 |
| MPI 线程支持 | 两驱动均要求 FUNNELED，MPI 在初始化线程调用；C 动态线程关闭，并探测真实团队大小、检查 rank 间一致性 | 将 C 团队探测/一致性检查迁入统一驱动；保持 B 初始化与 abort 处理 |
| CLI | B 公共 cli 支持 --communication，C 独立解析支持 --kernel；共同数值参数相近但错误信息不同 | 在公共 CLI 显式支持 kernel 选择，保留原有 B 参数和默认行为；同步修改错误消息断言 |
| JSON | B 的 variant 为 mpi-sendrecv/mpi-overlap；C 为 mpi/mpi_openmp；C 另有 mpi_thread_provided/openmp_version | 保留既有字段语义；新增混合 variant 与元数据，不能静默改名破坏采集器 |
| 全场回收 | 两者按行 Gatherv，只有 root 输出；完整场 int 计数上限检查不同（C 更保守） | 统一使用 B gather_solution/write_solution；保留超限/写文件失败测试 |

C 内核通过 OpenMP reduction 求和，与串行归约顺序不同属于预期；数值通过标准仍使用 A 既定混合容差，不要求逐位相同，也不因差异直接放宽标准。

## 必须解决的集成项

### 1. 构建选项不能相互绑死

C 分支含 `if(ENABLE_MPI AND NOT ENABLE_OPENMP) FATAL_ERROR`，会破坏已可用的 B MPI-only 构建。必须删除该依赖关系，独立查找 MPI/OpenMP。

| ENABLE_MPI | ENABLE_OPENMP | 预期可执行目标 |
|---|---|---|
| OFF | OFF | poisson_serial；不查找 MPI/OpenMP |
| ON | OFF | poisson_serial、poisson_mpi；不要求 OpenMP |
| OFF | ON | poisson_serial、poisson_openmp；不要求 MPI |
| ON | ON | 上述目标和 poisson_hybrid |

保留 B 的 cli.cpp/decomposition.cpp、test_decomposition、mpi_validation；增加 C 的线程核、线程单测和实验统计单测。不要用任意一方 CMake 整份覆盖另一方。

### 2. 正式 MPI 路径统一，保留必要的独立线程入口

- poisson_mpi 继续默认串行局部核，输出和 V1/V3 行为保持兼容。
- poisson_hybrid 使用 B solve_mpi + C LocalKernels，并支持 sendrecv/overlap。可将 B mpi_main.cpp 扩展为共享驱动或抽出公共驱动函数，避免复制求解循环。
- poisson_openmp 保留无 MPI 的线程路径；首轮可继续使用 C 驱动的非 MPI 路径，必须明确其来源，随后逐步收敛公共 CLI/输出逻辑。
- C 的旧 MPI 驱动不再作为正式性能主入口；历史源码在 Git 中可追溯，历史结果不改写。
- 小子域不会有线程性能收益，但必须正确；B 对 rows=1/2 的分支不可删掉。

### 3. 输出与实验工具约定（建议冻结方案）

原有 `mpi-sendrecv`、`mpi-overlap` 不改名；新增 `mpi-openmp-sendrecv`、`mpi-openmp-overlap` 区分混合通信。可额外增加 kernel/communication/driver 字段，保持 schema_version=1 的现有字段语义兼容；若改变必填字段语义，再升级 schema 并同时改读者。

C run_experiments.py 当前限制 variant 为 serial/mpi/openmp/mpi_openmp，且自动给非串行程序加 --kernel；B run_mpi_experiments.py 要求精确匹配 mpi-sendrecv/mpi-overlap。**仅改求解器会使采集器失败。** 下一阶段需：

1. C 的采集配置区分“研究类别”和“程序实际 variant”，显式加入 communication、driver/版本映射；命令生成可选择统一驱动，不能把 mpi_openmp 静默当作某一种通信。
2. 保留 B 采集器对已有 V0/V1/V3 配置的兼容；统一汇总通过 run_id、variant、driver、源码哈希识别来源。
3. 对旧日志只读，迁移现有测试配置和未来实验模板；统计测试核对失败抑制、重复计数和基线不变。

### 4. 测试需要扩展而非替换

复用 B 124 次 MPI 数值执行和 4 个错误案例；保留 C 的 OpenMP 内核/实验统计测试。C tests/test_parallel.py 当前依赖 --kernel、旧 variant 和旧错误消息，必须与统一驱动同步更新。

增加 Sendrecv/overlap × 实际线程 1/2/4 的有代表性组合，覆盖 rank 1/2/3、非整除、每 rank 1–2 行、奇偶迭代、mixed/zero、收敛/未收敛、线程环境和失败退出。逐项核对完整网格、独立残差、实际 rank/thread、退出码和超时。测试执行次数不能相加宣称为不同数学问题数。

## 文件级实施清单与交接

| 文件/模块 | 下一阶段修改 | 复核责任 |
|---|---|---|
| CMakeLists.txt | 四种独立构建、保留两方测试，混合目标显式链接 OpenMP 和 MPI | A 集成，B/C 复核 |
| include/cli.hpp、src/cli.cpp | kernel 能力选项、通信参数、帮助与统一 JSON 元数据；串行默认不变 | A/C |
| src/mpi_main.cpp、include/mpi_solver.hpp | 选择 LocalKernels、关闭动态团队、检查实际线程数一致性，保持 FUNNELED | B/C；A 验收 |
| C 的 kernel_openmp.hpp/.cpp | 引入现有实现，保留行范围契约与检查 | C，A/B 复核 |
| tests/validate_mpi.py、C test_parallel.py/test_openmp.cpp | 保留 MPI 回归，适配并补混合矩阵，避免双份重复 oracle | A |
| B/C 两套实验配置/采集器 | 兼容实际 variant、通信方式和驱动来源；历史数据不改标签 | C 主责，B/A 复核 |
| README、设计与交接文档 | 写明正式入口和四种构建；修正 C 交接文档的旧“未推送”状态 | A 汇总，全员确认 |

## 完成判定与风险边界

本轮 P0 完成的是集成设计审查和 MPI CI 接入，不是 C 合并验收。下一阶段必须满足：四种构建通过；原有 V0/V1/V3 回归通过；统一驱动混合测试通过；采集器不混淆旧新 variant；B/C 人工确认线程/通信设计；保存新源码哈希和日志。当前没有发现需要重写数值算法的接口障碍，但静态兼容性不等于运行正确性。
