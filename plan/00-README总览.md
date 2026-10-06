# invoice-ledger-checker 项目计划总览

**项目**：电子发票智能台账与重复报销检测桌面应用（财务领域，Windows 桌面程序形态）
**方法论**：ai-tool-project-sprint（plan 先行 → 数据先行 → 解析/规则 → 基准 → 桌面交付+打包 → 脱敏发布）
**项目系列**：①construction-drawing-plan-checker（建造，Web，已发布）②power-operation-ticket-checker（电力）③medical-record-quality-checker（医疗）④bidding-document-checker（公共采购）⑤food-label-compliance-checker（食品）→ ⑥本项目（财务，**首个桌面应用形态**）

## 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [01-题目详细定义.md](01-题目详细定义.md) | 模拟赛题全文（介绍/任务/提交材料/评分/含金量锚点/边界） | ✅ 定稿 2026-10-05 |
| [02-需求解读.md](02-需求解读.md) | 痛点→能力转译表、FR 清单（P0/P1/P2）、NFR、边界 | ✅ 定稿 2026-10-05 |
| [03-架构与技术选型.md](03-架构与技术选型.md) | 六层流水线、src 布局、选型表（3.8 兼容）、extras 策略、风险表 | ✅ 定稿 2026-10-05 |
| [04-模块详设.md](04-模块详设.md) | InvoiceCard schema、解析字段映射、八规则表、SQLite DDL、GUI 划分 | ✅ 定稿 2026-10-05 |
| [05-数据计划与里程碑.md](05-数据计划与里程碑.md) | 生成器+注入异常清单+真值语义、M0-M6 DoD、基准口径、交付对标 | ✅ 定稿 2026-10-05 |
| [06-决策记录.md](06-决策记录.md) | 重大决策表（已定+待定+缓议清零区） | ✅ 独立成文 2026-10-05 |
| [HANDOFF-M1.md](HANDOFF-M1.md) | 交接快照：M0 收尾 → M1 数据先行续接（已过时留档） | ✅ 2026-10-05 |
| [HANDOFF-M2.md](HANDOFF-M2.md) | 交接快照：M1 收尾 → M2 解析层续接（已过时留档） | ✅ 2026-10-06 |
| [HANDOFF-M3.md](HANDOFF-M3.md) | 交接快照：M2 收尾 → M3 规则引擎续接 | ✅ 2026-10-06 |

## 决策记录

| 日期 | 决策 | 结论 |
|---|---|---|
| 2026-10-05 | 选题与形式 | 系列第六题，**形式换挡为桌面应用**（用户要求"做成 app 或电脑程序"）：发票台账+重复报销检测——数电票 XML 解析是开源空白亮点，规则密度高、全离线零 API，与"程序化自制带真值"打法最契合 |
| 2026-10-05 | 技术栈 | Python + PySide6（QtCharts）+ SQLite（FTS 可选）+ openpyxl + reportlab（生成器）+ PyInstaller 打包；LLM 仅可选兜底，非必需 |
| 2026-10-05 | 仓库名与发布 | `invoice-ledger-checker`，GitHub 公开；Release 附 Windows exe |
| 2026-10-05 | 政策依据 | 11号公告/764号令/56号令已查证（见 01 §五），条文入库时逐条挂出处 |
| 2026-10-06 | 真值语义定稿 | 双键真值（cards 按文件路径、expectations 按号码）；基准按全部非 pass 集合对账；R-DUP-02 排除纯复制件（只报 R-DUP-01）；R-TIME 基准通路取批次 expense_anchor（与墙钟无关）；权威出处 = generator/synthetic.py 模块注释 |
| 2026-10-06 | 法规查证收口 | 764号令/《发票管理办法》修订原文已直连核对入库；11号公告/56号令原文未直连成功 → 条文标"待核对"+登记渠道，不空转（M2+ 补核） |
| 2026-10-06 | 解析层映射与实现定稿 | 字段映射权威 = TEMPLATE_REFERENCE（synthetic-v1）；PDF label-slot 实测固化三条口径：双栏版式 value 词以同线下一标签 x0 为右边界、`价税合计（大写）：` 与值同词合并取冒号后文本、明细四列按表头 x0 锚点最近列归并；对账器落 benchmarks/field_match.py（M4 基准同源复用） |

## 里程碑

- **M0 计划+骨架 ✅（2026-10-05）**：plan 02-06 定稿；src 布局骨架（models/parsing/storage/rules/generator/benchmarks/export/app + CLI）；种子规则 R-ARITH-01/R-DUP-01；25 项测试全绿；`py -m invoice_ledger_checker demo/doctor` 可用；CI（win 3.8/3.12 + ubuntu 3.12）；MIT + README + .gitattributes(EOL 门)
- **M1 数据先行 ✅（2026-10-06）**：合成发票生成器（5 类型 × XML/PDF/OFD 三格式，seed 可复现位级一致）；9 类注入 + 基线全落地，真值 JSON（cards/expectations/manifest）语义定稿；`generate --out data --seed 42 --n 60` 冻结 60 份入仓；法规知识库（764号令已核对、11号公告/56号令待核对挂渠道）；数据台账四行登记齐；65 项测试全绿
- **M2 解析层 ✅（2026-10-06）**：XML 解析器（FIELD_MAP localname 路径映射 + 命名空间降级 + 数值清洗丢值降置信）+ PDF 解析器（pdfplumber 词级 label-slot，双栏截断/大写合并词/明细 x 列聚类）→ InvoiceCard；`parse data/invoices --report` 一键全量（57 成功 + OFD 3 顺延登记，坏文件拒绝清单，缺依赖 exit 2）；冻结 60 份对账 XML 35/35、PDF 22/22 字段级 F1=1.0（门槛 0.95）；坏文件路径 7 项测试；pytest 95 项全绿（干净 venv 89 绿/6 skip = CI 平价）
- M3 规则引擎：重复报销/连号簇/时间逻辑/算术复核四类检测 + 三级判定
- M4 内置基准：解析 F1 ≥0.95、检出率 100%、误报 0
- M5 桌面交付：PySide6 界面（导入/台账/看板/异常清单）+ Excel 导出 + PyInstaller 打包
- M6 脱敏发布 GitHub + Release（exe）+ 收尾固化
