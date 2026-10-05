# HANDOFF-M1（M0 收尾 → M1 数据先行 续接快照）

> **⚠️ 已过时，仅作历史留档（2026-10-06 M1 收尾后归档）**。M1 已完成并收尾，
> 续接请读 [HANDOFF-M2.md](HANDOFF-M2.md)。本文保留 M1 启动时的状态快照与
> 本机环境坑记录（§4 环境坑仍然有效），勿按本文待办继续施工。

> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-M1.md 继续完成任务`（相对路径；启动命令由用户侧拼绝对路径）。
> 本快照落盘于 2026-10-05，M0（计划+骨架）收尾时。方法论：ai-tool-project-sprint。

## 1. 当前进度（M0 已完成）

- **计划文档**：plan/02-需求解读、03-架构与技术选型、04-模块详设、05-数据计划与里程碑、06-决策记录 全部定稿；plan/00 索引与里程碑状态已回写。
- **代码骨架**（src 布局，全部 stdlib-only 核心已落地并测试）：
  - `models/invoice.py`：InvoiceCard/LineItem/Evidence 契约（plan/04 §1），to_dict/from_dict 往返 + 主键强校验；
  - `storage/ledger.py`：SQLite 三表 schema 与 plan/04 §4 一致，add_invoice 主键冲突拒收（返回 False，不覆盖）；
  - `rules/`：引擎（Rule/Finding/DetectionEngine，card|batch 双 scope，注册序执行+互斥传递 ctx["findings"]）+ 种子规则 R-ARITH-01（价税合计复核，含非数值降级 review）与 R-DUP-01（批内精确判重）；
  - `parsing/`：base 契约（SUPPORTED_SUFFIXES/parser_for/ParserError）+ xml/pdf/ofd 三桩（NotImplementedError，设计要点已写入 docstring）；
  - `generator/`、`benchmarks/`、`export/`、`app/`：桩 + 设计契约 docstring；
  - `cli.py`：demo（3 张合成卡入库→查重→算术复核→findings 持久化，exit 0）/ doctor（六可选依赖体检）/ 五个 stub 命令（打印所属里程碑，exit 2）；`--version`；
  - `utils.py`：force_utf8_stdio（GBK 控制台防线）+ import_optional（缺依赖带安装提示，exit 2）。
- **工程配置**：pyproject（核心零依赖；extras: dev/parse/data/export/report/desktop/all；`invoice-ledger` console script）；`.gitattributes` `* text=auto eol=lf`（EOL 门）；`.gitignore` 已移除 `*.spec`（主 spec 将入仓）；CI（windows 3.8/3.12 + ubuntu 3.12 三矩阵）；MIT LICENSE；README（诚实骨架态，评测表占位）。
- **验证证据**：pytest **25 passed**；`py -m invoice_ledger_checker demo` exit 0（入库 2、重复拒收 1、异常 2 条）；doctor exit 0；stub 命令 exit 2 带里程碑提示；`pip install -e .` 成功（pip 25.0.1）。
- 本地 commit：M0 收尾提交（见 git log）。

## 2. M1 待办（数据先行，DoD 见 plan/05 §2）

1. **合成发票生成器** `generator/synthetic.py`：5 类发票模板（XML 直出 + reportlab PDF 版式 + OFD 可选）；`random.Random(seed)` 显式实例；CLI `generate --out data --seed 42 --n 60 --anomaly-rate 0.35` 接通（stub 摘除）；
2. **异常注入 10 类**按 plan/05 §1.3 清单落地，真值 JSON（按发票号码为键，expect/also_expect）——**真值语义定稿写进生成器模块注释**并回填 plan/05 §1.3（如有出入）；
3. **可复现守门测试**：同 seed 两次生成逐字节一致；冻结文件出现 CR 即大声失败的测试（EOL 门）；
4. **法规知识库**：data/knowledge/ 三部法规条文摘录入库，每条挂出处+status；查证失败的显式标"待核对"+已查渠道，不空转；
5. **数据台账**：data/README.md 登记表四行回写实际状态（来源/许可/seed/命令）；
6. 里程碑收尾：plan/00、05 状态回写 ✅；写 plan/HANDOFF-M2.md；本文件头部标注"已过时仅作历史"。

## 3. 既定口径清单（动了会打挂基准/测试的约定，改前先对照）

1. **InvoiceCard 字段名与嵌套结构** = plan/04 §1（items 是 LineItem 列表；金额全 str Decimal 文本）；改 schema 必须先改 plan/04 + 同步 tests；
2. **规则 ID 与级别语义**：R-DUP-01/02/03、R-SEQ-01、R-TIME-01/02、R-ARITH-01/02；error/suspicious/review 三级（plan/04 §3）；引擎注册序 = 执行序，R-DUP-03 必须排除 R-DUP-01/02 已命中组合（ctx["findings"] 互斥机制）；
3. **SQLite schema** = plan/04 §4 DDL（invoices 主键即 R-DUP-01 基础；重复导入拒收不覆盖）；
4. **真值语义**：基准按"每张卡全部非 pass 集合"对账（expect 主期望 + also_expect 隐含期望），不做"只验主期望"的假绿——M1 定稿后此处升级为权威表述；
5. **测试纪律**：tests 模块级只 import stdlib+pytest；重量依赖测试在函数体内 import_optional，缺失时显式 skip 且计数上报（防静默少跑）；conftest.py 负责 src 路径引导；
6. **核心零依赖**：models/storage/rules/utils 只准 stdlib；新重量级 import 必须走 extras + import_optional（utils 纪律注释）；
7. **EOL 门**：`.gitattributes` eol=lf；冻结生成物出现 CR 即失败；
8. **requires-python = ">=3.8"**：语法限 3.8（无 match、无 PEP604 标注）；CI ubuntu-3.12 常驻验前向兼容；
9. **退出码契约**：CLI 未交付命令/缺依赖 = exit 2；demo/doctor = exit 0。

## 4. 本机环境坑（只记录本轮实测）

- **Python 3.8.8 是唯一解释器**（`py` 即 3.8）；pip 25.0.1 可 PEP 660 可编辑安装，无需先升级 pip；
- **pip 走清华镜像 + `NO_PROXY="*" no_proxy="*"`**（注册表系统代理污染规避）；`PYTHONDONTWRITEBYTECODE=1` 全程携带（含 pip install）；
- **`invoice-ledger.exe` 不在 PATH**（Python Scripts 目录未入 PATH）——统一用 `py -m invoice_ledger_checker ...`；README 已按此书写；
- **系统 Python 已有 pdfplumber/reportlab/openpyxl/docx 存量包**（姊妹项目遗留）——doctor 显示"已安装"≠ extras 声明正确；**M6 干净环境验证是 extras 完整性的唯一真证据**；
- **PySide6 未安装**（desktop extra 未验证）——6.5-6.7 与 cp38 wheel 覆盖是 plan/03 待核对项，M5 安装时复核；
- Git Bash 下跑 Python 一律 `py -X utf8`；测试内 subprocess 显式 PYTHONIOENCODING=utf-8。

## 5. M1 DoD checklist（收尾逐项打勾，没做到的写偏差说明）

- [ ] `py -m invoice_ledger_checker generate --out data --seed 42 --n 60` 一键产出含 10 类注入异常的合成票 + 真值 JSON
- [ ] 同 seed 两次生成逐字节一致（守门测试断言，测试数同步更新 README/plan）
- [ ] 真值语义定稿写进生成器模块注释；plan/05 §1.3 与实现一致（有出入已回填）
- [ ] data/knowledge/ 三部法规条文入库，每条挂出处+status（或显式"待核对"+已查渠道）
- [ ] data/README.md 登记表四行回写实际状态
- [ ] pytest 全绿且含生成器回归（收集数与 M0 的 25 项对账逻辑清楚：新增多少、为何）
- [ ] plan/00、05 状态回写；HANDOFF-M2.md 落盘；本文件标注已过时

## 6. 关键命令速查

```
# 测试（全程携带 PYTHONDONTWRITEBYTECODE=1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest

# CLI（安装后；未装则 PYTHONPATH=src py -X utf8 -m invoice_ledger_checker ...）
py -X utf8 -m invoice_ledger_checker demo
py -X utf8 -m invoice_ledger_checker doctor
py -X utf8 -m invoice_ledger_checker generate --out data --seed 42 --n 60   # M1 接通后

# 安装（pip 代理规避 + 不写 pyc）
NO_PROXY="*" no_proxy="*" PYTHONDONTWRITEBYTECODE=1 py -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# git（提交前三核对：pwd / git log --oneline -1 / git remote -v）
git add -A && git commit -m "..."
```
