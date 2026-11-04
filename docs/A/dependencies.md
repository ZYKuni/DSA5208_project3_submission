# 依赖规划与验证边界

审查日期：2026-10-27。依据当前 CMake、C++ includes、Python imports 和 README；不是对未来全部功能的依赖锁定。

## 当前必须满足的环境

| 组件 | 要求 | 使用范围 | 验证情况 |
|---|---|---|---|
| C++ 编译器及标准库 | 支持 C++17 | 编译串行内核、程序、C++ 测试 | 本地 Apple Clang 17 已验证；未声称 GCC/Linux 已验证 |
| CMake | >=3.16 | 构建配置与 CTest 注册 | 本地 4.1.1 已验证；最低版本未单独实测 |
| 原生构建工具 | 所选 CMake generator 对应的 Make 或 Ninja 等 | 执行编译 | 本地 Unix Makefiles 已使用；不要求同时安装多个工具 |
| Python 解释器 | >=3.8，仅 BUILD_TESTING=ON 时必需 | 独立数值验证 | 本地 CMake 选用 3.12.11；3.8 下限未单独实测 |
| Python 第三方包 | 无 | 当前测试只用标准库 | 已检查实际 imports；requirements.txt 有意只保留注释 |
| sanitizer runtime | 可选，由兼容的 Clang/GCC 工具链提供 | ENABLE_SANITIZERS=ON 时使用 | 本地 Clang 地址/未定义行为检查已验证 |

`requirements.txt` 只管理 Python 第三方依赖，不能安装 C++ 编译器或声明 Python 解释器版本。C++17、CMake 下限、Python 下限分别由 CMake 配置约束。仅构建程序可使用 `-DBUILD_TESTING=OFF`，无需 Python 或 pip。

README 的测试命令采用 `(cd build && ctest --output-on-failure)`，避免依赖较新 CTest 的 `--test-dir` 选项。

## 当前复现步骤

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 2
(cd build && ctest --output-on-failure)
```

若希望明确指定验证解释器，可配置：

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$(command -v python3)"
```

没有第三方 Python 包，无需创建虚拟环境或运行 pip。需要与自动化统一入口时，`python3 -m pip install -r requirements.txt` 也是合法的空依赖安装步骤；它不是构建项目的前置条件。

## 后续阶段的依赖安排

| 阶段 | 候选依赖 | 引入条件与负责人 |
|---|---|---|
| B：MPI | 目标集群提供的 MPI 实现、C++ wrapper 与 launcher | B 确认 Atlas/Vanda 实际模块和版本后，通过 CMake 查找 MPI 并补运行记录；当前不指定未验证版本 |
| C：OpenMP | 与 C++ 编译器兼容的 OpenMP runtime | C 通过 CMake 查找 OpenMP，验证线程与绑定；当前不假定系统 Clang 已自带可用 OpenMP |
| C：性能绘图 | 可能需要 matplotlib；其他包按实际使用引入 | 绘图脚本落地后新增单独的 requirements-analysis.txt，记录并验证精确版本，避免让基础正确性测试依赖绘图库 |
| 最终复现 | 集群工具链、模块、编译选项、Python 分析环境 | B/C 提供实测版本，A 汇总最终可复现说明 |

C++ MPI 路线不需要为了项目名称安装 `mpi4py`；OpenMP 也不是需要在此文件中列出的 Python 包。当前没有使用 NumPy、pandas、pytest，不为它们添加占位版本。

## 版本与变更规则

1. 依赖声明与实际代码同时更新，不将无关个人环境的完整 pip freeze 作为项目依赖。
2. 引入第三方 Python 包时明确直接依赖和用途；为正式分析环境保存验证过的精确版本及传递依赖快照，同时注明 OS/架构和 Python 版本。
3. 系统工具链记录在 environment.md，采用目标平台实际可用版本；不能仅凭版本号推定不同集群工具链可混用。
4. 依赖修改后至少完成配置、构建、CTest；MPI/OpenMP 引入时还需对应的真实并行测试。
5. 现有 results/raw/a_stage1/source_manifest.json 是 10/24 的历史快照；本轮新增依赖文档和 Python 版本约束不回写该历史证据。

## A_1027 扩展（2026-10-27）

新增比较器、验收入口和错误注入测试仍只使用 Python 标准库（包括 unittest、hashlib、signal、subprocess 等），requirements.txt 仍无第三方包。统一入口的进程组超时回收面向本地 POSIX 环境；实际集群启动与作业管理需 B/C 实测。

## Linux 验证（2026-10-31）

已在 Ubuntu 24.04 ARM64 上实际安装 GCC/G++、CMake、Make、Python3 并通过所有测试；精确版本见 [Linux 验证记录](A_1031_linux.md)。新增入口依赖 Bash 和 Linux 常用系统工具；Git 用于来源记录。Python 仍仅使用标准库，无需 pip 依赖变更。Docker 仅用于可选的干净容器复现，Linux 原生或 CI 运行脚本不需要 Docker。

## P0 CI 模式

verify_linux.sh 第二参数默认为 serial，显式 ENABLE_MPI=OFF；mpi 模式要求 Open MPI 开发库与启动器（Ubuntu 包 openmpi-bin/libopenmpi-dev），显式 ENABLE_MPI=ON。两个模式均不新增 Python 第三方包。远端版本与验收见 [P0 完成记录](P0_completion.md)。

## A_1104 四模式

verify_linux.sh 支持 serial/mpi/openmp/hybrid；MPI 与 OpenMP 开关独立。GCC 提供 libgomp，MPI/hybrid 需匹配的 Open MPI 开发库/启动器；审计和打包仅 Python 标准库。报告隔离环境安装 requirements-report.txt，完整已安装版本留在 results/A_1104/report/report-packages.txt。
