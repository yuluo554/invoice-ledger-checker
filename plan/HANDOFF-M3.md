# HANDOFF-M3（M2 收尾 → M3 规则引擎 续接快照）

> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-M3.md 继续完成任务`（相对路径；启动命令由用户侧拼绝对路径）。
> 本快照落盘于 2026-10-06，M2（解析层）收尾时。方法论：ai-tool-project-sprint。

## 1. 当前进度（M2 已完成）

- **XML 解析器** `parsing/xml_parser.py`：stdlib ElementTree 单次递归遍历；FIELD_MAP
  = localname 相对路径 -> InvoiceCard 字段（权威映射 data/samples/TEMPLATE_REFERENCE.md §1，
  synthetic-v1 即 v1）；命名空间防御（localname 降级匹配 + confidence-0.1 +
  `xml#namespace_localname_fallback`）；数值清洗走 `base.clean_numeric_text` +
  `is_decimal_text`（严格十进制，拒 nan/inf/科学计数法），非法丢值 + `#invalid_number_dropped`
  flag + confidence-0.2，不猜值；可选字段缺席 -> 空串 + `#absent` flag（存在但空 -> `#missing`）；
  主键三要素（invoice_number/invoice_type/issue_date）缺失 -> ParserError；证据 location=节点路径。
- **PDF 解析器** `parsing/pdf_parser.py`：pdfplumber `extract_words()` 词级 + top 分行（2pt 容差）；
  label-slot 三条实测口径（plan/00 决策记录已登记）：①双栏版式 value 词以同线下一标签 x0 为
  右边界（发票号码行的右侧还有开票日期标签）；②`价税合计（大写）：` 与值同词合并（值起点与
  标签尾重叠），取词内冒号后文本，兼容标签/值分词变体；③明细四列按表头行 `项目名称/金额/税率/
  税额` 的 x0 锚点最近列归并（30pt 容差），行界 = 表头与 `合计：` 行之间；`合计：` 值
  `51097.17（税额 4743.68）` 正则拆双值；`（小写）￥X` 剥前缀过数值清洗；票种 = 标题词
  精确反查 TITLE_TO_TYPE（全词匹配，防子串误撞）；结构失败同 XML 纪律；证据 location=页码+y。
- **对账器** `benchmarks/field_match.py`：flatten_card（evidence/confidence/field_flags/
  batch_id 不参与；items 展开为 `items[i].field`）+ compare（P/R/F1 + mismatches；空==空计
  正确——INJ-FIELD-MISS 真值为空串的口径）。M4 字段解析基准直接复用。
- **CLI parse** `py -m invoice_ledger_checker parse <dir> --report`：递归扫描，批次=一级子
  目录名（根级文件批次=根目录名）；OFD 显式"顺延登记"（P2 未交付）；坏文件进拒绝清单不中断；
  退出码契约：目录不存在/无文件/有文件缺依赖=2，坏文件（数据条件）=0。实测冻结数据：57 成功
  （xml 35 + pdf 22）+ OFD 3 顺延 + 拒绝 0。
- **回归证据**：冻结 60 份 vs cards.json 字段级对账 **XML 35/35、PDF 22/22 全部 F1=1.0**
  （DoD 门槛 0.95）；坏文件 7+2 项测试；同号双文件（EXACT batch_01→02、JOINT batch_02→03，
  均 XML）解析不报错且 EXACT 副本字段全等。pytest **95 passed**（M1 的 65 + test_parsing.py
  27 + CLI parse 3）；干净 venv（无 pdfplumber/reportlab）89 绿/6 skip = CI 平价预演通过。
- 本地 commit：M2 收尾提交（见 git log）。

## 2. M3 待办（存储与规则引擎，DoD 见 plan/05 §2）

1. **八规则全量** `rules/checks/`：R-DUP-01/02/03、R-SEQ-01、R-ARITH-01/02、R-TIME-01/02，
   全部挂规则 ID 与三级语义（level ∈ error/suspicious/review）；实现按生成器模块注释 §3/§4
   的 INJECTION_EXPECTATIONS 对齐，测试直接 import 对拍；
2. **门控互斥**（plan/04 §3）：R-DUP-03 排除 R-DUP-01/02 已命中组合；R-DUP-02 排除纯复制件
   （EXACT 只报 01，JOINT 报 02+01；"金额"= total_with_tax，amount_tol=0.00）；
3. **check 命令接通** `check --db ledger.db`：parse -> 台账入库 -> 引擎 -> 三级异常清单落
   findings 表；demo 命令同步升级为端到端演示（parse(M2) -> check(M3) 全规则）；
4. **同号副本语义定稿（M3 设计决策，先改 plan/04 再实现）**：第二份同号文件入库被
   Ledger.add_invoice 拒（返回 False，主键语义），但被拒副本**仍须参与** R-DUP-01/02 判定
   ——建议：引擎输入 = 全部解析卡（含被拒副本），入库与判重分离；否则 INJ-DUP-EXACT/JOINT
   的 expect 永远无法命中；
5. **R-TIME 基准通路**：R-TIME-01/02 取批次 expense_anchor（manifest 固化 batch_01/02/03 =
   2026-07-15/08-15/09-15）——基准可复现前提；实际使用时 anchor=导入时刻，check 命令需提供
   两条通路（基准读 manifest / 常规用当前时间）；
6. **基准内检出率 100% 初核**：expect ∪ also_expect 全集对账（多记=误报、少记=漏报、级别
   不符=错判），正式基准脚本 M4 落，M3 先用测试初核；
7. 里程碑收尾：plan/00、05 状态回写 ✅；写 plan/HANDOFF-M4.md；本文件头部标注"已过时仅作历史"。

## 3. 既定口径清单（M2 定稿后增量；改前先对照）

1. **解析映射权威 = data/samples/TEMPLATE_REFERENCE.md**（与生成器一致，冲突以生成器代码为准
   并回填）；官方样例仍未获取（plan/03 风险表 #1 已收口记录，两套映射切换预案保留）；
2. **PDF label-slot 三条实测口径**（plan/00 决策记录 2026-10-06）：双栏 value 右边界=同线下一
   标签 x0；大写金额同词合并取冒号后文本；明细按表头 x0 锚点最近列归并（30pt）；
3. **数值清洗** = base.clean_numeric_text（全角/千分位/￥¥元 剥离）+ is_decimal_text（严格
   十进制正则）+ Decimal 复核；非法丢值 + `#invalid_number_dropped` + confidence-0.2；
4. **失败语义**：结构失败（无文本层/票种标题不可识别/主键三要素缺失）= ParserError；可选字段
   缺失 = 空串 + `#absent`（节点/标签整体缺席）或 `#missing`（存在但空）；解析层对同号多文件
   一文件一卡不报错（判重交台账主键与规则层）；
5. **对账口径**（benchmarks/field_match.py）：evidence/confidence/field_flags/batch_id 不参与；
   空==空计正确；M2 自测门槛 = 每文件 F1≥0.95（实测 1.0）；
6. **CLI parse 退出码契约**：目录不存在/无可解析文件/文件缺依赖 = 2；坏文件 = 0 + 拒绝清单；
   OFD = 顺延登记（NotImplementedError 语义保留）；
7. **confidence 语义**：ns 降级 -0.1、丢值 -0.2，下限 0；字段级问题只进 field_flags；
8. **M0/M1 既有口径全部有效**：InvoiceCard schema（plan/04 §1）、规则 ID 与三级语义、SQLite
   schema（plan/04 §4）、真值语义权威 = generator/synthetic.py 模块注释、R-DUP-02 排除纯复制
   件、R-TIME 取批次 expense_anchor、R-DUP-03 金额= total_with_tax 精确匹配档、测试纪律
   （stdlib+pytest 模块级，重依赖函数内 import_optional + 显式 skip）、核心零依赖、requires-
   python≥3.8 语法、退出码契约（未交付/缺依赖=2，可用命令=0）。

## 4. 本机环境坑（M2 实测增量 + 存量）

- **M2 新增**：Git Bash 的 `/tmp` 传进 PYTHONPATH 对 Windows Python 不可见（虚拟挂载路径），
  模拟缺依赖测试要在仓库内建临时目录；
- **M2 新增**：bash 管道后 `$?` 测到的是管道末命令（grep/tail）不是 python——CLI 退出码断言
  必须输出重定向到文件后单独 `echo $?`；
- **M2 新增**：fgk.chinatax.gov.cn 已恢复可达但列表/检索为 JS 动态渲染，WebFetch 静态抓取只有
  表头；内容页 URL 无规律不可猜测（试了 404）。11号公告/56号令原文补核下轮建议带 JS 渲染抓取
  或省级局全文直链（渠道明细已登记 knowledge JSON）；
- **M2 新增**：pdfplumber 在 py3.8 上 import 时向 stderr 打 CryptographyDeprecationWarning——
  无害，CLI/测试比对输出时注意过滤；
- **M2 教训**：Edit 工具大段替换发生过一次拼接残留（循环尾巴串进新循环体），靠冻结对账测试
  F1<1.0 当场暴露——**改解析器后立即跑冻结对账**（pytest 已常驻此门）；
- **存量（仍有效）**：Python 3.8.8 唯一解释器（`py` 即 3.8）；pip 清华镜像 + `NO_PROXY="*"
  no_proxy="*"`；`PYTHONDONTWRITEBYTECODE=1` 全程携带；统一 `py -m invoice_ledger_checker`；
  Git Bash 下 `py -X utf8`，测试内 subprocess 显式 PYTHONIOENCODING=utf-8；PySide6 未装（M5
  复核 cp38 wheel）；冻结数据后 data/invoices、ground_truth 无 .gitkeep.md（防冻结回归树不一致）。

## 5. M3 DoD checklist（收尾逐项打勾，没做到的写偏差说明）

- [ ] `py -m invoice_ledger_checker check data/invoices --db ledger.db`（或既定参数形态）一键
      入库+检测，产出三级异常清单（findings 落库 + stdout 清单）
- [ ] 八规则全实现挂规则 ID（04§3 规则表逐条对齐）；三级判定语义与 plan/04 §3 一致
- [ ] 门控互斥：R-DUP-03 排除 R-DUP-01/02；R-DUP-02 排除纯复制件（EXACT 只报 01）
- [ ] 同号副本设计定稿并回写 plan/04（被拒副本仍参与判重）
- [ ] R-TIME 双通路：基准=manifest 批次 anchor，常规=导入时刻
- [ ] 基准内检出率初核 100%（expect ∪ also_expect 全集对账，INJECTION_EXPECTATIONS 导入对拍）
- [ ] schema 与 04§4 一致（现有 SCHEMA_SQL 未动即视为一致，动了要回写）
- [ ] demo 命令升级端到端（parse->check 全规则演示）
- [ ] pytest 全绿且收集数与 M2 的 95 项对账清楚（新增多少、为何）
- [ ] plan/00、05 状态回写；HANDOFF-M4.md 落盘；本文件标注已过时
- [ ] （顺带）11号公告/56号令补核：带 JS 抓取 fgk 或省级局全文直链，取得即逐字核对改 status

## 6. 关键命令速查

```
# 测试（全程携带 PYTHONDONTWRITEBYTECODE=1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest

# CLI（安装后；未装则 PYTHONPATH=src py -X utf8 -m invoice_ledger_checker ...）
py -X utf8 -m invoice_ledger_checker demo
py -X utf8 -m invoice_ledger_checker doctor
py -X utf8 -m invoice_ledger_checker generate --out data --seed 42 --n 60   # 改生成器后必须重跑并提交冻结数据
py -X utf8 -m invoice_ledger_checker parse data/invoices --report           # M2 已接通

# 冻结对账（改解析器/生成器后必跑）
# pytest 内置：tests/test_parsing.py 冻结对账 + tests/test_generator.py 位级回归

# 安装（pip 代理规避 + 不写 pyc）
NO_PROXY="*" no_proxy="*" PYTHONDONTWRITEBYTECODE=1 py -m pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# git（提交前三核对：pwd / git log --oneline -1 / git remote -v）
git add -A && git commit -m "..."
```
