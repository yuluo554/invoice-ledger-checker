# invoice-ledger-checker 项目计划总览

**项目**：电子发票智能台账与重复报销检测桌面应用（财务领域，Windows 桌面程序形态）
**方法论**：ai-tool-project-sprint（plan 先行 → 数据先行 → 解析/规则 → 基准 → 桌面交付+打包 → 脱敏发布）
**项目系列**：①construction-drawing-plan-checker（建造，Web，已发布）②power-operation-ticket-checker（电力）③medical-record-quality-checker（医疗）④bidding-document-checker（公共采购）⑤food-label-compliance-checker（食品）→ ⑥本项目（财务，**首个桌面应用形态**）

## 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [01-题目详细定义.md](01-题目详细定义.md) | 模拟赛题全文（介绍/任务/提交材料/评分/含金量锚点/边界） | ✅ 定稿 2026-10-05 |
| 02-需求解读.md | 痛点→能力转译表、FR 清单、边界 | ⬜ |
| 03-架构与技术选型.md | PySide6 + SQLite + 规则引擎分层、PyInstaller 打包 | ⬜ |
| 04-模块详设.md | 发票参数卡 schema、XML 解析器、异常检测规则表 | ⬜ |
| 05-数据计划与里程碑.md | reportlab/XML 合成发票生成器、M1-M6 | ⬜ |
| 06-决策记录.md | 重大决策表 | ✅ 初始化（见下） |

## 决策记录

| 日期 | 决策 | 结论 |
|---|---|---|
| 2026-10-05 | 选题与形式 | 系列第六题，**形式换挡为桌面应用**（用户要求"做成 app 或电脑程序"）：发票台账+重复报销检测——数电票 XML 解析是开源空白亮点，规则密度高、全离线零 API，与"程序化自制带真值"打法最契合 |
| 2026-10-05 | 技术栈 | Python + PySide6（QtCharts）+ SQLite（FTS 可选）+ openpyxl + reportlab（生成器）+ PyInstaller 打包；LLM 仅可选兜底，非必需 |
| 2026-10-05 | 仓库名与发布 | `invoice-ledger-checker`，GitHub 公开；Release 附 Windows exe |
| 2026-10-05 | 政策依据 | 11号公告/764号令/56号令已查证（见 01 §五），条文入库时逐条挂出处 |

## 里程碑（初稿）

- M1 数据先行：发票模板（数电票 XML + PDF 版式）+ 生成器（固定 seed，植入重复/连号/算术错误真值）+ 数据台账
- M2 解析层：PDF 文本层 + XML 数据电文双解析器 → 发票参数卡，回归测试
- M3 规则引擎：重复报销/连号簇/时间逻辑/算术复核四类检测 + 三级判定
- M4 内置基准：解析 F1 ≥0.95、检出率 100%、误报 0
- M5 桌面交付：PySide6 界面（导入/台账/看板/异常清单）+ Excel 导出 + PyInstaller 打包
- M6 脱敏发布 GitHub + Release（exe）+ 收尾固化
