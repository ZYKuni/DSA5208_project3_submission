# A_1027：比较工具与统一验收使用说明

日期：2026-10-27。以下命令均从仓库根目录执行；Python >=3.8，仅使用标准库。代码入口在 scripts/，阶段结果在 [results/A_1027](results/A_1027/)。

## 1. 完整网格比较

```sh
./build/poisson_serial --n 7 --mode fixed --iterations 5 --problem discrete-mixed --solution build/candidate.csv
python3 scripts/compare_grids.py --reference tests/fixtures/serial_mixed_n7_k5.csv --candidate build/candidate.csv --n 7 --report build/comparison.json
```

实际并行验收时，把 candidate.csv 换成待测程序在相同 N、问题、初值及迭代数下生成的场。

输入必须为三列 `global_i,global_j,u`，表头顺序固定，包含全部 `(N+2)²` 个点（含物理边界）；数据行可以任意排序。

检查：文件与 CSV 合法、坐标为整数且在 0..N+1 范围内、无重复/缺点、数值有限、四条物理边界符合约定，最后按坐标逐点比较。参考文件和候选文件都检查，不能因为两份文件存在相同缺点或边界错误而通过。

默认逐点通过条件：

```text
abs(candidate[i,j] - reference[i,j]) <= 1e-10 + 1e-10 * abs(reference[i,j])
```

`--atol`、`--rtol` 必须有限且非负；`--boundary-atol` 默认 0，要求物理边界恰为零。

指标覆盖完整网格：

- max_abs_error：最大绝对误差；worst_coordinate：一个最大误差坐标。
- mismatched_points：不满足逐点容差的点数。
- absolute_l2_error：误差向量 L2 范数。
- relative_l2_error：误差 L2 / 参考 L2。
- 参考范数为 0 时，相对误差输出 JSON null，l2_error_kind=absolute_zero_reference，另报绝对 L2；仍按逐点条件判断。
- L2 指标用于报告，通过门槛为所有点满足逐点容差，没有隐藏的第二套 L2 阈值。

退出码：0=PASS；1=FAIL（合法网格但数值不一致）；2=ERROR（输入、格式或容差错误）。stdout 输出 JSON，--report 可保存同一结果，不能覆盖输入 CSV。

该工具比较文件，不证明两份 CSV 的运行参数一致；运行参数及实际执行需要下面的统一入口验证。

## 2. 非对称独立案例

新增 `--problem discrete-mixed`，要求 N>=3，保持网格、双缓冲、零边界和零初值规则。

```text
x=j*h, y=i*h, h=1/(N+1)
u*(x,y)=sin(πx)sin(2πy)+0.35sin(2πx)sin(3πy)
λ(p,q)=4/h² [sin²(pπh/2)+sin²(qπh/2)]
f_h=λ(1,2)sin(πx)sin(2πy)+0.35λ(2,3)sin(2πx)sin(3πy)
```

这是离散已知解问题，f_h 随网格变化，用于验证，不作为新的真实数据任务。两个模态方向、频率和权重不同，可识别转置及两个方向的翻转。

独立参考包含两条路径：

1. 小网格稠密矩阵：从采样 u* 构造离散右端，再显式执行稠密矩阵 Jacobi。
2. 模态公式：每个模态 K 轮后的幅值为 `a*(1-ρ^K)`，`ρ=(cos(pπh)+cos(qπh))/2`。

两条 Python 路径都不调用 C++ 内核；串行导出场同时对照二者。有限步参考不是收敛已知解，不能把未收敛的场直接与 u* 按机器精度比较。

`tests/fixtures/manifest.json` 新增 N=3,K=1 与 N=7,K=5 的非对称夹具。旧问题及夹具保持有效。

## 3. 统一验收入口

```sh
python3 scripts/run_acceptance.py --exe build/poisson_serial --config configs/acceptance_serial.json --output build/acceptance-local-01
```

输出目录必须尚不存在，重跑请换目录名，以免复用上次成功但本次未生成的结果。入口是小规模正确性工具，限制 N<=255，不用于性能实验。

每个 case 必须填写 name、n、problem、mode、iterations；tol 默认 1e-10，check_every 默认 1，expected_exit 默认 0。converge 可预期退出码 2，验证达到上限但未收敛的情况。name 只允许字母、数字、下划线和连字符，且必须唯一。

顶层包含 schema_version=1、timeout_seconds、comparison、launch 和非空 cases。未知字段、重复 JSON 键及非有限参数会被拒绝，避免拼写错误静默生效。

执行顺序：

1. 记录规范化配置、可执行文件/配置/验证工具的哈希，以及 Git 和工作区状态。
2. 使用 argv 数组启动程序，不经 shell 拼接；每个案例独立输出路径。
3. 保存命令、环境覆盖、超时设置及 stdout/stderr。
4. 核对退出码、单个 JSON 对象、问题参数、实际步数、检查次数、停止原因和进程/线程元数据。
5. 按案例和实际步数生成独立有限步参考，比较整个场。
6. 从导出场独立重算残差；收敛模式还检查是否明显错过前一个检查点。
7. 保存逐案例 verdict 并继续剩余案例，汇总所有失败。

程序报告与独立残差复算比较采用 rel_tol=1e-6、abs_tol=1e-12，以容纳浮点运算顺序差异。收敛边缘交叉核验的余量为 max(1e-13,tol*1e-6)，不改变程序自身停止阈值。默认案例求解阈值为 1e-10 或 1e-11。

每个案例都有 command.json、stdout.log、stderr.log、verdict.json；执行和解析成功后还保存 result.json、reference.csv、candidate.csv、comparison.json、independent_residual.json。失败可能发生在后续文件生成之前，以原始日志和 verdict 为准。

入口退出码：0=所有预期行为通过；1=至少一个案例失败；2=配置/入口错误。案例预期退出码为 2 且行为正确时，整套验收可以通过。

默认 14 个案例覆盖单内点、两行、零步、奇偶轮、混合模态、不同检查间隔、收敛、零右端和预期未收敛。原串行验证另有更细的参数错误检查。

## 4. B/C 接入约定

待测程序需支持串行版同名参数和 JSON schema。stdout 仅输出一个完整 JSON 对象，MPI 由一个 rank 输出；调试信息走 stderr。--solution 应输出回收后的完整全局 CSV，不让多个 rank 写同一路径。

launch 示例仅说明接口，未实际验证 MPI：

```json
{
  "prefix": ["mpiexec", "-n", "3"],
  "extra_args": [],
  "env": {"OMP_NUM_THREADS": "2"},
  "expected_ranks": 3,
  "expected_threads": 2
}
```

复制 acceptance_serial.json 修改 launch，--exe 指向 B/C 程序即可。extra_args 可传实现版本选项，但不能覆盖案例参数或输出路径。

- 3 ranks 时 N=1/2 不是首版支持的成功配置，应留在单独的 1-rank 配置中；3-rank 配置使用 N>=3。过多 ranks 的负面测试由 B 自身测试覆盖，本入口案例只支持预期退出码 0/2。
- OpenMP-only 可留空 prefix，按实际线程数设置环境和 expected_threads。程序应报告实际线程数。
- 混合版先通过独立 MPI/线程测试再集成。元数据核对不能独立证明真实运行的进程/线程数量。
- 新问题已加入公共 Problem 枚举和 RHS 生成器；B 若使用独立参数解析器，需加入 discrete-mixed，不能静默跳过案例。
- mpiexec/srun 等命令按平台调整；尚无实际集群启动验证。POSIX 超时会终止本地启动进程组，跨节点作业回收仍由集群调度器管理。

B/C 不需修改比较工具或数学 oracle。引入其他问题时需要独立可核验的参考，不能把待测输出自身作为 oracle。

## 5. 工具本身的测试

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
(cd build && ctest --output-on-failure)
```

四组 CTest：core_contract、serial_validation、grid_comparison_contract、acceptance_contract。后两组分别包含 14 和 10 个 unittest 方法，部分方法覆盖多个子案例。

tests/fault_injection_launcher.py 是故意破坏输出的测试夹具，只用于检查验收器能拒绝超时、错误退出、错误 JSON、缺文件、转置、错误元数据/残差/步数等情况，不是 MPI 实现或正式求解器。
