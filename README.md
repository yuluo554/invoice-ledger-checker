# invoice-ledger-checker

**电子发票智能台账与重复报销检测桌面应用**——全离线、规则引擎为主、零 API 依赖的发票台账与异常检测工具。

> 🚧 **状态：v0.1.0，按里程碑交付中（M0-M4 已完成，M5 桌面交付进行中）**。路线图见下。

## 它解决什么问题

随着全面数字化的电子发票（数电票）自 2024 年 12 月起全国推广（国家税务总局公告 2024 年第 11 号，新增 XML 数据电文格式），企业报销票据全面电子化，财务痛点集中爆发：

- **同一张发票被多名员工重复报销**——三档重复检测（精确/联合键/模糊）
- **连号发票拆分报销**——同销售方邻近日期连号簇检测
- **票面金额与报销单不符**——票面算术复核（金额+税额=价税合计、大小写一致）

商业费控 SaaS 均为闭源在线服务；本项目提供**桌面端、本地 SQLite 存储、断网可用**的开源替代，数电票 XML 解析器在开源界几乎空白，是本项目的核心亮点。

## 特性（按里程碑交付）

| 特性 | 状态 |
|---|---|
| 合成发票生成器：固定 seed 可复现（位级一致），程序化植入 9 类已知异常 + 真值 JSON，60 份样本入仓（XML/PDF/OFD） | ✅ M1 |
| 法规知识库：764号令/《发票管理办法》原文核对入库，11号公告/56号令待核对挂渠道 | ✅ M1 |
| 数电票 XML 数据电文解析器（stdlib ElementTree，规则优先） | ✅ M2 |
| 版式 PDF 文本层解析（pdfplumber，label-slot 规则） | ✅ M2 |
| OFD 解析（加分项） | P2 |
| SQLite 本地台账：解析->入库->检测流水线（多维筛选 GUI 见 M5） | ✅ M3 |
| 异常检测规则引擎：重复报销×3 / 连号拆分 / 时间逻辑×2 / 票面算术×2，三级判定（确认/疑似/待人工确认）挂证据 | ✅ M3 |
| 内置评测基准：字段解析 F1、检出率/误报率，零 API 可复现 | ✅ M4 |
| PySide6 桌面界面 + QtCharts 统计看板 | M5 |
| Excel 台账导出（openpyxl，条件格式标红） | M5 |
| PyInstaller 打包 Windows exe，双击即用 | M5 |

## 快速开始（开发态）

```bash
git clone https://github.com/yuluo554/invoice-ledger-checker.git
cd invoice-ledger-checker

# Windows 自带 Python 3.8 的老 pip 无法可编辑安装，先升级（Linux/Mac 可跳过升级步）
py -m pip install -U pip
py -m pip install -e ".[dev]"

# 冒烟：144 项测试全绿（核心逻辑零第三方依赖；PDF 相关测试缺 reportlab/pdfplumber 时自动 skip）
py -m pytest

# 端到端演示：合成数据 -> 解析 -> 台账入库 -> 八规则检测 -> 三级异常清单
py -m invoice_ledger_checker demo

# 合成发票数据集 + 真值 JSON（同 seed 重跑逐字节一致；PDF 输出需 `pip install -e ".[data]"`）
py -m invoice_ledger_checker generate --out data --seed 42 --n 60

# 解析冻结样例出导入报告；check 一键解析->SQLite 入库->八规则检测
py -m invoice_ledger_checker parse data/invoices --report
py -m invoice_ledger_checker check data/invoices --db ledger.db --anchor-manifest data/ground_truth/manifest.json

# 内置评测基准：两条基准 + 门槛断言 + 报告落 benchmarks/report.md
# （门槛未达退出码 1 = 回归信号；冻结数据含 PDF 样本，需 `pip install -e ".[parse]"`）
py -m invoice_ledger_checker benchmark

# 可选依赖体检（pdfplumber/PySide6/openpyxl 等 extras 可用性）
py -m invoice_ledger_checker doctor
```

> Windows 控制台中文乱码时用 `py -X utf8 -m invoice_ledger_checker demo`。
> 安装后也可用等价的 `invoice-ledger` 命令（脚本位于 Python Scripts 目录，需在 PATH）。
> 桌面 GUI：`py -m pip install -e ".[desktop]"` 后 `py -m invoice_ledger_checker app`（M5 交付）。

## 架构

```mermaid
flowchart LR
    GEN["合成生成器<br/>固定seed+真值"] --> XMLP["XML/PDF/OFD<br/>解析器"] --> CARD["InvoiceCard<br/>发票参数卡"] --> DB[("SQLite<br/>本地台账")] --> ENG["规则引擎<br/>8规则三级判定"] --> OUT["GUI / CLI /<br/>Excel 导出"]
    GEN -.真值对账.-> BENCH["内置基准<br/>F1/检出率/误报率"]
    BENCH -.验收.-> XMLP & ENG
```

核心逻辑（模型/存储/规则/引擎）只用 Python 标准库；重量级库全部 extras 惰性导入——评测与命令行核心零 API、零网络依赖。设计文档：[plan/03-架构与技术选型.md](plan/03-架构与技术选型.md)。

## 评测基准（M4 实测；报告全文见 [benchmarks/report.md](benchmarks/report.md)）

冻结 60 份合成数据（seed=42，9 类注入异常 + 基线）对账实测：

| 指标 | 门槛 | 实测 |
|---|---|---|
| 字段解析宏平均 F1（12 卡级字段 + 4 明细字段，微/宏平均均同值） | ≥ 0.95 | **1.0000** |
| 异常检出率（TP/真值异常，expect∪also_expect 全集对拍） | 100% | **100%**（18/18 对） |
| 误报率（FP/全部告警） | 0 | **0**（13 findings 全部对应真值异常） |
| 判定准确率（级别一致/真值异常） | 100% | **100%** |

零 API 可重复：纯规则通路、固定输入、无墙钟（R-TIME 走 manifest 批次 expense_anchor 基准通路），报告同输入重跑逐字节一致；`py -m invoice_ledger_checker benchmark` 一键重跑，门槛未达退出码 1（回归信号），CI 设 benchmark 作业守门。

## 目录结构

```
├── plan/          # 计划文档（需求/架构/详设/里程碑/决策——单一事实源）
├── data/          # 合成发票样本 + 真值 + 法规知识库（台账登记来源）
├── src/invoice_ledger_checker/
│   ├── models/    # InvoiceCard 发票参数卡（统一中间表示）
│   ├── parsing/   # XML / PDF / OFD 解析器
│   ├── storage/   # SQLite 台账
│   ├── rules/     # 检测规则引擎（error/suspicious/review 三级）
│   ├── generator/ # 合成发票生成器（固定 seed）
│   ├── benchmarks/# 评测基准
│   ├── export/    # Excel 导出
│   ├── app/       # PySide6 桌面入口
│   └── cli.py     # 命令行入口
└── tests/         # pytest（核心逻辑 stdlib-only 可跑）
```

## 路线图

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 计划 00-06 + 可运行骨架 | ✅ 2026-10-05 |
| M1 | 数据先行：合成发票生成器（位级可复现）+ 真值 + 法规知识库 | ✅ 2026-10-06 |
| M2 | 解析层：XML/PDF 双解析器 → 发票参数卡 | ✅ 2026-10-06 |
| M3 | SQLite 台账 + 规则引擎八规则全量 | ✅ 2026-10-06 |
| M4 | 内置基准达标（F1≥0.95 / 检出 100% / 误报 0） | ✅ 2026-10-06 |
| M5 | PySide6 桌面交付 + Excel 导出 + PyInstaller exe | ⬜ |
| M6 | 脱敏发布 GitHub + Release（exe） | ⬜ |

## 边界与免责声明

- 本项目是**检测辅助定位工具，不是审批决策工具**：输出三级异常清单供人工复核，最终判断由财务人员做出。
- 不做发票验真（不调用税务接口）、不做 OCR（拍照/手写票据）、不做报销审批流。
- 仓库内一切发票样例、公司名、纳税人识别号均为**程序合成的虚构数据**，与任何真实主体无关。
- 全部数据本地处理（SQLite），无任何网络上传。

## License

[MIT](LICENSE)
