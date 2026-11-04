# A_1027：第二阶段工作说明与实际结果

日期：2026-10-27。工作分支 A_1027，起点 4a30b9e，与远程同名分支对齐后开发。三个指定任务均完成；本阶段是 A 的本地正确性工作，不含 B/C 的 MPI/OpenMP 实现或集群性能测量。

## 交付清单

| 工作 | 交付 |
|---|---|
| 完整网格比较 | scripts/compare_grids.py；坐标、完整性、有限值、物理边界、逐点容差和 L2 报告 |
| 非对称独立案例 | discrete-mixed；scripts/validation_oracle.py；两份新夹具；稠密矩阵/模态双路径验证 |
| 统一验收入口 | scripts/run_acceptance.py；configs/acceptance_serial.json；命令、输出、参考场、独立残差和失败原因 |
| B/C 交接 | [工具与接入指南](A_1027_tools.md) |
| 阶段证据 | [结果目录](results/A_1027/)，不改写第一阶段历史结果 |

## 构建与测试

本地 Darwin arm64、Apple Clang 17、CMake 4.1.1。CTest 使用 CMake 找到的 Python 3.12.11；正式入口的解释器版本见 run_manifest。没有安装新 Python 包。

| 验证层 | 实际结果 | 证据 |
|---|---|---|
| Release CTest | 4/4 组通过 | [日志](results/A_1027/release_ctest.log) |
| Debug + ASan/UBSan | 4/4 组通过 | [日志](results/A_1027/sanitizer_ctest.log) |
| 串行数值/运行语义 | 37 个案例通过，另有 16 个非法 CLI 案例正确拒绝 | [摘要](results/A_1027/serial_validation_summary.json)、[表格](results/A_1027/serial_validation.csv) |
| 网格比较工具 | 14 个 unittest 方法通过，含多个错误子案例 | Release 日志的 grid_comparison_contract |
| 统一入口工具 | 10 个 unittest 方法通过，含失败注入和超时 | Release 日志的 acceptance_contract |
| 正式统一验收 | 14/14 案例通过 | [汇总](results/A_1027/acceptance/summary.json) |
| 保存的错误网格演示 | 7/7 故意错误被检出 | [故障汇总](results/A_1027/fault_detection/summary.json) |

计数存在覆盖重叠，不能相加称为独立样本数量。sanitizer 只覆盖已执行的 C++ 路径，不保证任意未测试输入均正确。

## 非对称案例结果

采用 `u*=sin(πx)sin(2πy)+0.35sin(2πx)sin(3πy)` 的离散已知解。

- N=7，K=5：相对独立有限步参考的最大绝对误差为 **2.220446049250313e-16**，相对 L2 为 **2.636889505532439e-16**。
- N=15，收敛阈值 1e-11，每 7 轮检查，实际执行 **518** 轮。
- 从完整场独立重算的相对残差为 **7.656596877449883e-12**。
- 相对收敛已知解 u* 的最大绝对误差为 **1.0291545393670276e-11**。
- 全部 14 个正式验收案例中，相对各自有限步数学参考的最大逐点误差不超过 **6.661338147750939e-16**。

有限步参考误差与收敛解误差不同：前者检查第 K 步是否执行正确，后者还包含尚未消失的迭代误差，不能将前者当作求解已达到机器精度。

证据：[N=7,K=5 比较](results/A_1027/acceptance/mixed_k5/comparison.json)、[N=15 输出](results/A_1027/acceptance/mixed_converged/result.json)、[独立残差](results/A_1027/acceptance/mixed_converged/independent_residual.json)。原连续正弦的二阶加密误差比仍为 4.023264931895842、4.005791291992650，旧问题行为保持一致。

## 错误检出能力

从真实 N=7,K=5 混合场构造故意错误：

| 错误 | 比较器结果 | 最大绝对误差 / 原因 |
|---|---|---|
| 行列转置 | FAIL，退出 1 | 1.0156538002961688 |
| 上下翻转 | FAIL，退出 1 | 1.278673976130537 |
| 左右翻转 | FAIL，退出 1 | 0.6663749778158707 |
| 缺少一个点 | ERROR，退出 2 | 完整性检查失败 |
| 重复一个坐标 | ERROR，退出 2 | 唯一性检查失败 |
| 内点 NaN | ERROR，退出 2 | 非有限数值 |
| 物理边界非零 | ERROR，退出 2 | 零边界约定被破坏 |

这些 FAIL/ERROR 是预期拒绝，说明工具成功识别故意错误，不是阶段测试失败。故意错误文件位于 fault_detection/，不能作为科学计算结果使用。

## 验证边界与下一步

- 启动器 argv/环境传递已用本地测试包装脚本验证，未声称 MPI/OpenMP 已通过。
- 非对称已知解提高方向错误检出能力，不代表任意 RHS 的完整证明。
- 日志中的耗时没有用于性能曲线或 Atlas/Vanda 结论。
- B/C 接入后还需真实 1/多 rank × 1/多 thread、非整除划分、窄子域、全局归约及跨节点验证。
- 修改在 A_1027 工作区内。运行时 base commit 与 dirty 状态记在 run_manifest，实际源码哈希见本阶段 source_manifest；不冒称运行的是已提交的干净版本。

下一步由 B 接入全局 CSV/统一 JSON 和 MPI 驱动，C 接入线程内核与真实线程元数据；A 可直接用本入口复核输出。
