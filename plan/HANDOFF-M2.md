# HANDOFF-M2（M1 收尾 → M2 解析层 续接快照）

> **【已过时，仅作历史】M2 已于 2026-10-06 完成**：解析层交付、60 份冻结数据对账 F1=1.0、
> pytest 95 项全绿，DoD 逐项打勾见 §5。续接请读 [HANDOFF-M3.md](HANDOFF-M3.md)。
> 本文其余内容定格在 M1 收尾时点，不再更新。

> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-M2.md 继续完成任务`（相对路径；启动命令由用户侧拼绝对路径）。
> 本快照落盘于 2026-10-06，M1（数据先行）收尾时。方法论：ai-tool-project-sprint。

## 1. 当前进度（M1 已完成）

- **合成发票生成器** `generator/synthetic.py`：5 类型（数电普/专票、电子普票、纸质专/普票）× 3 格式（XML 直出 / reportlab 版式 PDF（invariant=1 + STSong-Light 文本层）/ OFD 简化 zip）；唯一随机源 `random.Random(seed)`，同参数输出**逐字节一致**（守门测试已断言，PDF 含内）；`cn_amount.py` 中文大写金额转换器（生成器与 R-ARITH-02 共用，组单位挂组尾算法）。
- **注入与真值**：9 类注入 + 基线全落地（INJ-DUP-EXACT/JOINT/FUZZY、INJ-SEQ、INJ-ARITH-SUM/CN、INJ-TIME-FUTURE/STALE、INJ-FIELD-MISS）；真值双键：`cards.json`（按文件路径）+ `expectations.json`（按号码，expect/also_expect/missing_fields）+ `manifest.json`（seed/批次锚/文件清单）；**真值语义权威定稿写在生成器模块注释**（§3 注入->期望映射表 `INJECTION_EXPECTATIONS` 可被测试导入对拍）；生成期不变量自检（`_verify_invariants`）+ 测试侧独立复核双保险。
- **冻结数据入仓**：`py -m invoice_ledger_checker generate --out data --seed 42 --n 60` → 60 份（XML×35/PDF×22/OFD×3，batch_01/02/03），21 注入 + 39 基线；同参数重跑位级一致（冻结回归测试比对入仓数据 vs 现场生成）。
- **法规知识库** `data/knowledge/`：764号令/《发票管理办法》修订 **已核对**（上海税务局 + 商务部政策库直连，6 条原文）；11号公告/56号令 **待核对**（要点入库 + 渠道登记，M2+ 补核）；入库纪律见 knowledge/README.md。
- **数据台账** `data/README.md` 四行回写 ✅；`data/samples/` 样张 + TEMPLATE_REFERENCE.md（三格式字段映射，M2 权威出处）。
- **验证证据**：pytest **65 passed**（对账：M0 的 25 项 + cn_amount 19 + 生成器 19 + CLI generate 新增 2；本机含 reportlab/pdfplumber，CI 无重依赖路径同样全绿——生成器测试 stdlib 可跑，PDF 相关显式 skip）；demo/doctor 回归正常；generate exit 0、坏 formats exit 2。
- 本地 commit：M1 收尾提交（见 git log）。

## 2. M2 待办（解析层，DoD 见 plan/05 §2）

1. **XML 解析器** `parsing/xml_parser.py`：ElementTree；字段映射按 `data/samples/TEMPLATE_REFERENCE.md`（生成器模板即权威映射 v1）；数值清洗（千分位/全角/￥剥离，非法 Decimal 丢弃+降置信度）；FIELD_MAP 节点路径 -> InvoiceCard 字段；证据记录（location=节点路径）；
2. **PDF 解析器** `parsing/pdf_parser.py`：pdfplumber `extract_words()` label-slot（标签词典 = TEMPLATE_REFERENCE §2 标签全集）；大写金额行截取；明细按 x 坐标列聚类；失败语义（结构失败抛 ParserError、单字段缺失空串+flag，**不猜值**）；
3. **批量解析报告**：CLI `parse data/invoices --report` 接通（stub 摘除）；按批次目录导入语义（batch_id=目录名）；
4. **回归与门槛**：全量 60 份解析 vs cards.json 字段级对账（M2 内自测 F1，正式基准 M4 落）；坏文件路径测试（空 XML/无号码 PDF/二进制垃圾）→ ParserError/拒绝入库日志；
5. **R-DUP-03/FUZZY 联动注意**：解析层不得对同号双文件报错（EXACT/JOINT 副本跨批次同号是预期数据），交台账主键与规则层处理；
6. 里程碑收尾：plan/00、05 状态回写 ✅；写 plan/HANDOFF-M3.md；本文件头部标注"已过时仅作历史"。

## 3. 既定口径清单（M1 定稿后增量；改前先对照）

1. **真值语义权威出处 = generator/synthetic.py 模块注释**（M1 定稿）：双键真值、基准按全部非 pass 集合对账、`INJECTION_EXPECTATIONS` 映射表；
2. **R-DUP-02 排除纯复制件**（plan/04 §3 已回填）：EXACT 副本只报 R-DUP-01；JOINT 再制票报 R-DUP-02 + also R-DUP-01；
3. **R-TIME-01/02 基准通路取批次 expense_anchor**（manifest 固化 batch_01/02/03 = 2026-07-15/08-15/09-15），不依赖墙钟——基准可复现前提；
4. **R-DUP-03 的"金额"= total_with_tax**，amount_tol=0.00（精确匹配档）；
5. **生成器全局不变量**（测试断言，动生成器必重冻结 data/）：同 seed 位级一致；号码唯一（副本除外）；价税合计唯一（FUZZY 对除外）；基线号码后缀间隔≥2（防伪连号）；基线日期在 anchor-55 天内、STALE≥180 天、FUTURE≥+180 天；
6. **PDF 产物 reportlab invariant=1**：位级可复现但依赖 reportlab 版本——冻结回归测试在无 reportlab 环境 skip（CI），本机/M6 干净环境验证；
7. **EOL 门口径**：CR 检查只作用文本文件（loose XML/JSON/MD + OFD 内部成员）；PDF/OFD 本体是二进制容器不在门内（git text=auto 对二进制不转换）；
8. **M0 既有口径全部有效**：InvoiceCard schema（plan/04 §1）、规则 ID 与三级语义、SQLite schema（plan/04 §4）、测试纪律（stdlib+pytest 模块级，重依赖函数内 import_optional + 显式 skip）、核心零依赖、requires-python≥3.8 语法、退出码契约（未交付/缺依赖=2，可用命令=0）。

## 4. 本机环境坑（M1 实测增量 + M0 存量）

- **M1 新增**：冻结数据后删除了 data/invoices、data/ground_truth 的 .gitkeep.md（否则冻结回归测试树不一致）；data/knowledge、data/samples 的 .gitkeep.md 已随内容落盘删除；
- **M1 新增**：WebFetch 直连 beijing.chinatax.gov.cn 两次超时、fgk.chinatax.gov.cn 配额受限——11号公告/56号令原文补核留给 M2+ 会话（渠道已登记 knowledge JSON）；
- **存量（仍有效）**：Python 3.8.8 唯一解释器（`py` 即 3.8）；pip 走清华镜像 + `NO_PROXY="*" no_proxy="*"`；`PYTHONDONTWRITEBYTECODE=1` 全程携带；`invoice-ledger.exe` 不在 PATH → 统一 `py -m invoice_ledger_checker`；系统已有 pdfplumber/reportlab/openpyxl/docx 存量包（doctor"已安装"≠extras 正确，M6 干净环境是唯一真证据）；PySide6 未装（M5 复核 cp38 wheel）；Git Bash 下 `py -X utf8`，测试内 subprocess 显式 PYTHONIOENCODING=utf-8。

## 5. M2 DoD checklist（收尾逐项打勾，没做到的写偏差说明）

- [x] `py -m invoice_ledger_checker parse data/invoices --report` 一键全量解析，产出报告（各批次/格式成功数、坏文件清单）——实测 57 成功 + OFD 3 顺延登记，拒绝清单为无；缺依赖 exit 2、坏目录 exit 2
- [x] XML 解析器：60 份 XML 全解析成功，字段与 cards.json 对账 F1 初测 ≥0.95——35 份 XML 全部 F1=1.0
- [x] PDF 解析器：22 份 PDF 全解析成功（pdfplumber label-slot），同一 F1 门槛——22 份全部 F1=1.0
- [x] OFD：P2 顺延可接受，但 stub 状态在报告中显式登记——报告含"OFD 顺延登记： 3 个文件未解析"
- [x] 坏文件路径有测试（空 XML/无号码/垃圾字节 → ParserError 或日志拒绝，不崩溃）——7 项测试 + PDF 手工极简 PDF/垃圾字节 2 项
- [x] 解析层对同号双文件（EXACT/JOINT 副本）不报错，批次语义 = 目录名——冻结测试断言 EXACT 副本字段全等
- [x] pytest 全绿且收集数与 M1 的 65 项对账清楚（新增多少、为何）——95 项 = 65 + test_parsing.py 27（冻结对账×2/同号双文件/清洗×13 参数化/XML 单元×4/坏文件×7/OFD stub×1）+ CLI parse 3；干净 venv（无 pdfplumber/reportlab）89 绿/6 skip 验证 CI 平价
- [x] plan/00、05 状态回写；HANDOFF-M3.md 落盘；本文件标注已过时
- [x] （顺带）11号公告/56号令补核：fgk.chinatax.gov.cn 检索原文，knowledge JSON status 更新——**偏差说明**：补核已执行并登记（fgk 当日恢复可达但为动态加载站点，静态抓取无条目；上海局官方解读页二次直连复核要点一致；多引擎未获官方原文直链），原文全文仍未直连取得，两条 status 维持"待核对"，渠道明细与下轮建议已回填 knowledge JSON 与 knowledge/README.md

## 6. 关键命令速查

```
# 测试（全程携带 PYTHONDONTWRITEBYTECODE=1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest

# CLI（安装后；未装则 PYTHONPATH=src py -X utf8 -m invoice_ledger_checker ...）
py -X utf8 -m invoice_ledger_checker demo
py -X utf8 -m invoice_ledger_checker doctor
py -X utf8 -m invoice_ledger_checker generate --out data --seed 42 --n 60   # M1 已接通；改生成器后必须重跑并提交冻结数据

# 安装（pip 代理规避 + 不写 pyc）
NO_PROXY="*" no_proxy="*" PYTHONDONTWRITEBYTECODE=1 py -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# git（提交前三核对：pwd / git log --oneline -1 / git remote -v）
git add -A && git commit -m "..."
```
