# B_mpi_local 合并验证

合并输入：main 24ae1b4，B_mpi_local d590e2e。唯一冲突为 README，保留 A 的 Linux 验证与 B 的 MPI 说明。算法、MPI 实现、测试容差未改动；A 的 CI、验证脚本及历史日志未删改。

## 实际测试

Ubuntu 24.04 ARM64 容器，GCC 13.3.0，Open MPI 4.1.6，Release，ENABLE_MPI=ON：CTest **6/6 通过**，含 5 组非 MPI 测试及 MPI 矩阵；MPI 数值案例 **124/124**，错误案例 **4/4** 按预期处理。覆盖 V1 Sendrecv / V3 overlap、1–4 ranks、独立数学参考和直接串行完整网格对照。实际环境与紧凑逐案例证据见 [results/B_merge_linux](results/B_merge_linux/)。源码哈希随记录保存。

构建与测试命令：

```sh
cmake -S /src -B /evidence/build -DENABLE_MPI=ON -DCMAKE_BUILD_TYPE=Release
cmake --build /evidence/build -j 2
cd /evidence/build
ctest --output-on-failure -V
```

容器系统依赖：gcc g++ cmake make python3 openmpi-bin libopenmpi-dev。本次容器以 root 运行，设置 OMPI_ALLOW_RUN_AS_ROOT=1、OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1，并设置 OMPI_MCA_rmaps_base_oversubscribe=1 允许小规模正确性测试；这些不是集群性能实验设置。完整字段见 environment.txt。

## 保留的首次环境失败

首次使用 Ubuntu 的 MPICH 4.2.0/Hydra：非 MPI 5/5 通过，但多进程各自报告 ranks=1，导致 MPI 验收失败。环境日志显示 MPICH 使用 --with-pmix 构建，与 [MPICH 上游问题 #7064](https://github.com/pmodels/mpich/issues/7064) 记录的 Ubuntu 启动兼容性问题一致。首次失败的原始输出和 summary 保存在 mpich_failed，未覆盖或标成通过。

随后在新的容器用配套 Open MPI 开发库与启动器重新构建，全部通过。没有为通过测试修改算法、跳过案例或放宽容差。此结果只证明该 Linux 环境下 V0/V1/V3 的正确性，不代表 OpenMP V2、Atlas/Vanda 性能或所有 MPI 实现均已验证。默认 CI 仍验证串行构建，尚未扩展为 MPI CI。

本轮 AI 使用：Codex 协助合并、解决文档冲突、执行容器测试及定位 MPI 启动环境问题；组员人工代码审查仍需完成。
