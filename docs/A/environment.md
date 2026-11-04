# 环境记录

## A 第一阶段本地开发（2026-10-24）

- OS/架构：Darwin / arm64。
- C++：Apple clang 17.0.0（clang-1700.3.19.1），C++17。
- CMake：4.1.1；Unix Makefiles generator。
- Release 编译参数：`-O3 -DNDEBUG -std=c++17 -arch arm64 -Wall -Wextra -Wpedantic`。
- CMake 测试找到的 Python：3.12.11；验证脚本也只使用 Python >=3.8 标准库。
- MPI/OpenMP：本阶段未链接或运行。
- 机器用途：开发与正确性验证，没有采集课程性能数据。
- 阶段来源：基于 main 的初始提交 18f0c56 开发；实际源码快照 SHA256 见 `results/raw/a_stage1/source_manifest.json`。

构建目录不提交 Git。重复执行 README 命令可生成新的测试结果；小幅浮点末位与耗时差异不应直接视为失败。

## Atlas/Vanda

待 B/C 实测填写：平台、计算节点 CPU、物理核数、内存、节点数、调度器/队列、MPI/编译器/OpenMP runtime、绑定配置、实际构建命令、作业 ID。不得从本地环境推断集群参数。

## 依赖声明更新（2026-10-27）

完整要求见 [dependencies.md](dependencies.md)，Python 包声明见根目录 requirements.txt（当前无第三方包）。CMake 已显式要求测试解释器 Python >=3.8。10/24 的 source_manifest 保留为历史证据，不代表 10/27 修改后的全部文件。

2026-10-27：文档按成员归档至 docs/A、docs/B、docs/C；团队完整分工保留于 docs 根目录。历史 source_manifest 中的文档路径与哈希仍对应当时快照，不随本次目录整理改写。

## A_1027 第二阶段（2026-10-27）

在相同本地 C++/CMake 工具链上完成 Release 和 ASan/UBSan 的四组测试。记录位于 docs/A/results/A_1027/，每次正式验收的可执行文件与脚本哈希见 run_manifest.json。该阶段源码尚含工作区修改，不能用起点 commit 单独表示实际运行版本；完整源码快照见本阶段 source_manifest.json。

## A Linux 验证（2026-10-31）

实际运行于干净 Ubuntu 24.04.5 LTS / aarch64 容器，Docker Linux VM 内核 6.10.14-linuxkit；GCC/G++ 13.3.0、CMake 3.28.3、Python 3.12.3、Make 4.3、glibc 2.39。Release CTest 4/4、统一验收 14/14 通过。详见 [完整记录](A_1031_linux.md) 和 results/A_1031_linux/verification/environment.txt。未验证 x86_64 CI 或 Atlas/Vanda 性能。

## P0 双模式 CI

已核实 GitHub 工作流 41186406666：Ubuntu 24.04.5 x86_64、GCC 13.3.0、CMake 3.31.6、Python 3.12.3、Open MPI 4.1.6。串行 CTest 5/5、MPI CTest 6/6，通过 124 数值/4 错误 MPI 案例，两模式独立验收各 14/14。对应源码 44388a4；原始环境及证据见 [P0 完成记录](P0_completion.md)。

## A_1104 四模式与交付复现

本轮四模式本地隔离验证和 GitHub x86_64 CI 均通过；构建与包解压复验分开保留。具体工具链、390 次混合执行、Vanda 独立审计和报告依赖记录见 [完成说明](A_1104_completion.md)。原 Vanda 版本与时间样本不变。
