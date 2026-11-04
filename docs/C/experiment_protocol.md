# C：实验协议与数据边界

2026-10-31 更新：当前采集器使用 B 的共享 MPI 后端；新增的完整流程检查和正式矩阵见 [C_1031 交接](C_1031_handoff.md) 与 [集群接入](cluster_handoff.md)。下文的 10/27 时间属于旧独立 C 驱动，保留历史，不与新后端混合或当作集群结果。

## 已执行的本地协议

配置：`configs/experiments_local.json`；原始数据：`results/raw/c_local_1027/`；汇总：`results/summary/c_local_1027/`；图：`results/figures/c_local_1027/`。

四组研究共 15 个配置，每个预热 1 次、正式重复 3 次，总计 60 次真实运行、45 个正式样本。强扩展固定 N=1024、K=100、check_every=10；弱扩展 N=512/724/1024，约 262144 点/核；配比固定 4 核比较 4x1/2x2/1x4；实际求解 N=31、tol=1e-10、check_every=10，串行与混合均为 4780 步。

本地 MPI launcher 使用 `--map-by slot:PE={threads} --bind-to core --report-bindings`，并设置 OMP_PLACES=cores、OMP_PROC_BIND=close、OMP_DYNAMIC=FALSE。原始 stderr 表明 2x2 的 rank CPU 集合分别为 0–1 和 2–3。OpenMPI 同时报告内存绑定失败；日志保留，不把容器数据视为已完成目标集群绑定验证。OpenMP-only 由 runtime 绑定线程；串行基线不额外强制 CPU affinity，当前比较也因此属于预实验。

每轮测量采用程序的 solve_seconds_max，MPI 取最慢 rank。计入更新、缓冲交换、必要 halo 和既定残差归约；不含初始化、RHS 范数、最终诊断、导出或 launcher 启动。相同研究共享 problem、mode、K、tol 和 check_every。fixed 与 converge 的结果分别解释。

强扩展 S=t_serial/t_P，E=S/P。相对基线使用 E_rel=(t_P0/t_P)/(P/P0)。配比图以 4x1 为基线，因此大于 1 是相对布局收益，不是串行效率。弱扩展 E_weak=t_base(N0)/t_P(NP)，另外报告每核点数比例；N=724 的取整误差约 -0.0214%。

统计使用全部成功重复的中位数和 min-max。正式样本缺失、失败或预热失败会令该配置标为 INCOMPLETE，并抑制指标；不选择最快值替代中位数。原始退出码、超时、命令、输出、环境、源码与二进制 SHA256 均保留。性能样本的 PASS 表示元数据/有限诊断有效，不替代完整场数学验收。

## 对预实验的解释

N=1024 的 2x2 混合中位数约 0.01963 秒，相对串行约 3.23 倍；4 核配比单独试验中差异很小且范围重叠，不能据此断言最优布局。N=31 到同容差时混合比串行慢，说明小任务不能预设资源增加即收益。弱扩展四 rank 效率约 71.3%；一维 slab 的 halo 长度变化是解释候选，但未做阶段 instrumentation，不能断言已定位瓶颈。

虚拟硬件、Apple Silicon 核心差异、主机调度、内存绑定警告和几十毫秒的运行区间限制结论。正式集群试跑后应选择更长 K/更大 N 与更多重复，至少覆盖几个可行核心数，必要时增加跨节点结果。

## Atlas/Vanda 接入

复制 `configs/experiments_cluster.template.json`，填入真实 cluster、node_count、cpu_model、ranks_per_node、rank_binding、launcher，核对后设置 platform_verified/binding_verified。不能仅把 local scope 改成 cluster。采集器要求真实调度器 job ID，元数据确认也不替代人工检查调度分配和 affinity。

`scripts/cluster/run_job.sh` 在已分配作业中执行采集/汇总/绘图。`scripts/cluster/vanda_cpu.pbs.example` 是通用 PBS CPU pilot 草案，无队列/账号/模块假设，未在 Vanda 执行。课程使用说明核实后再提交；不要在登录节点跑正式实验。

公开的 [MLE4217/5219 教学团队教程](https://mle4217-5219.matsci.dev/orientation/vanda/) 将 Vanda 描述为 PBS/OnDemand 平台，并给出 NUSNET/HPC 账号及校外 VPN 前提。它是其他课程的一手教学说明，不等同本课程账号配额或当前管理员规则。教程链接的官方 SharePoint 指南不可由本次网页工具访问；NUS IT 页面返回 403。尚未获得用户的集群登录入口、账号或会话，因此没有尝试猜测身份登录或提交远程作业。

最终报告必须用 Atlas/Vanda 真实数据替换/补充当前性能部分。`scripts/build_report.py` 明确只生成本地进度草稿；正式集群报告需修改报告源与生成器，不能靠改文件名变成最终版。
