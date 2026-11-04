# C：Atlas/Vanda 接入与正式实验交接

日期：2026-10-31。当前没有已确认的集群连接或成功作业记录。以下是待真实平台核实的接入流程，不是已成功的集群命令。

## 需要提供的信息

- Atlas 或 Vanda 的课程使用指南、登录方式或已配置 SSH 别名；不提供或提交密码/令牌。
- 调度器、队列/账户、CPU 节点物理核数、可分配节点数、walltime 和配额。
- 实际模块、GCC/MPI/CMake/Python 版本及 MPI launcher/绑定规则。
- 一次小作业的实际提交脚本、job ID、节点分配与 stdout/stderr；代跑时交回完整目录。

当前工作站没有发现可用于 Atlas/Vanda 的 SSH 主机配置。模板仍保持未验证，不猜测主机名、账户、队列或模块。

## 接入后顺序

1. 在计算节点分配中编译同一 C 集成提交，保留构建日志、编译参数和源码/二进制 SHA256。
2. 运行串行、MPI、OpenMP 和混合的小规模全场验收；混合同时覆盖 sendrecv/overlap、窄子域和余数划分。正确性可允许小规模超额订阅，正式测量不可。
3. 用平台 launcher 输出及线程绑定诊断核对不同 rank 的线程落在不同物理核上；确认 OMP_PLACES/OMP_PROC_BIND 与 MPI 绑定兼容。设置 OMP_DYNAMIC=FALSE。
4. 校准 N/K，使主要定时任务有足够持续时间；固定步数与同容差实验分开。禁止直接把几十毫秒的本地候选配置当正式工作量。
5. 复制 cluster template，填写实际配置与验证证据，并确认 platform_verified、binding_verified、launcher_verified、workload_calibrated。
6. 使用 run_job.sh 在 allocation 内运行。每组预热一次、正式五次；失败保留，排查后换新目录重跑。保存 job ID、原始运行、manifest、CSV、图及绑定证据。

## 分工与匹配

C 负责混合、强弱扩展、rank/thread 配比、统计图表及性能正文；B 负责 MPI-only、阻塞/重叠和通信实验并复核混合 MPI 语义；A 负责独立验证和最终复现。B 的 MPI-only 采集不需要等待 C 的 OpenMP。

两套采集器共用同一编译版本、N/K/check_every、精度、节点布局与绑定规则。B 返回整个采集目录，C 按 manifest/config/run_id 关联资源与逐次 result，不直接拼接两个口径不同的 summary。涉及混合时必须记录实际线程数。

强扩展固定 N/K/check_every，报告相对同工作量串行的加速比与效率。配比固定总核数和节点数。弱扩展保持近似每核点数与固定 K，并披露网格取整及一维 slab halo 增长。同容差求解同时报告 actual_iterations 和最终残差。

没有阶段计时或 MPI 进度证据时，只能把通信/带宽/线程启动作为瓶颈假设，不能编造通信占比或宣称非阻塞已经重叠。
