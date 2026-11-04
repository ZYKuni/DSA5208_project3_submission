# C：已验证开发环境

日期：2026-10-27。宿主机是用户现有 macOS/Apple Silicon；已启动原有 Docker Desktop 28.3.3，没有安装或替换宿主机编译器/MPI。

- 工具链镜像：`project3-c-dev:bookworm`。
- 本次 image ID：`sha256:20c03f7e5b3a1cdd7be91bbc992124a7e70b584ae205647169d9068cd1b56961`。
- 基础镜像拉取摘要：`debian:bookworm-slim@sha256:7ff6ba31527b9e336162fa061746c366c4b2032f4d2cff2078bea43f78efe3f8`。
- Dockerfile 重建会使用当时可用的 Debian 包；本次精确包版本见 `results/C_1027/packages.txt`，不宣称重建镜像字节一致。
- Linux aarch64 VM，10 个可见逻辑 CPU，容器 lscpu 每核 1 线程；不据此推断宿主机的性能核/能效核。
- GCC 12.2.0，libgomp/OpenMP 4.5；OpenMPI 4.1.4。CMake 检测的 MPI 3.1 是接口标准版本，不是实现版本号。
- CMake 3.25.1，Ninja；Release 使用 -O3 -DNDEBUG -std=c++17 和现有 warning flags，无 fast-math。
- Python 3.11.2，matplotlib 3.6.3，reportlab 3.6.12；分析依赖来自 Debian 包，容器不需要 pip。完整编译命令在本地实验原始目录。
- MPI/OpenMP 为容器内真实执行。正确性套件为便于多配置测试允许本地 oversubscription；性能矩阵最多 4 核，另用分核绑定。
- MPI rank CPU 绑定日志存在，容器内存绑定失败警告也存在；它们不属于 Atlas/Vanda 实测。

纯串行默认 CMake 路径仍无需 MPI/OpenMP。原生集群需使用管理员提供的工具链，不能把本容器版本当作已验证的 Atlas/Vanda 环境。
