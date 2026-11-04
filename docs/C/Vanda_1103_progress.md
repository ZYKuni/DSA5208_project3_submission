# C：Vanda 接入进度（2026-11-03）

已通过 NUS 网页认证、首次 SSH 主目录初始化与 amgr 认证。账号 CPU 配额已查询，密码及认证材料未写入仓库。

## 已核实的平台信息

- OnDemand 控制台 4.1.7；登录主机 stdct-login-01。
- PBS 的 default_queue 为 auto；auto 是 Route 队列，转发至 batch_cpu/batch_gpu。
- 直接 qsub 到 batch_cpu 返回 Access to queue is denied；通过 auto 并声明 node_pool=cpu_node 的 CPU 作业已被接受。不是更改访问控制。
- 登录节点提示架构与计算节点不同，因此只在调度分配内编译和测试。
- 已观察 OpenMPI 模块 openmpi/gcc/64/4.1.8；CMake 模块 CMake/3.26.3-GCCcore-12.3.0。实际构建版本待计算节点日志确认。

## 源码与作业

GitHub 直接 clone 要求认证，已取消该尝试。通过 OnDemand 文件管理器上传 git archive 导出的提交 a1ee628951a3c381b9351d4978a714ee9a521478，文件 project3-source-a1ee628.tar.gz，SHA256 b5745d132e4f93b4c95d388b747e189fac5f5f4f817a4d618d035b2e3d000d1f。作业启动时再次校验。

首次接受作业：1514292.stdct-mgmt-02，名称 p3-c-pilot。请求 1 节点、4 CPU、2 MPI ranks、每 rank 2 OpenMP threads、8GB 内存、20 分钟。实际调度到 CN-017，PBS 将内存调整为 27GB；应报告实际分配。

提交时上传脚本的队列为 batch_cpu，命令行用 -q auto 与 node_pool=cpu_node 覆盖；仓库中的脚本已改为正确的 auto/pool 默认，后续可直接复用。首次脚本与准确提交命令将随证据归档。

此进度记录不声明作业成功、正确性通过或正式性能结论。作业运行中，需获取退出码、CTest、绑定、校准和原始日志后更新。

以上段落记录首轮提交时的状态；下面的复验结果取代其中“待确认”的当前状态，不改写历史失败记录。

## 首轮结果与复验安排

1514292 已在真实计算节点编译完成，8/9 CTest 组通过（包含 B 的 MPI-only 矩阵）。C 混合矩阵执行至 154 次，153 次通过；3 rank × 4 thread 的 continuous_converged 案例在 4 核分配中触发 30 秒超时。随后测试脚本读取缺失 result.json 引发 FileNotFoundError，原始超时仍保留在 verdict/stdout/stderr。

复验将申请 16 核以覆盖最大 12 线程，并仅在正确性测试中设 OMP_WAIT_POLICY=PASSIVE；算法、残差阈值和比较容差不变。测试脚本修复缺失结果时的诊断，继续保留 FAIL 并运行后续配置，不把超时或缺失结果标为通过。新包使用独立源码清单固定 revision 和 SHA256。

## 第二轮验证已完成

PBS 1514325.stdct-mgmt-02 在 CN-008 成功结束，退出码 0。实际分配 16 CPU / 111GB，节点为双路 Intel Xeon Platinum 8452Y，72 个物理核，SMT 未开启。工具链 GCC 12.3.0、Open MPI 4.1.8、OpenMP 4.5、CMake 3.26.3、Python 3.9.18；Release 编译采用 -O3 -DNDEBUG，无 fast-math。

- CTest 9/9 通过。
- C 的混合/线程矩阵 294/294、5 个负面案例通过。
- B 的 MPI-only 矩阵 124/124、4 个负面案例通过。测试覆盖有重叠，不把两组数量相加为独立案例。
- 单独绑定的 2 rank × 2 thread Sendrecv/overlap 均成功。
- N=2048、K=1000、check-every=10 的串行校准实测 5.77904227 秒；仅作为正式固定工作量选择依据。

实际源码固定为 af45f5bd84103838cef7e9e5ecdf221585b9fad3，上传包 SHA256 为 05493d35200bb03f5f69b9fccbae36318f812dc1839194d23975d2d42a9ae19d。这是不带 .git 的提交导出，不冒称计算节点有干净 checkout。归档保留原始源码与可执行文件哈希。

下载的两轮证据压缩包、可读摘要、调度资源与完整校验清单位于 results/Vanda_1103。压缩包在远程排除了重复网格 CSV，但保留所有比较、独立残差、结果与运行日志；原始场仍留在 Vanda。

## 正式性能实验

1514353 在计时之前的 Python affinity probe 处因一个多余括号退出，未生成性能样本。问题已修复；生成器现在也会单独保存 probe 的 stdout/stderr/argv。重新提交 1514382.stdct-mgmt-02，通过全部 R:T 组合的真实物理绑核检查后开始采集；结果完成后再汇总。

矩阵包含强扩展、弱扩展、固定总核数的进程/线程配比、Sendrecv/overlap、同残差求解。每配置 1 次预热和 5 次正式测量，串行校准选定 K=2600；强扩展 N=2048、check-every=10。正式测量使用 ACTIVE waiting，正确性复验用 PASSIVE，二者不混作性能样本。

当前只验证单节点 CPU。MPI 日志存在不可加载 PBS/UCX 插件的警告；实际 rank 绑定与 CPU 集合均单独核实，但不能据此声称跨节点运行或网络重叠已验证。

## 正式结果与报告交付

1514382 于 2026-11-03 18:10:21 SGT 完成，退出码 0；PBS 记录 CN-008、16 CPU、111GB、运行墙钟 11 分 3 秒。30 个配置共 180 次启动：30 次预热、150 次正式测量，全部 PASS。固定工作量、弱扩展、配比和通信研究使用 K=2600；同容差研究使用 N=127、tol=1e-8、check-every=20，所有版本均在 61160 次更新后收敛。

| 观测 | 实际结果 |
|---|---|
| 强扩展串行基线 | 14.2761 s 中位数 |
| 强扩展 MPI 16×1 | 1.3391 s，10.66× 加速，66.6% 效率 |
| 强扩展最快配置 2×8 | 1.0729 s，13.31× 加速，83.2% 效率 |
| 固定 16 核配比研究最低中位数 | 1×16：1.0095 s；但正式重复范围 0.9928–3.2417 s，不能把小差异当稳定优胜 |
| 16 核弱扩展效率 | MPI 49.8%；T=2 hybrid 58.0% |
| 4×4 通信比较 | Sendrecv 1.0651 s，overlap 1.0831 s；overlap 中位数高约 1.7%，重复范围重叠 |

单 rank MPI 强扩展五次正式样本为约 14.363、50.830、51.068、51.027、15.017 秒；没有删除慢样本。其原因没有隔离，报告明确不将这个差异解释成稳定的 MPI 额外开销。重复次序固定、节点共享、串行基线未单核固定，以及未控制 NUMA/频率，均限制性能归因。

原始下载包为 `results/Vanda_1103/vanda-measure-1514382-complete.tar.gz`，包含完整性能运行记录、失败准备作业及串行验证（远程打包排除 CSV，统计 CSV 已从 JSON 重建）。解压后可读材料位于 `measure_1514382/`、`failed_preparation_1514353/`。`audit.json` 核实 60 个源码文件与导出提交逐一相同，四个程序与成功 pilot 哈希一致，实验脚本哈希正确，每配置恰好有 -1/0/1/2/3/4 六次重复且逐运行结果一致。

已生成 `output/pdf/Project3_report.pdf`，8 页；科学图表 PNG/PDF 位于 `report/figures/Vanda_1103/`。三人姓名学号与截止时间采用用户直接提供的信息。逐页渲染检查已完成，字体嵌入且无溢出/遮挡。旧 C 进度 PDF 仍是历史文件，不能替代本报告。

## 交接与尚待人工确认

- C 分支已同步 main 的 882a816（A 集成审查和 MPI CI）。本轮实验仍明确引用 af45f5b；同步没有改动 src/include/CMakeLists.txt，未给历史日志换版本。
- A 的审查新增了更完整的混合组合建议（OpenMP 核下的 1×4、2×1、3×1，两种通信），当前 294 案例没有覆盖这些额外组合的完整 oracle 矩阵，不能声称已补齐。
- 当前 CI 的 serial/mpi job 不覆盖 OpenMP；建议 A 合并 C 时加入 hybrid job并独立复验。此处不冒称已有远端 hybrid CI 成功。
- 正式实验只使用 poisson_mpi 或 hybrid 的 OpenMP 内核，未用有输出身份歧义的 hybrid --kernel serial 作为性能版本。
- A/B/C 仍应人工审阅报告解释、算法、线程/通信设计和 AI 声明；本报告可用于团队审稿，不代表完成三人人工签核。没有向 Canvas 提交，也没有向他人发送消息。
