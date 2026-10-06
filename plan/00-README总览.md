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
| [HANDOFF-M3.md](HANDOFF-M3.md) | 交接快照：M2 收尾 → M3 规则引擎续接（已过时留档） | ✅ 2026-10-06 |
| [HANDOFF-M4.md](HANDOFF-M4.md) | 交接快照：M3 收尾 → M4 内置基准续接（已过时留档） | ✅ 2026-10-06 |
| [HANDOFF-M5.md](HANDOFF-M5.md) | 交接快照：M4 收尾 → M5 桌面交付续接（已过时留档） | ✅ 2026-10-06 |
| [HANDOFF-M6.md](HANDOFF-M6.md) | 交接快照：M5 收尾 → M6 脱敏发布续接（含既定口径清单速查区）（已过时留档） | ✅ 2026-10-06 |
| [HANDOFF-FINAL.md](HANDOFF-FINAL.md) | 终版收官快照：M6 完成态 + 全量既定口径速查区 + 后续可捡起项 | ✅ 2026-10-06 |
| [RELEASE-M6.md](RELEASE-M6.md) | M6 脱敏发布留档：脱敏四步/产物本体扫描/元数据邮箱改写/干净环境验证逐项命令与结论 | ✅ 2026-10-06 |

## 附：M5 交付物索引（plan 外）

| 交付物 | 位置 |
|---|---|
| 技术报告（提交材料之一） | [docs/技术报告.md](../docs/技术报告.md) + [docs/make_report_docx.py](../docs/make_report_docx.py)（docx 生成器，产物不入仓） |
| PyInstaller 打包 | [packaging/invoice_ledger_checker.spec](../packaging/invoice_ledger_checker.spec) + entry_gui.py / entry_cli.py |

## 决策记录

| 日期 | 决策 | 结论 |
|---|---|---|
| 2026-10-05 | 选题与形式 | 系列第六题，**形式换挡为桌面应用**（用户要求"做成 app 或电脑程序"）：发票台账+重复报销检测——数电票 XML 解析是开源空白亮点，规则密度高、全离线零 API，与"程序化自制带真值"打法最契合 |
| 2026-10-05 | 技术栈 | Python + PySide6（QtCharts）+ SQLite（FTS 可选）+ openpyxl + reportlab（生成器）+ PyInstaller 打包；LLM 仅可选兜底，非必需 |
| 2026-10-05 | 仓库名与发布 | `invoice-ledger-checker`，GitHub 公开；Release 附 Windows exe |
| 2026-10-05 | 政策依据 | 11号公告/764号令/56号令已查证（见 01 §五），条文入库时逐条挂出处 |
| 2026-10-06 | 真值语义定稿 | 双键真值（cards 按文件路径、expectations 按号码）；基准按全部非 pass 集合对账；R-DUP-02 排除纯复制件（只报 R-DUP-01）；R-TIME 基准通路取批次 expense_anchor（与墙钟无关）；权威出处 = generator/synthetic.py 模块注释 |
| 2026-10-06 | 法规查证收口 | 764号令/《发票管理办法》修订原文已直连核对入库；11号公告/56号令原文未直连成功 → 条文标"待核对"+登记渠道，不空转（M2+ 补核） |
| 2026-10-06 | **M5 法规补核突破（收口）** | 11号公告/56号令**原文全文取得并逐字核对，status 转「已核对」**：11 号公告 = fgk `content.html` 后缀 + 浏览器 UA/Accept-Language 直连（HTTP 200）→ 本地剥 HTML 提取，核对第一/二/三/四/十一/十二条；56 号令 = fgk **PDF 附件直链**（HTTP 200 / 17 页）→ pdfplumber 本地提取，核对新增第三/四/五条 + 原第四条改第七条。**两处订正**：①11 号公告官方标题无「的」字；②11 号公告正文与附件**不含 XML 格式条款**（此前表述实出自上海局解读页，引用不得挂条号）。**经验固化**：fgk 的 `content.html` 后缀与 PDF 附件直链是该域最可靠可达形态（无后缀内容页仍被 WAF 挑战页拦截）；检索摘要仅用于定位候选直链，可达性与条文一律 curl 落盘+本地提取。11 号公告新增入库 20 位号码法定分段（2+2+1+15，与生成器号码布局一致） |
| 2026-10-06 | 解析层映射与实现定稿 | 字段映射权威 = TEMPLATE_REFERENCE（synthetic-v1）；PDF label-slot 实测固化三条口径：双栏版式 value 词以同线下一标签 x0 为右边界、`价税合计（大写）：` 与值同词合并取冒号后文本、明细四列按表头 x0 锚点最近列归并；对账器落 benchmarks/field_match.py（M4 基准同源复用） |
| 2026-10-06 | M3 规则语义定稿 | 入库与判重分离（引擎输入=全部解析卡含被拒副本，R-DUP-01=批内重复+台账既有号码）；R-DUP-02 纯复制件判定=语义字段全等（evidence/confidence/field_flags/batch_id 不参与）；R-TIME-02 仅追溯方向（未来票 R-TIME-01 全覆盖防双报）；R-SEQ-01 跨前缀不产出 finding；R-TIME 双通路（基准=manifest 批次 anchor / 常规=导入时刻）；详见 plan/04 §3/§3.1 |
| 2026-10-06 | M4 基准定稿 | 基准模块 benchmarks/benchmark.py（复用 field_match.py 同口径，逐文件与 compare 一致性内部断言）；指标语义：检出率=TP/真值异常、误报率=FP/全部告警、判定准确率=级别一致三元组/真值异常（对账键=(号码,rule_id)，级别并入三元组）；门槛=F1≥0.95、检出率 100%、误报 0、判定准确率 100% + 零容忍项（冻结数据解析失败/未知号码告警/批次锚点缺失）；`benchmark` 退出码 0/1（门槛未达）/2（参数或缺依赖）；报告 benchmarks/report.md 无墙钟（无时间戳/路径/环境，同输入逐字节一致，守门测试断言）；R-TIME 基准只走 manifest 批次 anchor（禁 default_anchor 墙钟兜底，缺映射列为门槛失败）；CI 增 benchmark 作业（win-3.8 + parse/data extras） |
| 2026-10-06 | M5 桌面交付选型复核 | PySide6 6.6.3.1 cp38-abi3 wheel 实测可用（`>=6.5,<6.7` 解析命中；6.7+ requires-python≥3.9），QtCharts 在 PySide6-Addons 离屏冒烟通过；PyInstaller `>=6,<7`（实测 6.22.3）——plan/03 §3 待核对标注消除 |
| 2026-10-06 | M5 打包构建解释器通道 | 本机唯一解释器 3.8.8 跑 PyInstaller 构建出现构建工具级不稳定（modulegraph 字节码扫描层 re.error / Instruction not iterable / Constant 缺 value / SubprocessDied 0xC0000005 / 段错误 139，清 pyc + 换 venv 均不解，与项目代码零关联）→ 改用 **Python 3.12.10 干净 venv**（PyInstaller 6.22.3 + PySide6 6.11）构建一次成功。**冻结产物与构建解释器绑定，与项目源码运行时底线 3.8 无关**——源码 3.8 兼容性由 CI win-3.8 矩阵继续守 |
| 2026-10-06 | M5 GUI 单一事实源纪律 | GUI 只消费既有 CLI/引擎 API（cli._scan_and_parse / _run_check_pipeline + storage.Ledger 查询），不另起第二套行为；检测参数默认值单一来源 = 各规则模块 `DEFAULT_*` 常量（GUI 设置页 `_reset_params` 反向 import 该常量）；引擎参数经 `_run_check_pipeline(engine_params=)` 注入 |
| 2026-10-06 | M5 CI 作业分工 | `test`（win3.8/win3.12/ubuntu3.12，仅 dev extras，GUI/PDF 用例声明式跳过）+ `desktop`（win-3.8，装 desktop+export extras 使 GUI/导出测试真正执行，防"双绿但悄悄少跑"）+ `benchmark`（win-3.8，基准门槛）。改 CI 装机清单会改变 skip 计数口径 |
| 2026-10-06 | **M6 脱敏发布** | 脱敏四步 + 产物本体扫描 + 提交元数据邮箱改写（真实个人邮箱全历史 → GitHub noreply）逐项留档 `plan/RELEASE-M6.md`；扫描器 `tools/sensitive_scan.py` 入仓（五模式 + dist 产物模式 + selftest 阳性/阴性双对照 + 输出掩码化）。**第 0 步结论：前作五题全部 public → 保留系列表述、不做掩码** |
| 2026-10-06 | **M6 干净环境门抓出的两个真问题（均已修复 + 回归锁）** | ① `data` extras 未锁 reportlab 上界 → 3.8 上 `generate` TypeError（`usedforsecurity` 是 py3.9 参数），且会打挂**从未跑过**的 CI win-3.8 作业 → 改**双向环境标记**（py<3.9 锁 <4、py≥3.9 放开；统一锁 <4 会打挂 3.12，实测 3.6.13 无 wheel）② 冻结 exe 缺 pdfplumber（`utils.import_optional` 惰性导入对 PyInstaller 静态分析不可见，spec 只声明了 openpyxl）→ 发行包解析不了 PDF（`check` 退出码 2、GUI 导入通路同坏）→ spec `hiddenimports` 补齐。**方法论收获**：M5 记录的"CLI 五连全过"是把**管道退出码**当成了 exe 退出码（假绿），关键命令必须单跑取真实退出码 |
| 2026-10-06 | M6 产物扫描形态 | `dist` 模式只跑**强标记**（个人标记/姊妹词，以 `--marker-b64` 现场传入、字面值不入仓）+ 禁区成分复核；刻意不跑邮箱/手机号宽正则（上游厂商 DLL/SBOM 公共串与二进制噪声非本项目泄漏面）。产物与发布源码同基线以 `git diff <里程碑>..HEAD -- src/` 为空为据 |

## 里程碑

- **M0 计划+骨架 ✅（2026-10-05）**：plan 02-06 定稿；src 布局骨架（models/parsing/storage/rules/generator/benchmarks/export/app + CLI）；种子规则 R-ARITH-01/R-DUP-01；25 项测试全绿；`py -m invoice_ledger_checker demo/doctor` 可用；CI（win 3.8/3.12 + ubuntu 3.12）；MIT + README + .gitattributes(EOL 门)
- **M1 数据先行 ✅（2026-10-06）**：合成发票生成器（5 类型 × XML/PDF/OFD 三格式，seed 可复现位级一致）；9 类注入 + 基线全落地，真值 JSON（cards/expectations/manifest）语义定稿；`generate --out data --seed 42 --n 60` 冻结 60 份入仓；法规知识库（764号令已核对、11号公告/56号令待核对挂渠道）；数据台账四行登记齐；65 项测试全绿
- **M2 解析层 ✅（2026-10-06）**：XML 解析器（FIELD_MAP localname 路径映射 + 命名空间降级 + 数值清洗丢值降置信）+ PDF 解析器（pdfplumber 词级 label-slot，双栏截断/大写合并词/明细 x 列聚类）→ InvoiceCard；`parse data/invoices --report` 一键全量（57 成功 + OFD 3 顺延登记，坏文件拒绝清单，缺依赖 exit 2）；冻结 60 份对账 XML 35/35、PDF 22/22 字段级 F1=1.0（门槛 0.95）；坏文件路径 7 项测试；pytest 95 项全绿（干净 venv 89 绿/6 skip = CI 平价）
- **M3 规则引擎 ✅（2026-10-06）**：八规则全量（DUP-01/02/03、SEQ-01、ARITH-01/02、TIME-01/02，三级语义 + 门控互斥：DUP-03 排除 DUP-01/02 命中号、DUP-02 排除纯复制件）；入库与判重分离（被拒副本仍参与判定）；R-TIME 双通路（manifest 批次 anchor / 导入时刻）；`check --db` 一键解析→入库→检测→findings 落库 + 三级清单；demo 升级端到端；冻结 60 份对拍 expect∪also_expect 全集：检出率 100%、误报 0、级别全对（13 findings）；pytest 138 全绿（干净 venv 129 绿/9 skip CI 平价）；M3 语义定稿回写 plan/04 §3/§3.1
- **M4 内置基准 ✅（2026-10-06）**：benchmarks/benchmark.py 双基准（字段级解析 P/R/F1 复用 field_match.py + 异常检测检出率/误报率/判定准确率按 expect∪also_expect 全集对拍）+ 门槛断言 + 确定性报告；`benchmark` 一条命令出指标表（退出码 0/1/2 契约）；冻结 60 份实测宏平均 F1=1.0000、检出率 100%（18/18）、误报 0、判定准确率 100%（13 findings 形态同 M3 锚点）；报告落 benchmarks/report.md（同输入重跑逐字节一致，OFD 3 份顺延显式登记）；README 回填指标表；CI 增 benchmark 作业；pytest 144 绿（干净 venv 131 绿/13 skip）；既定口径清单收口入 HANDOFF-M5
- **M5 桌面交付 ✅（2026-10-06）**：PySide6 6.6.3.1（cp38-abi3 wheel 实测复核回写 plan/03 §3）六页签桌面应用（导入向导/台账多维筛选分页+增删改查/异常清单级别着色+证据面板/看板 QtCharts 三图/Excel 导出对话框/设置参数+状态栏免责声明常驻）；Excel 导出 `export` 命令（openpyxl 双 sheet + 三级条件格式标红，样式用例断言）；CLI `export`/`app` 双命令接通（stub 清零）；extras 覆盖运行期 import 静态+动态断言测试 6 项；PyInstaller onedir **双 exe**（GUI console=False 双击即用 + CLI console=True 无 Python 机器脚本化通路）主 spec 入仓，**3.12 干净 venv 构建通道**（3.8 构建工具级不稳定 7 种"不可能错误"连崩，与项目代码无关，详见 HANDOFF-M6 §4）；干净环境（中立目录 + `env -i` 剥离 PATH）CLI 五连（doctor/demo/generate/check/export）+ GUI 冒烟探针（2.2s）实测通过；技术报告 docs/技术报告.md + docx 生成器脚本（程序化生成禁手改，产物不入仓）；CI 增 `desktop` 作业（装 desktop+export extras 使 GUI/导出测试真正执行）；pytest **170 全绿**（=M4 144 + 26：export 4/app 10/extras 6/packaging 5/cli 净 +1），干净 venv 160 收集/143 绿/18 skip（差 10 = test_app.py 模块级 skip 收成 1 条目，逐项归因）；benchmark 门槛全过不回退；演示 GIF 顺延 M6 初
- **M6 脱敏发布 ✅（2026-10-06）**：脱敏四步（第 0 步姊妹表述核实——前作五题**全部 public** → 无需掩码；第 1 步密钥/凭据扫描为空；第 2 步内容级扫描工具化 `tools/sensitive_scan.py`——tracked/history/binaries/messages/metadata 五模式 + 产物树 `dist` 模式 + selftest 阳性/15 阴性双对照 + 掩码化输出 + 正则片段拼接，自测抓出并修掉 4 处检测器缺陷）+ 二进制样例单独扫（PDF Info 元数据域：Author=anonymous / Producer 厂商串 / **CreationDate 固定 2000-01-01**；OFD zip 条目 + 固定 1980 时间戳 + 空 comment）+ 产物本体扫描（378 文件/184.3 MB，4 强标记 + 禁区成分 0 命中；产物与发布源码同基线 `git diff src/` 为空；Release zip sha256 留档）+ **提交元数据邮箱全历史改写** GitHub noreply（含个人目录字面量同改；全对象库深度扫描 0 命中；fsck 干净；`data/` 树哈希不变）；**干净环境验证为发布门核心**（新 clone + 新 venv 逐条跑通 README，**抓出 2 个发布阻断缺陷**：① `data` extras 未锁 reportlab 上界 → 3.8 上 `generate` TypeError（并会打挂从未跑过的 CI win-3.8 作业），修成双向环境标记 + 分层位级守门；② 冻结 exe 缺 pdfplumber（惰性导入未进 hiddenimports）→ 发行包 `check` 退出码 2、台账不生成、GUI 导入通路同坏，修复后六命令真实退出码全 0）；计数对账 dev **177** = 干净 venv 168 + 9（test_app 模块级 skip 收成 1 条目，19 skip 逐项指认）；基准不回退（F1=1.0000 / 检出 100% / 误报 0）；逐项证据留档 [RELEASE-M6.md](RELEASE-M6.md)、交接见 [HANDOFF-FINAL.md](HANDOFF-FINAL.md)
