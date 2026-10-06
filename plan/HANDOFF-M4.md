# HANDOFF-M4（M3 收尾 → M4 内置基准 续接快照）

> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-M4.md 继续完成任务`（相对路径；启动命令由用户侧拼绝对路径）。
> 本快照落盘于 2026-10-06，M3（存储与规则引擎）收尾时。方法论：ai-tool-project-sprint。

## 1. 当前进度（M3 已完成）

- **八规则全量** `rules/checks/`：R-DUP-01/02/03（duplicate.py）、R-SEQ-01（sequence.py）、
  R-ARITH-01/02（arithmetic.py）、R-TIME-01/02（time_rules.py），全部挂规则 ID 与三级语义
  （error/suspicious/review）；注册顺序 = 执行顺序（plan/04 §3.1 固定）：
  DUP-01 → DUP-02 → DUP-03 → SEQ-01 → ARITH-01 → ARITH-02 → TIME-01 → TIME-02。
- **门控互斥**：R-DUP-03 经 ctx["findings"] 取 R-DUP-01/02 已命中号集合做排除（同号副本
  同销售方同日同额不触发）；R-DUP-02 排除纯复制件（语义字段全等判定，
  evidence/confidence/field_flags/batch_id 不参与）——EXACT 只报 01，JOINT 报 02+01。
- **入库与判重分离**（M3 设计决策，plan/04 §3 定稿）：引擎输入 = 全部解析卡（含入库被拒的
  同号副本）；R-DUP-01 = 批内同号多卡 ∪ 台账既有号码（ctx existing_numbers，check 命令入库
  前查询）。Ledger.add_invoice 主键拒收语义不变；create_batch 改 INSERT OR IGNORE（重跑幂等）；
  findings 按 finding_id 幂等拒收。
- **引擎契约扩展**（plan/04 §3.1）：`run(cards, ctx_extra=None)`，三键 batch_anchors /
  default_anchor / existing_numbers；finding_id = rule_id + ":" + "|".join(全部号码)。
- **R-TIME 双通路**：基准通路 `check --anchor-manifest data/ground_truth/manifest.json` 读批次
  expense_anchor；常规通路不传时 default_anchor=导入当天。R-TIME-02 方向定稿：仅追溯
  （issue 早于 anchor 超 N 期），未来票由 R-TIME-01 全覆盖防双报（对拍真值口径）。
- **check 命令** `check <dir> --db ledger.db [--anchor-manifest ...]`：递归扫描（批次=一级
  子目录名）→ 逐文件解析 → 台账入库 → 八规则 → findings 落库 + stdout 三级清单。实测冻结
  数据：57 成功 + OFD 3 顺延 + 拒绝 0；入库 55 + 主键拒收同号副本 2；**13 条三级异常**
  （error 9 / suspicious 2 / review 2）；退出码契约同 parse（坏文件=0，缺依赖/目录不存在=2）。
  parse/check 共用 `_scan_and_parse`（cli.py），卡片入库前已填 batch_id。
- **demo 命令升级端到端**：临时目录生成 60 张 XML 合成票（9 类注入全触发）→ 与 check 完全
  相同的解析+入库+检测流水线（内存库）→ 打印三级清单 → 清理临时目录；零重依赖可跑。
- **基准内检出率 100% 初核**（tests/test_baseline_detection.py）：冻结 60 份 → 引擎 vs
  expect ∪ also_expect 全集按 (号码, rule_id, level) 对拍，58 号码 **0 偏差**（检出率 100%、
  误报 0、级别全对）；13 findings 形态断言（DUP-01×2 DUP-02×1 DUP-03×1 SEQ×1
  ARITH-01×2 ARITH-02×2 TIME-01×2 TIME-02×2）；真值 expectations 与生成器
  INJECTION_EXPECTATIONS 同源对拍；OFD 顺延号码均无规则期望（对账无结构性缺口）。
- **回归证据**：pytest **138 passed**（M2 的 95 + 43：test_rules 8→41、test_cli 11→15、
  test_ledger 4→6、test_baseline_detection 新增 4）；干净 venv（无 pdfplumber/reportlab）
  **129 绿/9 skip = CI 平价预演通过**（skip 全为 PDF/reportlab 依赖路径）。
- schema 与 plan/04 §4 一致（SCHEMA_SQL 未动）；本机 commit：M3 收尾提交（见 git log）。

## 2. M4 待办（内置基准，DoD 见 plan/05 §2 M4 行）

1. **基准脚本** `benchmarks/benchmark.py`（+ CLI `benchmark` 命令接通）：
   - 字段解析基准：冻结 60 份 vs cards.json 字段级对账（复用 benchmarks/field_match.py，
     M2 冻结对账逻辑即测试形态基准）→ 宏平均 P/R/F1 + 分字段表；
   - 异常检测基准：复用 tests/test_baseline_detection.py 对拍逻辑（引擎 vs
     expect∪also_expect 全集）→ 检出率（TP/真值异常）、误报率（FP/全部告警）、
     判定准确率（level 一致占比）；
   - 输出 `benchmarks/report.md`（生成物，README 引用关键表；OFD 3 份顺延显式登记）。
2. **门槛断言**：解析 F1≥0.95（实测 1.0）、检出率 100%、误报 0；零 API 可重复
   （纯规则通路、固定输入、无墙钟——R-TIME 必须走 --anchor-manifest 基准通路）。
3. **回归纪律落地**：改数据/改规则/改接口 → 重跑基准确认不回退（CI 已有测试形态基准，
   M4 补 CLI 形态并考虑 CI 步骤）。
4. **既定口径清单定稿**（见 §3）写入 HANDOFF 速查区收口（plan/05 §3 要求）。
5. 里程碑收尾：plan/00、05 状态回写 ✅；写 plan/HANDOFF-M5.md；本文件头部标注"已过时仅作历史"。
6. （顺带）11号公告/56号令补核：带 JS 渲染抓取 fgk 或省级局全文直链（渠道明细已登记
   data/knowledge JSON），取得即逐字核对改 status；M3 一轮 WebFetch 静态抓取仍未取得原文。

## 3. 既定口径清单（M3 定稿后增量；改前先对照，M4 收口入 HANDOFF）

**M3 新增（规则/引擎/CLI）**：

1. 八规则注册顺序 = 执行顺序（plan/04 §3.1）；DUP 三规则必须在前（R-DUP-03 门控依赖）；
2. 入库与判重分离：引擎输入 = 全部解析卡含被拒副本；R-DUP-01 = 批内重复 ∪ existing_numbers；
3. R-DUP-02 纯复制件判定 = 语义字段全等（evidence/confidence/field_flags/batch_id 不参与，
   与解析对账口径一致）；
4. R-DUP-03 金额 = total_with_tax、amount_tol=0.00、date_window=1d；门控 = DUP-01/02 命中号
   集合；配对 finding 挂双号码；
5. R-SEQ-01：suffix_len=8、min_len=3、date_window=7d；**跨前缀不产出 finding**（M3 定稿）；
6. R-TIME-02 **仅追溯方向**（issue 早于 anchor 超 n_period=3 期报 review）；未来票 R-TIME-01
   全覆盖（防 INJ-TIME-FUTURE 双报误报）；
7. 引擎 run(cards, ctx_extra=None)；ctx 三键 batch_anchors / default_anchor / existing_numbers；
   finding_id = rule_id + ":" + "|".join(invoice_numbers)（无号码用 "-"）；
8. 规则参数键名：arith_tolerance / dup_date_window_days / dup_amount_tol / seq_suffix_len /
   seq_min_len / seq_date_window_days / time_n_period；
9. check 命令：--anchor-manifest 基准通路 / 缺省 anchor=导入当天；退出码契约同 parse
   （坏文件=0，目录不存在/无可解析文件/缺依赖=2）；create_batch 幂等（OR IGNORE）；findings
   按 finding_id 幂等拒收；重复检测需新 --db（重复导入本身是 R-DUP-01 信号）；
10. demo = 端到端（生成→解析→入库→检测，临时目录自清理，内存库）；
11. **冻结数据检测对拍锚点数字**：13 findings（明细见 §1）——数据/规则/引擎任何改动都会
    打挂 tests/test_baseline_detection.py，属预期回归门；
12. 解析层规则函数可硬判边界：字段缺失一律跳过不硬判（越权报 field_flags 属解析层）。

**M0-M2 既有口径全部有效**：InvoiceCard schema（plan/04 §1）、解析映射权威 =
TEMPLATE_REFERENCE（synthetic-v1）、PDF label-slot 三条实测口径、数值清洗/失败语义、
对账口径（evidence/confidence/field_flags/batch_id 不参与；空==空计正确）、confidence 语义、
真值双键与 expect∪also_expect 全集对账、R-DUP-02 排除纯复制件、R-TIME 取批次
expense_anchor、测试纪律（stdlib+pytest 模块级，重依赖函数内 import_optional + 显式 skip）、
核心零依赖、requires-python≥3.8 语法、退出码契约（未交付/缺依赖=2）。

## 4. 本机环境坑（M3 实测增量 + 存量）

- **M3 新增**：pytest `-q` 输出经 bash 管道（grep/tail）时 summary 行偶发被吞——**输出
  重定向到文件后单独 grep**（存量"退出码断言重定向"教训的同源变体，本轮再次踩到）；
- **M3 新增**：会话中断续跑时 Write 工具可能只完成一半（本次 test_rules.py 首写残留旧文件），
  恢复后先 `wc -l`/读尾确认落盘状态再重写；
- **M3 重申**：改解析器/生成器后立即跑冻结对账；改规则/引擎后立即跑 test_baseline_detection
  （13 findings 锚点 + 58 号码对拍，偏差即回归）；
- **存量（仍有效）**：Python 3.8.8 唯一解释器（`py` 即 3.8）；pip 清华镜像 + `NO_PROXY="*"
  no_proxy="*"`；`PYTHONDONTWRITEBYTECODE=1` 全程携带；统一 `py -m invoice_ledger_checker`；
  Git Bash 下 `py -X utf8`，测试内 subprocess 显式 PYTHONIOENCODING=utf-8；pdfplumber 在
  py3.8 上 import 时向 stderr 打 CryptographyDeprecationWarning（无害，比对输出注意过滤）；
  Git Bash `/tmp` 对 Windows Python 不可见（临时目录建仓内）；PySide6 未装（M5 复核 cp38
  wheel）；*.db 已在 .gitignore（测试一律用 tmp_path 或 .tmp_m3，防仓库根残留 ledger.db）。

## 5. M4 DoD checklist（收尾逐项打勾，没做到的写偏差说明）

- [ ] `py -m invoice_ledger_checker benchmark`（或既定参数形态）一条命令出指标表
- [ ] 解析基准：冻结 60 份字段级 F1，宏平均 + 分字段表，F1≥0.95（实测 1.0）
- [ ] 检测基准：检出率 100%、误报 0、判定准确率 100%（expect∪also_expect 全集对拍）
- [ ] 零 API 可重复：纯规则通路、固定输入、无墙钟（R-TIME 走 manifest 基准通路）
- [ ] benchmarks/report.md 生成（OFD 3 份顺延显式登记），README 引用关键表
- [ ] 既定口径清单定稿收口入 HANDOFF 速查区
- [ ] 回归纪律：基准可一键重跑，改数据/规则/接口后不回退
- [ ] pytest 全绿且收集数与 M3 的 138 项对账清楚（新增多少、为何）
- [ ] plan/00、05 状态回写；HANDOFF-M5.md 落盘；本文件标注已过时
- [ ] （顺带）11号公告/56号令补核：取得原文即逐字核对改 status

## 6. 关键命令速查

```
# 测试（全程携带 PYTHONDONTWRITEBYTECODE=1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest

# CLI（安装后；未装则 PYTHONPATH=src py -X utf8 -m invoice_ledger_checker ...）
py -X utf8 -m invoice_ledger_checker demo                      # M3 端到端演示
py -X utf8 -m invoice_ledger_checker doctor
py -X utf8 -m invoice_ledger_checker generate --out data --seed 42 --n 60   # 改生成器后必须重跑并提交冻结数据
py -X utf8 -m invoice_ledger_checker parse data/invoices --report
py -X utf8 -m invoice_ledger_checker check data/invoices --db ledger.db \
    --anchor-manifest data/ground_truth/manifest.json          # M3 已接通（DoD 命令形态）
# 注意：重复对同一 --db 跑 check 会把全部号码判 R-DUP-01（重复导入=异常信号）；基准请用新库

# 冻结对账（改解析器/生成器/规则后必跑）
# pytest 内置：tests/test_parsing.py 字段冻结对账 + tests/test_baseline_detection.py 检测对拍
#              + tests/test_generator.py 位级回归

# 安装（pip 代理规避 + 不写 pyc）
NO_PROXY="*" no_proxy="*" PYTHONDONTWRITEBYTECODE=1 py -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# git（提交前三核对：pwd / git log --oneline -1 / git remote -v）
git add -A && git commit -m "..."
```
