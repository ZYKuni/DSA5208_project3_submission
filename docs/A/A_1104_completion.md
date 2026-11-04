# A：P0 / P1 / P2 完成记录

> 本文为首轮技术验收记录，报告当时为 8 页。后续姓名修正、9 页报告与独立提交目录整理见 [提交版更新](Submission_refresh_1104.md)。

本轮基于 A_1104 的 fea31fa；验证工具和 CI 提交为 4ddfc9103541576022767216a22f21598e33bde6。实际求解源码、头文件及 CMake 与 Vanda af45f5b 相同，没有因补测更改算法、计时范围或容差。

## P0：补齐混合验证与四种构建

- tests/test_parallel.py 补入 OpenMP 核 1×4、2×1、3×1，每种分别覆盖 sendrecv/overlap。现有案例与五个负面测试保留。
- verify_linux.sh 明确设置 MPI/OpenMP 两开关，支持 serial/mpi/openmp/hybrid，隔离输出目录；正确性使用 PASSIVE 等待和关闭动态线程。
- EXIT trap 归档 mpi-validation、parallel-acceptance、CTest Testing，保留超时/失败时已有日志。工作流矩阵四 job 独立执行，失败不取消其他 job。

| 构建 | 本地 CTest | 并行验证 |
|---|---|---|
| serial | 6/6 | 串行统一验收 14/14 |
| mpi | 7/7 | MPI 124/124 + 4 个错误案例；串行统一验收 14/14 |
| openmp | 8/8 | 线程矩阵 42/42；串行统一验收 14/14 |
| hybrid | 9/9 | 混合/线程 390/390 + 5 个错误案例；MPI 124/124 + 4 个错误案例；串行统一验收 14/14 |

这些组别有重叠，不能相加为不同数学问题数。Vanda 的历史验证仍为 294，不将本轮新增 96 次执行改写为集群已运行。实际环境、命令和逐案例紧凑证据位于 results/A_1104/local；完整网格在忽略的 build-a-final/evidence 中，可用入口重新生成。

远端四模式 CI 与解压包复验的最终状态见本文件末尾的收尾记录。

## P1：数据/报告审核与隔离重建

[独立审计](Vanda_report_audit.md) 核对 3 个归档、943 个可读原文件、60 个历史源文件、四个二进制身份及全部 180 次启动。30 个配置、150 个正式样本的统计重算一致。故意篡改临时原始输出和汇总值均被拒绝。

报告使用干净 Ubuntu 和独立 venv，按 requirements-report.txt 安装 matplotlib 3.10.7、reportlab 4.4.9，实际完整依赖版本保存于 results/A_1104/report/report-packages.txt。复建使用仓库已有 Vanda 数据与生成器，不制造新测量。生成的 8 页 PDF 已逐页视觉检查，表格、图表、文字、页码无遮挡或截断；数学、计时、限制、身份来源与 AI 声明已审阅。正式入口 output/pdf/Project3_report.pdf 更新为本轮复建副本，仍明确引用 Vanda 实测源版本。

没有新增求解器或性能问题需要重跑 Vanda。没有宣称三个成员已人工签核；助手的源码/页面审阅和自动检查不代替本人确认。

## P2：提交与文档

README 改为当前团队版本、四种构建、最新测试组数，保留历史版本标记。提交包入口 scripts/package_submission.py 排除 .git/build/缓存和历史进度 PDF，包含独立可运行源码、配置/夹具、报告源、证据与正式 PDF；包内逐文件 SHA256 和包外 checksum 可校验交付。

[提交清单](Submission_checklist.md) 指定唯一正式报告和源码包，明确人工确认、Canvas 要求、上传/重新下载核对与回执步骤。未访问 Canvas、未提交作业、未代签。

## 收尾记录

[GitHub Actions 41837165001](https://github.com/ZYKuni/NUS_DSA5208_project3/actions/runs/41837165001) 对代码提交 4ddfc91 的 serial、mpi、openmp、hybrid 四任务均已完成且 success。此结论来自真实 Actions API/job 状态，不是仅检查 YAML。原始任务元数据与选取产物保存于 results/A_1104/remote；本轮本地容器为 ARM64，GitHub runner 为 x86_64。

候选包解压后不含 .git，3,069 个文件通过 manifest 校验。在新容器中从该目录重新构建，四模式 CTest 再次为 6/6、7/7、8/8、9/9；混合 390/390、5 个负面案例通过。解压包内再次执行独立数据审计通过；报告重建后的全文与已审阅副本相同。结果见 results/A_1104/package。最终包只增加后续文档与证据，运行代码/配置和正式报告通过与已测试候选包的逐文件身份核对；包外 Project3_source.verification.json 记录最终包哈希。

故障注入验证 CTest 返回 23 时，MPI 和 parallel-acceptance 的已有 stderr 均能归档，原退出码保留；重复输出目录与非法模式被拒绝。注入结果不计作数值测试通过。

P0/P1/P2 的技术执行已完成。仍需成员本人审稿/确认和 Canvas 上传回执，见提交清单；这些不是可由助手冒称完成的自动化步骤。
