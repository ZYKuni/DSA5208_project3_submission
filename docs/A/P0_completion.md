# A P0 完成记录

整理日期：2026-11-01。实际运行时间以日志 UTC 为准（本地和远端运行均在 2026-10-31）。代码/审查提交已由期间的外部操作保存并推送为 44388a4e29fb9a6650644dfe513be52a3c557c71，当前分支 A_1031；本轮没有再次提交或推送。本文和新增归档是该提交的补充证据。

## P0-1：B/C 集成审查完成

见 [BC_integration_review.md](BC_integration_review.md)。审查 B d590e2e（已入 main 7729bfc）与 C 5e29ae6，确认三个线程内核签名可接入 LocalKernels；给出构建四模式、正式驱动、CLI/JSON、线程数、计时、实验采集映射和测试迁移的文件级清单。

采用的下一阶段建议：以 B 的 MPI 求解循环和通信实现接入 C 线程内核；保留无 MPI 的线程入口。C 当前 MPI 依赖 OpenMP 的构建限制、两套 variant 命名和采集器硬编码必须同步处理。未合并 C；静态审查结论不等同于统一混合版本已运行通过。团队人工复核仍待完成。

## P0-2：MPI CI 接入并实际验证完成

.github/workflows/linux-gcc.yml 现在包含 serial/mpi 两个独立矩阵任务：Ubuntu 24.04、GCC Release，MPI 任务安装配套 Open MPI 库和启动器，显式启用 ENABLE_MPI；fail-fast=false，单 job 15 分钟，artifact 保留 30 天，失败也上传。

scripts/verify_linux.sh 兼容原单参数用法，新增第二参数 serial/mpi。入口保存环境、源码/程序哈希、构建和 CTest 日志、统一验收结果。EXIT trap 将 MPI 原始运行目录及 CTest Testing 目录移出被排除的 build 区域，失败/超时尚无 summary 时也保留已有证据。

```sh
bash scripts/verify_linux.sh build-linux-serial serial
bash scripts/verify_linux.sh build-linux-mpi mpi
```

目录必须不存在。MPI 模式面向 Open MPI；先安装 openmpi-bin/libopenmpi-dev。CI 的 oversubscribe 与不绑核设置仅为小规模正确性检查，不能据此形成性能结论。

## 实测结果与来源

| 环境 | 串行 CTest | MPI CTest | MPI 数值/错误案例 | 独立串行统一验收 |
|---|---|---|---|---|
| Ubuntu ARM64 容器，GCC 13.3.0、CMake 3.28.3、Open MPI 4.1.6 | 5/5 | 6/6 | 124/124；4/4 按预期处理 | 两模式各 14/14 |
| GitHub Ubuntu x86_64，GCC 13.3.0、CMake 3.31.6、Open MPI 4.1.6 | 5/5 | 6/6 | 124/124；4/4 按预期处理 | 两模式各 14/14 |

远端对应提交 44388a4 的 [push 工作流 41186406666](https://github.com/ZYKuni/NUS_DSA5208_project3/actions/runs/41186406666) 已完成且 conclusion=success；serial job 124494112023、mpi job 124494112176 均成功。另查询到同提交 PR 工作流成功；本次归档选择上述 push 运行，不混合不同运行证据。

归档位于 [results/P0_ci](results/P0_ci/)：

- local_arm64：本轮两个共用入口的真实测试日志、环境、源码哈希、统一验收与 MPI 紧凑逐案例证据。
- github_x86_64：下载 artifact 中的环境、编译/CTest、验收摘要和 MPI 逐案例 evidence；run/jobs/artifacts 元数据及下载 ZIP 的 SHA256/选取文件清单。原始 ZIP 留在忽略的 build-p0-ci/remote 中，不重复提交全部网格。原始完整 artifact 仍受 GitHub 30 天保留期限制。
- entrypoint_fault_test：独立故障注入；用临时 ctest 替身返回 23，检查退出码和原始 stderr 被保存，并核对重复目录/非法模式被拒绝。这不是求解器正确性测试，不计入上表案例数。

本轮核对远端 artifact 的全部 source_manifest 哈希与当前源码一致。时间/绝对路径保留原值，源 manifest 不因归档位置或后续文档更新而改写。跨架构通过只支持当前小规模正确性结论，不替代 Atlas/Vanda 的真实性能数据，也不证明 C 混合驱动已整合。

## 下一阶段

两项 P0 的代码/审查、共用入口测试与远端 CI 证据已齐。下一项是按审查清单开展 B/C 混合集成及四种构建验收，同时撰写算法/正确性正文；不需要再次从零构建 MPI 验收工具。
