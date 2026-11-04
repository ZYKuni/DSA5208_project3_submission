# 提交版整理与报告更新（2026-11-04）

按用户要求，在工作仓库中更新报告内容与排版，并参考 Project 1 的根目录 report.pdf + 英文复现 README 组织独立提交副本。

## 成员与仓库

| 姓名 | 学号 |
|---|---|
| Yikun Zhao | A0353894M |
| Jiahao Zhou | A0354090J |
| Zheke Chen | A0356140M |

姓名拼写与顺序为本轮用户直接确认；学号保持此前确认的对应关系。report/source/team.json 和 PDF author 元数据同步修正。暂定提交仓库为 https://github.com/ZYKuni/DSA5208_project3_submission.git ，仅记录地址；没有初始化提交仓库、修改 remote、迁移或推送远端内容。

## 报告变更

- 正式报告由 8 页调整为 9 页，独立展示正确性验证与实验设计。
- 统一 A4 页边距、字体、深色表头、交替行底色、正文层级、图表颜色和页脚。
- 使用支持希腊字母的内嵌 DejaVu Sans 字体，修复数学符号，加入离散模态有限迭代解析式和行域分解示意图。
- 增加网格加密误差及约四倍误差比，明确后续 390 案例验证与 Vanda 历史 294 案例不同。
- 增加五组实验设计、配置数与基线总表，保留原始变异范围和单节点结论限制。
- 所有原有数值统计与旧报告 facts 逐项一致；没有修改计时样本、容差或求解器。
- 逐页检查全部 9 页，核对姓名学号、公式、表格、图片、换页和页脚。

## 提交目录

`/Users/yikun_zhao/Documents/DSA 5208/DSA5208_project3_submission`

根目录以 report.pdf、report_facts.json 和 README.md 为入口，包含 C++ 源码与头文件、CMake、配置、独立验证工具、测试夹具、集群脚本、报告生成器、正式图表、AI 记录及原始 Vanda/Linux/CI 证据。保留历史 docs 作为溯源资料；其旧进度不作为最终状态。排除 .git、虚拟环境、构建产物、缓存和旧进度报告生成器。工作仓库的正式 PDF 也已同步更新。

## 本轮直接从提交目录验证

- macOS 串行（Apple Clang）：CTest 6/6；独立统一验收 14/14。
- macOS OpenMP（GCC 15）：CTest 8/8，包含 42 个线程案例。
- Vanda 独立归档/统计审计通过：30 配置、180 启动、150 正式样本。
- 在独立输出位置重建报告，全文与交付报告一致；统计与旧报告一致。
- 20 个 src/include 文件及 CMake 保持实测版本，源码副本逐文件核对。
- 本机没有可用 MPI runtime，本轮未新增 MPI/hybrid 执行；此前 Linux 四模式/远端 CI 原始通过证据保留于 docs/A/results/A_1104，不冒称本轮重跑。

本轮具体检查见提交目录 docs/submission_checks/verification.json 和日志。SUBMISSION_MANIFEST.json 记录交付文件身份；相邻 ZIP 及 .sha256 提供传输副本。成员人工审阅与 Canvas 提交仍按最终提交清单执行。
