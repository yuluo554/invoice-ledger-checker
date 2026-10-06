# HANDOFF-M6（M5 收尾 → M6 脱敏发布 续接快照）〔已过时：M6 已完成，见 HANDOFF-FINAL.md〕

> ⚠️ **本文件已过时留档**：M6 已于 2026-10-06 完成（脱敏发布全流程 + 干净环境验证抓出并修复
> 2 个发布阻断缺陷）。当前态、全量既定口径与后续可捡起项见 **[HANDOFF-FINAL.md](HANDOFF-FINAL.md)**；
> 发布逐项证据见 **[RELEASE-M6.md](RELEASE-M6.md)**。本文保留 M5→M6 交接时的原始判断（含若干
> 事后被修正的预期，如"exe 五连全过""CI 四作业"等，实际结论以 RELEASE-M6 为准）。
>
> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-M6.md 继续完成任务`（相对路径；启动命令由用户侧拼绝对路径）。
> 本快照落盘于 2026-10-06，M5（桌面交付）收尾时。方法论：ai-tool-project-sprint。
> 发布类里程碑额外要求：脱敏四步 + 干净环境验证逐项留档；发布后用 GitHub 全新 clone 复核。

## 1. 当前进度（M5 已完成）

- **环境复核（M5 首项）**：PySide6 **6.6.3.1** 发 cp38-abi3 wheel 且为 `<6.7` 内最新可解析版
  （`pip download` 实测）；QtCharts（PySide6-Addons 6.6.3.1）离屏冒烟通过；PyInstaller
  `>=6,<7` 实测 6.22.3。plan/03 §3 "待核对"标注已消除，plan/06 决策行已回写。
- **Excel 导出** `export/excel.py`（openpyxl，extras: export）：发票台账 sheet + 异常清单
  sheet；条件格式三分支（error=红 `FFC7CE` / suspicious=黄 `FFEB9C` / review=蓝 `BDD7EE`，
  整行着色）+ 字段标记非空浅黄提示；金额列转数值单元格；`export_findings_xlsx` 供 GUI 复用。
  CLI `export <db> [--out]` 接通（缺 openpyxl=exit2，db 不存在=exit2）。
- **GUI** `app/`（PySide6；六页签，plan/04 §6）：`main.py`（MainWindow + AppContext +
  DEFAULT_ENGINE_PARAMS + run_app）/ `tabs.py`（ImportTab/LedgerTab/FindingsTab/DashboardTab/
  ExportTab/SettingsTab）/ `models.py`（两个 QAbstractTableModel）/ `dialogs.py`（编辑/详情/导入摘要）。
  状态栏常驻数据库路径 + 免责声明。CLI `app [--db]` 接通（PySide6 与 PySide6.QtCharts 双门）。
- **storage 扩展**（GUI 数据源）：`query_invoices`（多维筛选+分页）、`distinct_months/types`、
  `get_invoice/delete_invoice/update_invoice_fields`、`set_finding_status`、`monthly_stats/
  top_sellers/type_distribution`；`list_findings` 增 `created_at` 键。
- **cli 抽出可复用流水线**：`_scan_and_parse`(M3 已有) / **`_register_batches`（新）** /
  **`_run_check_pipeline(..., engine_params=)（加参）**——GUI 导入复用同一实现（单一事实源）。
- **PyInstaller 打包**：`packaging/invoice_ledger_checker.spec`（onedir **双 exe**）+
  `entry_gui.py`（console=False，崩溃兜底写日志+原生消息框；`INVOICE_LEDGER_GUI_SMOKE=1`
  冒烟探针 1.5s 自动退出）+ `entry_cli.py`（console=True，无 Python 机器脚本化通路）。
  datas 白名单为空（运行期不依赖仓库数据，版权红线不入包）；hiddenimports=["openpyxl"]。
- **打包实测（干净环境）**：dist 182M→158M；中立目录（`%LOCALAPPDATA%\Temp\ilc-clean`）+
  `env -i` 剥离 PATH 下 CLI 五连全过：doctor / demo（60 卡 13 异常）/ generate / check /
  export（10 张 7 条）；GUI 冒烟探针 2.2s（= Qt 启动 + 1.5s 定时）= 事件循环真跑过。
- **技术报告** `docs/技术报告.md`（9 节：概述/解析方案/检测算法/数据先行/打包与离线设计/
  桌面形态/质量保障/限制与边界/复现命令）+ `docs/make_report_docx.py`（md→docx 程序化生成，
  md 为唯一定稿源、禁手改产物，产物 `.gitignore` 排除）；实测生成 head 20 个 / table 1 个。
- **CI**：新增 `desktop` 作业（win-3.8，装 `[dev,parse,data,export,desktop]` extras 使 GUI/
  导出测试**真正执行**——主 test 作业只装 dev，test_app.py 模块级 skip 收成 1 条目）。
- **测试**：pytest **170 全绿**（= M4 144 + 26：test_export 4 / test_app 10 / test_extras 6 /
  test_packaging 5 / test_cli 净 +1[删 1 stub 测试 + 加 2 export 测试]）。
- **干净 venv 对账**（纪律：dev 与干净环境收集数一致、差异逐项归因）：干净 venv（仅 pytest）
  **160 收集 / 143 绿 / 18 skip / 0 失败**；差 10 = `test_app.py` 模块级 `importorskip("PySide6")`
  把 10 项收成 1 个 skip 条目（运行输出 161 项 = 160 收集 + 1 模块级 skip）。
  18 skip 明细：test_app 1（模块级）+ pdfplumber 11（parsing 3 / baseline_detection 2 /
  benchmark 4 / cli 2）+ reportlab 2（generator）+ openpyxl 2（export）+ PySide6 1（extras 的
  QtCharts 模拟测试 1）+ test_cli 导出管线 1。**修掉干净 venv 首跑抓到的 2 个测试卫生 bug**
  （导出 CLI 测试缺 openpyxl 守卫、QtCharts 测试缺 PySide6 守卫）——干净环境门的价值实证。
- **基准不回退**：`benchmark --no-report` exit 0，宏平均 F1=1.0000 / 检出率 100% / 误报 0 /
  判定准确率 100%，门槛全过。
- **README 回填**：状态行 M0-M5 ✅、特性表 M5 四项、桌面应用节、快速开始（export/app/打包）、
  技术报告链接、限制与已知环境问题节（OFD 顺延/PDF 文本层/构建解释器通道偏差/CI 三作业分工）。
- **法规补核突破（原 M4 起挂起的顺带项，M5 完成）**：11 号公告与 56 号令**原文全文取得并逐字
  核对，status 全部转「已核对」**——① 11 号公告 = fgk `content.html` 后缀 + 浏览器 UA
  (`/zcfgk/c100012/c5236067/content.html`，HTTP 200)；核对第一/二/三/四/十一/十二条，**新增入库
  20 位号码法定分段（2+2+1+15，与生成器号码布局结构一致）**；② 56 号令 = fgk **PDF 附件直链**
  （HTTP 200 / 17 页），pdfplumber 本地提取；核对新增第三/四/五条 + 原第四条改第七条。
  **两处订正**：11 号公告官方标题无「的」字；11 号公告正文与附件**不含 XML 格式条款**（此前
  "格式条款"表述实出自上海局解读页，引用不得挂条号）。**经验固化**：fgk 的 `content.html`
  后缀与 PDF 附件直链是该域最可靠可达形态（无后缀内容页仍被 WAF 挑战页拦截）；检索摘要仅用于
  定位候选直链，可达性/条文一律 curl 落盘 + 本地提取。回写：`data/knowledge/*.json` 两份 +
  `data/knowledge/README.md` 补核履历 + plan/00 决策行 + plan/05 §1.4 + README 特性表。

## 2. M6 待办（脱敏发布，DoD 见 plan/05 §2 M6 行 + skill 阶段 7）

1. **脱敏四步 + 产物本体扫描 + 提交元数据邮箱**（skill 阶段 7，缺一不可，逐项留档
   `plan/RELEASE-M6.md`）：
   - 姊妹/系列表述处置：本项目 plan/00 头行枚举前作名称与领域——**先核实前作是否已公开**
     （`gh api users/<owner>/repos`），未全公开则掩码为"同系列第 N 题"（前作词表 base64 入
     扫描器）；
   - `git ls-files` 密钥/凭据扫描为空；内容级扫描全部跟踪文本（密钥/手机号/身份证/个人目录
     前缀/内网 IP/邮箱）——**最高频藏点 = HANDOFF 用法行**，本批 HANDOFF 已全用相对
     路径（M1-M6 一律 `plan/HANDOFF-Mx.md`），提交前复核一遍；
   - 扫描器做成入仓可复跑工具（selftest 阳性对照 + tracked/history/messages 三模式，
     模式用片段拼接构造、输出掩码化"文件:行号 [类别] x次数"）；
   - **提交元数据邮箱必须单独查**：`git log --format="%ae %ce" --all | sort -u`——
     plan/06 已登记本地 git 身份为真实个人邮箱，M6 发布前 filter-branch `--env-filter` 全历史
     改写 GitHub noreply（`gh api user --jq .id`）+ 本地 config 同步；若 plan/06 决策行正文也
     写了邮箱字面值 → `--env-filter` 与 `--tree-filter` 并进同一条 filter-branch 一次跑完；
   - 终验三扫全 0：`git rev-list --all` 逐提交 grep + `git log --all -p` 计数 + 提交信息扫描；
     扫描模式避免 `/` 起始形式（MSYS 静默转写 → 假 0 命中）、先跑阳性对照。
2. **干净环境验证（发布门核心）**：临时 clone（新目录）+ 全新 venv，按 README 快速开始**逐条
   原味执行**（3.8 老 pip 20.2.3 需先 `pip install -U pip` 才可编辑安装 pyproject-only 项目；
   系统 env 还需 `pip install -U setuptools wheel` 防 `invalid command 'bdist_wheel'`）；
   全量 pytest 分批跑完 + 收集数对照（dev 170 = 干净 160 + 10 GUI 模块级 skip，逐项指认 skip 原因）；
   暴露的每个问题修复后**必加回归测试**；验证用临时 clone 用完即删（防邮箱改写前的残留历史对象混入）。
3. **CI 首跑全绿 + `gh run list` 对账 push 数=run 数**；新增的 `desktop` 作业是**未实测过的
   作业**（本地无法验证 CI 的 Qt 环境），首跑预算"诊断+修复+再推一轮"；失败面本身指认类型
   （windows 全挂 + ubuntu 全过 = 代码页/EOL/路径类）。
4. **建仓与 push**：`gh repo create <u>/<r> --public --description "…" --source . --remote origin`
   （**不带 `--push`**，防 workflow scope 半失败态）→ `ssh -T git@github.com` 验证 key →
   `git remote set-url origin git@github.com:<u>/<r>.git` → push 一次成。
5. **Release**：tag 打在含完整收尾回写的提交上；`gh release create` 附 exe zip + sha256
   （exe 需**重新打包或用已构建产物**——dist 未入仓，Release 附件从当前 dist 压缩上传，
   sha256 留档 RELEASE-M6）+ 演示 GIF。
6. **演示 GIF 录制**（M5 顺延项）：本机 Chrome 崩溃（见 §4）→ 用 `INVOICE_LEDGER_GUI_SMOKE=1`
   无法录交互；可行路径 = 手动录屏（用户操作）或改用 CLI demo 终端录制 + GUI 截图；
   素材全为合成数据，无隐私。**若无法录制，如实登记顺延并在 Release notes 用截图替代**。
7. **仓库 topics**：`gh repo edit --add-topic`（小写连字符），`gh api` 回读确认生效。
8. **收尾固化**（skill 阶段 8）：台账收尾段 + 里程碑计划缓冲段 + 对标文档回写；缓议项清零
   （plan/06 §3 当前为空）；README 状态行"🚧 准备中"→"✅ v0.1.0 已发布"（挂 Release 链接）+
   CI 徽章指向发布仓库 Actions + 路线图最后一棒打勾；写 HANDOFF-FINAL 或就地收束
   （勾选本 HANDOFF DoD + 顶部"终版收官"标注）。
9. ~~（顺带）11号公告/56号令补核~~ ✅ **M5 已完成**（详 §1 末条）：三部法规原文逐字核对齐，
   status 全部转「已核对」；无需再依赖健康浏览器环境。

## 3. 既定口径清单（M0-M5 定稿收口速查区；改前先对照，动一笔须回写 plan）

**M5 新增（GUI/导出/打包/CI）**：

1. **GUI 单一事实源**：GUI 只消费 CLI/引擎 API（`cli._scan_and_parse` / `_register_batches` /
   `_run_check_pipeline`）与 `storage.Ledger` 查询；**检测参数默认值单一来源 = 各规则模块
   `DEFAULT_*` 常量**（GUI `_reset_params` 反向 import session 常量）；引擎参数经
   `_run_check_pipeline(engine_params=)` 注入 → 改规则默认值须同步 GUI 设置页量程；
2. **GUI 编辑保护**：台账编辑仅开放 `buyer_name/seller_name/remark`；号码/类型/日期/金额为
   对账链字段只读（`update_invoice_fields` 只接受这三个键，card_json 同步重写）；
3. **Excel 导出形态**：双 sheet 名固定 `发票台账`/`异常清单`；级别显示名 `确认异常/疑似/
   待人工确认`；条件格式三分支填充色 `FFC7CE/FFEB9C/BDD7EE`（用例断言 `rule.dxf.fill.bgColor.rgb`
   前缀 `00`）；发票 sheet 表头 16 列、异常 sheet 9 列（改列增删会打挂 tests/test_export.py）；
4. **`export` 退出码**：台账不存在=2、缺 openpyxl=2（OptionalDependencyError 经 main 统一捕获）、
   成功=0；默认输出 = 与 db 同目录同名 `.xlsx`；
5. **`app` 退出码**：缺 PySide6 或 PySide6.QtCharts=2（双门，报错定位到 desktop extras）；
   `--db` 默认 `ledger.db` 不存在即新建（AppContext→Ledger 建表）；
6. **打包形态**：onedir 双 exe（`invoice-ledger` console=False / `invoice-ledger-cli`
   console=True）；spec 内 `Analysis` 的 scripts **必须按名字过滤**（`a.scripts` 前几项是
   PyInstaller 运行时钩子，按下标取会拿到 bootstrap → 静默假成功 RC=0 无输出，M5 实录）；
   datas 白名单为空、hiddenimports=["openpyxl"]；spec 相对路径用 `SPECPATH` 解析、Analysis
   脚本用绝对路径；
7. **打包构建解释器通道**：冻结产物用 **Python 3.12 干净 venv** 构建（本机 3.8 通道构建工具级
   不稳定，见 §4）；`pack` 是独立 extra，**不进 `all`**（CI 测试矩阵保持精简）——
   tests/test_extras.py 断言 `all` = dev+parse+data+export+report+desktop；
8. **extras 覆盖运行期 import 的权威映射**（tests/test_extras.py `RUNTIME_IMPORT_EXTRA`）：
   openpyxl→export / PySide6+PySide6-Addons→desktop / pdfplumber→parse / reportlab→data /
   python-docx→report / pytest→dev / pyinstaller→pack——新增重量级 import 必须同步三处
   （pyproject extras + utils.import_optional 调用 + 本映射），漏一即测试红；
9. **测试计数口径**：dev 全 extras = **170 项**；干净 venv（仅 pytest）= **160 收集 / 143 绿 /
   18 skip**；差 10 = test_app.py 模块级 `importorskip` 收成 1 条目。改 extras 装机清单或
   新增模块级 importorskip 会改变此对账 → 须回写本速查区；
10. **CI 三作业**：`test`（win3.8/win3.12/ubuntu3.12，仅 dev）+ `desktop`（win-3.8，
    `[dev,parse,data,export,desktop]`，GUI/导出测试真跑）+ `benchmark`（win-3.8，
    `[dev,parse,data]`，门槛 exit 1=回归）；
11. **技术报告**：`docs/技术报告.md` 是唯一定稿源，docx 由 `docs/make_report_docx.py` 生成、
    禁止手改；docx 产物 `.gitignore` 排除不入仓；**先定稿 md 再生成**；
12. **文档计数全仓同步**：README/plan/00/05 与 HANDOFF 里的测试数（170/160/18/143）、
    命令数（六命令：demo/doctor/generate/parse/check/benchmark/**export**/**app**——实为八命令）、
    里程碑状态处统一维护，改测试必同步。

**M4 新增（基准/报告/CI）全部仍有效**（详见上一版 HANDOFF，此处不重复）：
字段级对账复用 field_match.py；检测指标 (号码,rule_id)+级别三元组；门槛 F1≥0.95/检出 100%/
误报 0/判定 100% + 零容忍项；benchmark 退出码 0/1/2；零 API 可重复（不传 default_anchor）；
报告无墙钟同输入逐字节一致；基准锚点数字 = 58 号码 / 57 解析卡 / 真值异常 18 对 / 告警 18 /
13 findings / 分字段 16。

**M0-M3 既有口径全部有效（速查版）**：

- InvoiceCard schema（plan/04 §1）；解析映射权威 = TEMPLATE_REFERENCE（synthetic-v1）；
  PDF label-slot 三条实测口径（双栏截断 / 大写合并词 / 明细 x 列聚类）；
- 真值双键：cards.json 按文件路径、expectations.json 按号码；对账 = expect∪also_expect
  全集；权威出处 = generator/synthetic.py 模块注释；
- 数值清洗/失败语义：解析不到留空串 + field_flags，不造默认值；confidence 语义；
- 八规则注册顺序 = 执行顺序（plan/04 §3.1）；入库与判重分离（引擎输入=全部解析卡含被拒副本）；
  R-DUP-02 排除纯复制件；R-DUP-03 金额=total_with_tax、tol=0.00、窗 1d；R-SEQ-01 跨前缀不
  产出 finding；R-TIME-02 仅追溯方向；
- 引擎 `run(cards, ctx_extra=None)`：ctx 三键 batch_anchors/default_anchor/existing_numbers；
  finding_id = rule_id + ":" + "|".join(全部号码)（无号码 "-"）；
- check 命令：--anchor-manifest 基准通路 / 缺省 anchor=导入当天；create_batch 幂等；findings
  按 finding_id 幂等拒收；重复检测需新 --db；
- 测试纪律：stdlib+pytest 模块级，重依赖函数内 import_optional+显式 skip；干净 venv 与 dev
  收集数一致（skip 计数上报）；核心零依赖；requires-python≥3.8 语法（无 match/PEP604）；
  退出码契约（未交付/缺依赖=2）；
- 生成器：唯一随机源 random.Random(seed)，同 seed 位级一致（EOL=LF 门）；OFD zip 固定时间戳；
  PDF invariant=1；合成数据 FAKE 税号自证虚构。

## 4. 本机环境坑（M5 实测增量 + 存量）

- **M5 新增（最重要）：PyInstaller 在 3.8.8 通道构建工具级不稳定**——同一 spec 出现 5 种
  "不可能错误"：`re.error: missing ), unterminated subpattern`（packaging 库正则编译失败）、
  `TypeError: 'Instruction' object is not iterable`（modulegraph 反汇编）、
  `required field "value" missing from Constant`（base_library.zip 阶段 AST 编译）、
  `SubprocessDiedError exit 3221225477`（隔离子进程 0xC0000005）、`Segmentation fault 139`；
  全在工具自身的扫描/编译层、与项目代码零关联，清全局 pyc + 重建 venv 均不解。
  **处置 = 换构建解释器通道**：用户级静默装 Python **3.12.10**（npmmirror 下载
  `https://registry.npmmirror.com/-/binary/python/3.12.10/python-3.12.10-amd64.exe`，
  `/quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0`）→ 干净 venv → 首跑一次成功
  （36s）。**另一坑**：`py -m venv` 的 ensurepip 在 `PYTHONDONTWRITEBYTECODE` 导出**之前**
  执行会写下坏 pyc（venv 内 pip 随即段错误）→ 建完 venv **先清 `__pycache__`** 再装包。
- **M5 新增**：`py -m PyInstaller`（**模块名大写 P**）——`py -m pyinstaller` 报
  "No module named pyinstaller"（大小写敏感），别误判为未安装。
- **M5 新增**：本机 sys.path 被**多个姊妹项目的 `src` .pth 条目污染**（site-packages 里挂着
  bidding/food/medical/resume/structural 五个项目的 src）——构建分析面不干净，构建务必用
  干净 venv（`python -c "import sys; print(sys.path)"` 核对）。
- **M5 新增**：Git Bash 下复合命令里的 `cd <dir> && ...` 若目录不存在会静默回落到原 cwd
  （实测：`cd dist/test-cli` 失败后后续命令在仓库根跑）——构建验证用绝对路径或先 `ls` 确认。
- **M4 重申**：pytest `-q` 输出经 bash 管道时 summary 行偶发被吞 → 重定向到文件后单独 grep；
  整轮 pytest 收集也可能偶发 `AttributeError: 'Compare' object has no attribute
  'push_format_context'`（断言重写抖动，同命令重跑即绿）。
- **存量（仍有效）**：**本机 Chrome 启动崩溃**（agent-browser 自动起 Chrome exit 3 无
  DevToolsActivePort）——真实浏览器自动化不可用：GUI 录屏/演示 GIF 需先解决（排查已开 Chrome
  实例占用/公司策略/换 Edge channel）；**fgk.chinatax.gov.cn 可达形态已摸清（M5 突破，原
  "静态抓取全不可达"结论作废）**：① **PDF 附件直链**最可靠（无需 JS，不受 WAF 挑战页拦截，
  `curl -A "<浏览器 UA>"` 即 200）；② **内容页加 `content.html` 后缀 + 浏览器 UA +
  `Accept-Language: zh-CN`** 可 200（无后缀的 `/zcfgk/c100012/c<id>/` 形态仍被 WAF 挑战页拦
  → 403，别再试该形态）；③ 检索摘要仅用于定位候选直链，**可达性与条文一律 curl 落盘 + 本地
  提取**（PDF 用 pdfplumber），不采信摘要转述；pip 清华镜像 + `NO_PROXY="*" no_proxy="*"`；
  `PYTHONDONTWRITEBYTECODE=1` 全程携带（含 pip install；**venv 创建后先清 `__pycache__`**）；
  统一 `py -m invoice_ledger_checker`；Git Bash 下 `py -X utf8`，测试内 subprocess 显式
  PYTHONIOENCODING=utf-8；pdfplumber 在 py3.8 import 时打 CryptographyDeprecationWarning
  （无害）；Git Bash `/tmp` 对 Windows Python 不可见（临时目录建仓内）；*.db 已在 .gitignore
  （测试一律 tmp_path）；**PySide6 离屏测试打印 `QFontDatabase: Cannot find font directory`
  警告（无害，非失败）**。

## 5. M5 DoD checklist（收尾逐项打勾，没做到的写偏差说明）

- [x] PySide6 cp38 wheel 复核结论回写 plan/03 §3 表格（消除"待核对"标注）
- [x] `export` 命令：Excel 发票+异常清单双 sheet，条件格式标红正确（用例断言样式）
- [x] `app` 命令：六窗口组件可演示（导入/台账/异常清单/看板/导出/设置+状态栏）
- [x] 看板 QtCharts 三图（月度趋势/供应商 Top-N/类型分布）
- [x] extras 覆盖运行期真实 import 断言测试（export/desktop 缺依赖显式 skip 计数）
- [x] PyInstaller onedir + 主 .spec 入仓；exe 干净环境实测
      （**偏差说明**：构建解释器通道由 plan 声明的 win-3.8 改为 Python 3.12 干净 venv——
      3.8 通道构建工具级不稳定（§4 首条），与项目代码无关；产物与构建解释器绑定、与源码
      运行时底线 3.8 无关，已回写 README 限制节 + plan/00 决策表 + plan/06）
- [x] 技术报告 docs/技术报告.md（解析方案/检测算法/打包与离线设计）+ docx 脚本
- [x] 基准不回退：`benchmark` 门槛全过（宏平均 F1=1.0000 / 检出 100% / 误报 0 / 判定 100%）
- [x] pytest 全绿且收集数与 M4 的 144 项对账清楚（**170** = 144 + 26，逐项列明；干净 venv
      160/143/18 与 dev 差 10 已归因到 test_app 模块级 skip）
- [ ] 演示 GIF 录制落 docs/（**偏差说明**：顺延 M6 初——本机 Chrome 崩溃无法自动录制；
      路径与替代方案见 §2.6，届时如实登记）
- [x] plan/00、05、06 状态回写；HANDOFF-M6 落盘；本文件头部标注已过时
- [x] （顺带）11号公告/56号令补核：**M5 完成**——原文全文经 fgk `content.html` 后缀（11 号公告）
      与 PDF 附件直链（56 号令）取得，逐字核对，status 转「已核对」；两处订正与新增条款见 §1 末条

## 6. 关键命令速查

```
# 测试（全程携带 PYTHONDONTWRITEBYTECODE=1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest                    # dev 全 extras：170 项
clean-venv/Scripts/python.exe -m pytest -rs                       # 干净 venv：160 收集/143 绿/18 skip

# CLI（未装则 PYTHONPATH=src py -X utf8 -m invoice_ledger_checker ...）
py -X utf8 -m invoice_ledger_checker demo                         # 端到端演示
py -X utf8 -m invoice_ledger_checker doctor                       # 可选依赖体检
py -X utf8 -m invoice_ledger_checker generate --out data --seed 42 --n 60   # 改生成器后必须重跑并提交冻结数据
py -X utf8 -m invoice_ledger_checker parse data/invoices --report
py -X utf8 -m invoice_ledger_checker check data/invoices --db ledger.db \
    --anchor-manifest data/ground_truth/manifest.json
# 注意：重复对同一 --db 跑 check 会把全部号码判 R-DUP-01；基准请用新库
py -X utf8 -m invoice_ledger_checker export ledger.db             # Excel 双 sheet 导出
py -X utf8 -m invoice_ledger_checker app --db ledger.db           # 桌面应用（需 .[desktop]）

# 基准（门槛未达 exit 1 = 回归信号）
py -X utf8 -m invoice_ledger_checker benchmark                    # 出指标表 + 刷新 benchmarks/report.md
py -X utf8 -m invoice_ledger_checker benchmark --no-report        # 只看指标（CI 形态）

# 打包（M5；务必用 3.12 干净 venv，见 §4）
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" -m venv build-venv312
find build-venv312 -name __pycache__ -type d -exec rm -rf {} +    # 清 ensurepip 坏 pyc（必做）
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" build-venv312/Scripts/python.exe -m pip install -U pip
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" build-venv312/Scripts/python.exe -m pip install \
    ".[parse,data,export,desktop,report]" "pyinstaller>=6,<7" -i https://pypi.tuna.tsinghua.edu.cn/simple
build-venv312/Scripts/python.exe -m PyInstaller packaging/invoice_ledger_checker.spec --noconfirm
# 干净环境验证：复制 dist 到中立目录（%LOCALAPPDATA%\Temp）+ env -i 剥离 PATH 跑 CLI 五连
# GUI 冒烟：INVOICE_LEDGER_GUI_SMOKE=1 ./invoice-ledger.exe（1.5s 自动退出）

# 技术报告（先定稿 md 再生成 docx；产物不入仓）
py -X utf8 docs/make_report_docx.py

# 冻结对账（改解析器/生成器/规则后必跑）
# tests/test_parsing.py 字段冻结对账 + tests/test_baseline_detection.py 检测对拍
# + tests/test_generator.py 位级回归 + tests/test_benchmark.py 门槛与报告确定性

# 安装（pip 代理规避 + 不写 pyc）
NO_PROXY="*" no_proxy="*" PYTHONDONTWRITEBYTECODE=1 py -m pip install -e ".[all]" -i https://pypi.tuna.tsinghua.edu.cn/simple

# git（提交前三核对：pwd / git log --oneline -1 / git remote -v）
git add -A && git commit -m "..."
```
