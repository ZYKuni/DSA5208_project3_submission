# A：Linux / GCC 可复现性验证（2026-10-31）

## 目标与边界

在干净 Linux 环境完成 GCC Release 构建、全部 CTest 和统一验收，不依赖 B/C 的并行实现。只验证串行基线与验证工具；这些日志不能替代 Atlas/Vanda 性能实验，也不证明 MPI/OpenMP 的正确性。

## 可复用入口

Linux 上先安装 GCC/G++、CMake >=3.16、Make 和 Python >=3.8，再从项目根目录执行：

```sh
bash scripts/verify_linux.sh build-linux-evidence
```

输出目录必须尚不存在。脚本强制使用 GCC/G++、Release、BUILD_TESTING=ON、系统 Python，并记录实际版本与编译参数。任意构建、CTest 或验收失败都会返回非零退出码；已生成日志保留，退出码写入 exit_code.txt。再次运行请更换目录名。

## 干净容器复现

本轮把 Git HEAD 导出到新目录，只加入本轮新增的验证脚本和 CI 文件，以只读方式挂载到容器；未挂载宿主机编译器、Python 环境或历史 build 目录。容器退出后自动删除，日志保留。对应基础提交见结果目录 base_commit.txt；实际运行代码以 verification/source_manifest.json 中的 SHA256 为准。

其他机器可在项目根目录执行以下命令（需要 Docker；输出目录应当为空）：

```sh
mkdir build-linux-output
docker run --rm \
  --mount "type=bind,src=$PWD,dst=/src,readonly" \
  --mount "type=bind,src=$PWD/build-linux-output,dst=/evidence" \
  ubuntu@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852 \
  bash -c 'set -euo pipefail; export DEBIAN_FRONTEND=noninteractive; apt-get update 2>&1 | tee /evidence/apt-update.log; apt-get install --no-install-recommends -y gcc g++ cmake make python3 git ca-certificates 2>&1 | tee /evidence/apt-install.log; bash /src/scripts/verify_linux.sh /evidence/verification'
```

镜像固定 digest，但 apt 软件源和 CI runner 会更新，因此不是逐字节可重建的工具链。每次必须保留实际包版本；目标是可重复执行并通过相同正确性标准。Docker 默认选择宿主机架构，本轮为 aarch64，不能称为 x86_64 实测。

## CI

.github/workflows/linux-gcc.yml 对 push、pull_request 和手动触发运行 ubuntu-24.04（GitHub 托管 x86_64 runner），调用相同脚本；失败时仍上传已生成证据，保留 30 天。仅授予 contents:read，checkout 不保留 Git 凭据，单次限时 15 分钟。

本轮只准备配置，未推送触发远程 Actions。远程 CI 成功结论须等待实际运行，最终提交前还应下载归档所需日志，避免 artifact 过期。

## 实测结果

原始证据：[results/A_1031_linux/](results/A_1031_linux/)。

| 项目 | 实测结果 |
|---|---|
| 时间 | 2026-10-31 07:38:52 UTC 开始配置前环境采集 |
| 环境 | Docker Desktop Linux VM，Ubuntu 24.04.5 LTS，aarch64，内核 6.10.14-linuxkit |
| 工具链 | GCC/G++ 13.3.0、CMake 3.28.3、Python 3.12.3、GNU Make 4.3、glibc 2.39 |
| 编译 | Release，-O3 -DNDEBUG -std=c++17 -Wall -Wextra -Wpedantic；成功 |
| CTest | 4/4 通过：core_contract、serial_validation、grid_comparison_contract、acceptance_contract |
| 串行验证 | 37 个数值案例、16 个非法 CLI 案例通过；网格加密误差比 4.0233、4.0058 |
| 验证工具自测 | 14 个网格比较测试方法、10 个验收测试方法通过，包括错误注入和超时回收 |
| 独立统一验收 | 14/14 PASS，0 FAIL |
| 总入口退出码 | 0 |

本轮没有修改算法、数值容差或既有测试来适配 Linux。未运行 Linux sanitizer；已有 macOS sanitizer 结果仍属于此前阶段。

归档包含安装日志、镜像元数据、完整 CTest 日志、编译参数、CMakeCache、串行验证数据、14 案例逐次命令/stdout/stderr/网格/比较结果，以及源码和可执行文件哈希。编译目录和二进制不提交。

导出的源码没有 .git，所以环境日志中的 Git 查询失败、run_manifest.json 的 git_commit=null 是预期现象，不是测试失败。base_commit.txt 记录导出基点 ae6d139fe517baf1e4c21b10c0c9224ad5843586；另加的脚本和 CI 文件已包含在 source_manifest.json 中。结果里的 /src 和 /evidence 是当时容器路径，容器退出后应按归档中的相对目录阅读。

本轮完成 A 可独立推进的 Linux 正确性复现；B/C 后续交付后，仍须接入真实 MPI/OpenMP 验收和 Atlas/Vanda 实验。
