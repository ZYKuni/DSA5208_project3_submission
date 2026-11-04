# 最终提交检查清单

> 最新独立提交目录：`/Users/yikun_zhao/Documents/DSA 5208/DSA5208_project3_submission`，以其中 `report.pdf` 和英文 README 为提交入口；相邻同名 ZIP 为本轮整理版。此前 build-submission 中的包属于排版更新前快照。

## 工作仓库交付入口

- 正式报告：output/pdf/Project3_report.pdf（9 页，Vanda 正式数据；2026-11-04 提交版排版更新）。旧 C_progress 等 PDF 属于历史资料，不作为最终报告。
- 源码包：运行 `python3 scripts/package_submission.py --output build-submission/Project3_source.tar.gz`。包内 Project3/ 为根目录，包含源码、README、配置、证据、报告源及正式 PDF。
- 外部 .sha256 校验完整压缩包；内部 ARCHIVE_MANIFEST.json 校验每个文件。当前生成包的实际哈希与复现状态见 build-submission/Project3_source.verification.json（包外校验记录）。

## 已执行的技术检查

- 四种构建显式设置 MPI/OpenMP 开关，独立目录；串行、MPI、OpenMP、混合测试与完整场验证。
- 新增 1×4、2×1、3×1 的 OpenMP 核两通信组合；历史 Vanda 数量和新测试数量分开记录。
- Vanda 180 次原始启动与全部统计、归档和程序身份独立审计。
- 隔离安装 requirements-report.txt，使用归档数据重建正式报告，并逐页检查。
- 从不含 .git/build 的源码包解压，核对 manifest、运行审计、核对用于四模式测试的源码身份。
- README 命令、Python/系统依赖、报告入口及真实 CI 状态更新。完整证据见 A_1104_completion.md。

## 必须由成员完成，不能自动代签

- [ ] 三位成员阅读最终 PDF，确认姓名学号、贡献和 AI 声明准确。
- [ ] B/C 人工确认线程、通信和性能解释；不把自动测试当人工签核。
- [ ] 登录 Canvas 核实准确截止时刻、上传格式和大小限制。team.json 记录的时间为先前用户确认，本轮未访问 Canvas。
- [ ] 按要求上传正式 PDF 和源码包；重新下载核对文件与 SHA256，保存回执。

代码与资料的技术就绪不等同已交作业。没有自动向 Canvas 上传、向教师发送邮件或代成员签名。
