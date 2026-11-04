# A → B/C 第一阶段交接

状态：A 的接口、V0 和本地验证已就绪；2026-10-27 增加 [完整网格比较/非对称验证/统一验收入口](A_1027_tools.md)，实际结果见 [阶段记录](A_1027_results.md)；尚无 B/C 人工确认。开发入口为 README 的 CMake/CTest 命令。

## B 可立即开始

- 使用 `Grid(N, rows, offset)` 存储一个子域，`initialize_rhs` 根据全局坐标生成本地右端。
- 自行实现按行均衡划分及余数分配，不把完整网格广播到每个 rank。
- `jacobi_rows` 可直接当作 MPI-only 版本内核；首版 `Sendrecv` 实现保持数学逻辑不变。
- 收敛判断：全局平方和 → sqrt → 相对/绝对残差指标，所有 rank 同时停止。
- 所有当前解 halo 更新完毕后才算残差；输出完整场时按全局行偏移回收。
- 非阻塞版本内部行可取 `[2,rows)`（仅 rows>=3）；剩余边界行覆盖所有拥有行且不重复。rows=1/2 单独处理。

## C 可立即开始

- 按 `include/kernel.hpp` 的同一行范围语义实现线程内核，可命名 `jacobi_rows_openmp`，避免与串行符号冲突。
- `next` 每个格点只有一个线程写入，old/rhs 只读；不在内核中交换缓冲或调用 MPI。
- 为残差平方和使用 OpenMP reduction；浮点归约顺序变化用既定容差验证。
- B 的驱动负责初始化 MPI、halo 和全局停止；首次集成将 MPI 调用置于线程区之外。
- 实验汇总需要补充集群、job ID、commit/源码状态、编译器、节点与线程绑定等字段。

## 参考数据

`tests/fixtures/manifest.json` 列出每份完整网格 CSV 的参数及生成命令；`tests/fixtures/serial_n3_k1.csv`、`serial_n3_k2.csv` 是一轮/两轮夹具；`serial_n7_k5.csv` 可用于非整除划分。CSV 包含 N+2 行 × N+2 列的物理网格，采用 0 起始全局坐标，17 位有效数字。

这些文件已通过独立稠密矩阵 oracle 检查。未来并行版应按 manifest 参数产生完整场，比较所有坐标，不仅比较 checksum 或残差。不得将参考文件加载后直接当作程序结果。

## 后续共同验收

1. 1 rank/1 thread 与 V0 相同。
2. 多 rank/1 thread、1 rank/多线程、多 rank/多线程。
3. N=7 配 2/3 ranks 等非整除划分，N=1/2 的窄子域。
4. K=0/1/2/5，核对初始状态与奇偶轮交换。
5. 两种停止模式、zero RHS、check-every>1、未收敛退出。
6. Atlas/Vanda 的实际作业及环境记录。

当前仅第一个条目的 V0 参考已提供，没有任何 MPI/OpenMP 配置被标为通过。

## B 合入后的当前交接状态

main 7729bfc 已合入 B 的 V1/V3，合并后 Linux/Open MPI 验证通过，见 [合并验证](B_merge_validation.md)。上文“B 可立即开始”和“尚无 MPI 配置通过”描述第一阶段历史状态，不再代表当前进度。

C 的远端分支 codex/c-openmp-integration（5e29ae6）已有线程内核、独立混合驱动和本地测试材料，尚未整合进当前 main。A 下一步优先审查 B/C 驱动与构建选项、补齐 MPI CI，再验收统一混合版本；详见 [更新后的下一阶段计划](A_next_steps_after_main_sync.md)。

## A_1104 当前状态

B/C 已整合，Vanda 数据与正式 PDF 已交付。A 完成四模式与新增混合组合验证、数据审计、报告/包复现，当前交付入口见 [完成记录](A_1104_completion.md) 和 [提交清单](Submission_checklist.md)。上文各阶段待办仅描述当时状态。
