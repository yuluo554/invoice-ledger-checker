# HANDOFF-FINAL（M6 终版收官快照）

> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-FINAL.md 继续完成任务`（相对路径；启动命令由
> 用户侧拼绝对路径——**入库文档一律相对路径**，脱敏纪律）。
> 落盘 2026-10-06，**M0-M6 全部完成、项目已公开发布**。方法论：ai-tool-project-sprint。
> 本文件是系列第六题的终版收官：既定口径全量收口在 §3，后续可捡起项在 §6。
> 历史快照按序见 HANDOFF-M1…M6（均已标注过时留档）；发布留档见 [RELEASE-M6.md](RELEASE-M6.md)。

## 1. M6 完成态（脱敏发布）

- **脱敏第 0 步（姊妹/系列表述）**：`gh api users/<owner>/repos` 实测 —— 账号 14 仓库、13 public
  （唯一 private 与本系列无关），**前作五题全部 public → 保留系列表述、不做掩码**。
- **脱敏第 1 步（密钥/凭据）**：`git ls-files` 扫描 0 命中；`.gitignore` 覆盖 .env/\*.key/\*_private/\*.db 等。
- **脱敏第 2 步（内容级扫描，工具化）**：`tools/sensitive_scan.py` 入仓（stdlib-only、3.8 兼容、退出码 0/1/2）：
  - 六模式：`selftest` / `tracked` / `history` / `binaries` / `messages` / `metadata`（+ `dist` 产物树）
  - **selftest 阳性+阴性双对照**：六类目全有阳性样本，15 个易误报样本必须不命中
  - **输出掩码化**：`文件:行号 [类别] x次数`，不回显字面值 → 报告可随仓留档
  - **正则片段拼接构造**：工具源码自身在朴素 grep 下也干净
  - 自测抓出并修掉 4 处检测器缺陷（身份证缺结构校验 / 邮箱单字母 TLD / **PDF 的 ASCII85 流是纯 ASCII**
    被当文本 / 密钥赋值口径过宽致**自命中**）——详见 RELEASE-M6 §3.1
- **脱敏第 3 步（二进制样例单独扫）**：PDF Info 元数据域（Author=anonymous、Producer 厂商串、
  **CreationDate 固定 2000-01-01**）+ OFD zip 条目（固定 1980 时间戳、空 comment）；本仓无 tracked docx。
- **产物本体扫描**：378 文件 / 184.3 MB，4 强标记 + 禁区成分 **0 命中**（标记以 `--marker-b64` 现场传入，
  字面值不入仓）；产物与发布源码同基线（`git diff <M5>..HEAD -- src/` 为空）；
  上游噪声已甄别登记（CPython 官方构建机残留的 macOS 用户目录路径 = 上游产物、GPU 厂商串 = Qt 串表）。
- **提交元数据邮箱全历史改写**：真实个人邮箱 → GitHub noreply（`<uid>+<user>@users.noreply.github.com`），
  同一次 filter-branch 内一并消除个人目录字面量；`refs/original` 已删 + reflog 过期 + `gc --prune=now`；
  **全对象库（含不可达）深度扫描 0 命中**；`git fsck` 干净；**`data/` 树哈希不变**（md5 `59ce1250…`）。
- **干净环境验证（发布门核心，新 clone + 新 venv 逐条跑 README）**：**抓出 2 个发布阻断缺陷并修复**——
  ① `data` extras 未锁 reportlab 上界 → 3.8 上 `generate` 崩（`usedforsecurity` 是 py3.9 参数），
  且会打挂**从未跑过**的 CI win-3.8 作业；② 冻结 exe 缺 pdfplumber（惰性导入对 PyInstaller 不可见）→
  发行包 `check` 退出码 2、台账不生成、GUI 导入通路同坏。两者均已加回归锁（RELEASE-M6 §7.3）。
- **冻结产物复测**（中立目录 + `env -i` 剥离 PATH，**逐条取真实退出码**）：doctor/demo/generate/
  check/export/benchmark **六条全 exit 0**；check 解析 60 文件成功 **57 张卡（pdf 22 + xml 35，0 失败）**；
  GUI 冒烟探针 2599 ms。
- **基准不回退**：宏平均 F1=**1.0000**、检出率 **100%**、误报 **0**、判定准确率 **100%**；
  `benchmarks/report.md` 同输入重跑逐字节一致。
- **计数对账**：dev **179 项全绿**；干净 venv（仅 dev）**170 = 151 绿 + 19 skip**；
  干净 venv（`[all]`）**179 = 178 + 1**（与 dev 同构，CI `desktop` 作业等价）。
  **差 9 = test_app.py 模块级 importorskip 收成 1 条目**；19 skip 逐项指认（见 §3 第 12 条）。
- **建仓、push 与 CI 首跑**（GitHub `yuluo554/invoice-ledger-checker`，public + MIT）：不带 `--push` 建仓
  → SSH 通路一次 push → **CI 五运行全绿**（`test` 三矩阵 + `desktop` + `benchmark`，其中 desktop 与
  benchmark 作业在发布前**从未执行过**）；topics 10 个回读生效；README 渲染核对通过。
  首跑又暴露并修复**第三个"从未验证过"的缺陷**：`ci.yml` 的 step 名含未加引号的「冒号+空格」→
  整份 workflow 非法 YAML → GitHub 不建任何 job（run 0 秒失败、jobs=0），已修复 + 加 YAML 守门测试
  （见 §3 第 15 条与 §4）。

## 2. 交付物索引

| 交付物 | 位置 |
|---|---|
| 桌面应用（PySide6 六页签） | `src/invoice_ledger_checker/app/` |
| 核心代码框架（解析/存储/规则/基准/导出/CLI） | `src/invoice_ledger_checker/` |
| 合成数据集 + 生成器（含真值） | `data/` + `src/invoice_ledger_checker/generator/` |
| 内置评测基准 | `benchmarks/benchmark.py` + `benchmarks/report.md` |
| 技术报告（+ docx 生成器） | `docs/技术报告.md` + `docs/make_report_docx.py` |
| 打包 spec + 双入口 | `packaging/invoice_ledger_checker.spec` + `entry_gui.py` / `entry_cli.py` |
| 脱敏扫描器（发布门工具） | `tools/sensitive_scan.py` |
| Release 附件（Windows 免安装 zip） | GitHub Release（sha256 见 RELEASE-M6 §5） |
| 发布留档 | `plan/RELEASE-M6.md` |

## 3. 既定口径清单（全量收口速查区；改前先对照，动一笔须回写 plan）

**M6 新增（脱敏发布）**：

1. **脱敏门六件套缺一不可**：第 0 步姊妹表述核实（前作全 public → 不掩码）/ 第 1 步密钥扫描 /
   第 2 步内容级扫描（工具化）/ 第 3 步二进制样例单独扫 / 产物本体扫描 / 提交元数据邮箱；逐项留档 RELEASE-M6。
2. **扫描器纪律**：`tools/sensitive_scan.py` 六模式 + selftest 双对照；输出掩码化；正则与夹具**片段拼接**；
   **扫描器源码自己也要过自己的扫描**；模式**避免 `/` 起始形式**（MSYS 静默转写 → 假 0 命中）；
   跑前先做**阳性对照**（已知存在串必须命中，否则扫描命令本身可能是坏的）。
3. **产物扫描形态**：只跑强标记（个人标记/姊妹词，`--marker-b64` 现场传入）+ 禁区成分；
   **不跑**邮箱/手机号宽正则（上游厂商公共串与二进制噪声刷屏）；产物与源码同基线用 `git diff src/` 为空为据。
4. **元数据邮箱**：内容级扫描覆盖不到，必须 `git log --format="%ae %ce" --all | sort -u` 单独查；
   改写用 `filter-branch --env-filter`，**本地 `git config user.email` 同步**；改完**必须**删 `refs/original`
   + reflog 过期 + `gc --prune=now`（不清则 `--all` 类扫描继续见到旧对象，白验）；
   终验要**全对象库**（`git cat-file --batch-all-objects`）而非只扫可达对象。
5. **filter-branch 两条纪律（本项目实测）**：① 输出**别接管道**（SIGPIPE 可写坏 ref）——
   重定向到文件或直跑；② **Git-for-Windows 的 sed 在 BRE 里不匹配字面反斜杠**（静默不生效）→
   优先用 `--index-filter` + `git update-index --cacheinfo` 做**预计算 blob 替换**（可先 diff 验证）。
6. **extras 版本约束必带环境标记**：`reportlab` py<3.9 锁 `<4`（4.x 在 3.8 运行期崩）、py≥3.9 放开
   （3.6.13 在 3.12 装不起来）；`PySide6` py<3.9 锁 `>=6.5,<6.7`。**单一上界不可行**是实测结论。
7. **位级复现门分层**：冻结数据 PDF 字节依赖 reportlab 主版本 → 仅 reportlab **3.x** 环境比对 `.pdf` 字节；
   **XML/OFD 与 `ground_truth` 任何环境全量比对**（不做整块 skip，防静默少跑）。
8. **打包 hiddenimports 纪律**：经 `utils.import_optional` **惰性导入**的包对 PyInstaller 静态分析不可见，
   必须显式进 `hiddenimports`（现有 `openpyxl` + `pdfplumber`），漏一个即产物**静默缺能力**；
   新增惰性依赖必须同步 spec + `tests/test_packaging.py` 断言。
9. **exe 验证纪律（M5 假绿教训）**：关键命令**单跑取真实退出码**，绝不看 bash 管道的 `$?`
   （`| tail` 的 `$?` 是 tail 的）。M5 记录的"CLI 五连全过"即因此为假绿。
10. **测试计数口径**：dev 全 extras = **179 项**；干净 venv（仅 `[dev]`）= **170 = 151 绿 + 19 skip**；
    干净 venv（`[all]`）= **179 = 178 + 1**（dist 缺席）。差 9 = `test_app.py` 模块级 `importorskip`。
    改 extras 装机清单或新增模块级 importorskip 会改变此对账 → 须回写本速查区与 RELEASE-M6。
11. **CI 三作业（五运行）**：`test`（win3.8/win3.12/ubuntu3.12，仅 dev）+ `desktop`（win-3.8，
    `[dev,parse,data,export,desktop]`，GUI/导出真跑）+ `benchmark`（win-3.8，`[dev,parse,data]`，门槛）。
12. **19 skip 明细（干净 venv 仅 dev）**：test_app 1（模块级）+ pdfplumber 11（parsing 3 /
    baseline_detection 2 / benchmark 4 / cli 2）+ test_cli openpyxl 1 + test_export openpyxl 2 +
    test_extras PySide6 1 + test_generator reportlab 2 + test_packaging dist 1。
13. **产物形态**：onedir 双 exe（`invoice-ledger` GUI console=False / `invoice-ledger-cli` console=True）；
    `datas` 白名单为空（版权红线数据不入包）；构建通道 = **Python 3.12 干净 venv** + PyInstaller 6.22.3
    （3.8 通道构建工具级不稳定）；产物 186 MB、Release zip 83.3 MB（zip 时间戳使重打包哈希必变）。
14. **文档计数/表述全仓同步**：README/plan/00/05/06 与 HANDOFF 的测试数（179/170/19）、命令数
    （八命令：demo/doctor/generate/parse/check/export/app/benchmark）、里程碑状态处统一维护，改测试必同步。
15. **CI workflow YAML 守门**（`tests/test_ci_workflow.py`，pyyaml 已入 dev extras）：workflow 必须
    可被 YAML 解析，且每个 job 声明 `runs-on`/`steps`（防 0 秒空跑）；`ci.yml` 作业面固化。**纯量里
    含「冒号+空格」必须加引号**——否则整份 workflow 非法，GitHub 不建任何 job（run 0 秒失败、jobs=0）。

**M0-M5 既有口径全部仍有效（速查版）**：

- **M5**：GUI 单一事实源（只消费 CLI/引擎 API；检测参数默认值单一来源 = 规则模块 `DEFAULT_*`）；
  GUI 编辑仅开放 `buyer_name/seller_name/remark`；Excel 双 sheet 名固定 `发票台账`/`异常清单`、
  条件格式 `FFC7CE/FFEB9C/BDD7EE`（发票 sheet 16 列、异常 sheet 9 列）；
  `export` 退出码（台账不存在=2 / 缺 openpyxl=2）；`app` 退出码（缺 PySide6 或 QtCharts=2）；
  spec 的 `Analysis.scripts` **必须按名字过滤**（按下标取会拿到运行时钩子 → 静默假成功 RC=0 无输出）。
- **M4**：字段级对账复用 `benchmarks/field_match.py`；检测指标 (号码, rule_id) + 级别三元组；
  门槛 F1≥0.95 / 检出 100% / 误报 0 / 判定 100% + 零容忍项（解析失败/未知号码告警/锚点缺失）；
  `benchmark` 退出码 0/1/2；零 API 可重复（不传 `default_anchor`）；报告无墙钟同输入逐字节一致；
  基准锚点数字 = 58 号码 / 57 解析卡 / 真值异常 18 对 / 告警 18 / 13 findings / 分字段 16。
- **M0-M3**：InvoiceCard schema（plan/04 §1）；解析映射权威 = TEMPLATE_REFERENCE（synthetic-v1）；
  PDF label-slot 三条口径（双栏截断 / 大写合并词 / 明细 x 列聚类）；真值双键（cards 按路径、
  expectations 按号码；对账 = expect∪also_expect）；八规则注册顺序 = 执行顺序（plan/04 §3.1）；
  入库与判重分离（引擎输入含被拒副本）；R-DUP-02 排除纯复制件；R-DUP-03 金额=total_with_tax、
  tol=0.00、窗 1d；R-SEQ-01 跨前缀不产出 finding；R-TIME-02 仅追溯方向；
  `finding_id` = rule_id + ":" + "|".join(全部号码)；`ctx` 三键 batch_anchors/default_anchor/existing_numbers；
  check 命令 `--anchor-manifest` 基准通路 / 缺省 anchor=导入当天；重跑 check 需新 `--db`；
  测试纪律（stdlib+pytest 模块级、重依赖函数内 `import_optional` + 显式 skip、退出码契约、requires-python≥3.8
  语法）；生成器唯一随机源 `random.Random(seed)`、同 seed 位级一致（EOL=LF 门）、OFD zip 固定时间戳、
  PDF invariant=1、合成数据 FAKE 税号自证虚构。

## 4. 本机环境坑（M6 增量 + 存量权威速查）

- **M6 增量**：① **关键命令别接管道取退出码**（假绿之源，M5 exe 验证实录）；② **Git-for-Windows sed
   的 BRE 不匹配字面反斜杠**（静默不生效 → 改 `--index-filter` + `git update-index --cacheinfo` blob 替换）；
  ③ `filter-branch` 输出接管道有 SIGPIPE 写坏 ref 的风险；④ **PyInstaller 的 `hiddenimports`
  必须覆盖全部惰性导入**（本次 pdfplumber 漏声明 → 发行包残废）；⑤ 本机为**已知不稳定环境**：
  全量 pytest 偶发单条 PDF 解析失败（**每次文件不同**；660 次连续解析 0 失败可证非数据缺陷）与偶发段错误
  （exit 139）、偶发 `XXX lineno: N, opcode: 0` 帧损坏（traceback 乱码）——**同命令重跑即绿**，
  处置 = 如实登记 + 重跑取绿，零容忍门槛不放宽；⑥ **workflow 非法 YAML 极度隐蔽**：GitHub 端
  `state` 仍显示 `active`、文件字节也洁净，看状态/看字节都查不出，**只有真解析或真跑才暴露**——
  排查手段 = "最小 workflow 隔离实验"（同一次 push 下最小文件成功即证明问题在目标文件自身）；
  CI 首跑**必须**预留"诊断 + 修复 + 再推一轮"预算。
- **M5**：PyInstaller 在 3.8.8 通道构建工具级不稳定（5 种"不可能错误" + 段错误）→ **换 3.12 干净 venv
  构建通道**；`py -m venv` 的 ensurepip 会写坏 pyc（建完 venv **先清 `__pycache__`**）；
  `py -m PyInstaller`（**模块名大写 P**）；本机 sys.path 被多个姊妹项目 `src` 的 .pth 污染（构建务必用干净 venv）；
  Git Bash 下 `cd <不存在目录> && ...` 会静默回落原 cwd（验证用绝对路径）。
- **M4 重申**：pytest `-q` 的 summary 行经 bash 管道**偶发被吞**（本次实测即便重定向到文件也会丢计数行）
  → 以**退出码 + `-rs` 的 skip 明细**为准，计数用 `--co -q` 或带 `-rs` 的完整输出；
  整轮收集偶发断言重写抖动（同命令重跑即绿）。
- **存量（仍有效）**：**本机 Chrome 启动崩溃**（浏览器自动化不可用 → GUI 录屏走人工/截图替代）；
  fgk 法规域可达形态（PDF 附件直链 + `content.html` 后缀 + 浏览器 UA）；pip 清华镜像 +
  `NO_PROXY="*"`；`PYTHONDONTWRITEBYTECODE=1` 全程携带；`py -X utf8`；Git Bash `/tmp` 对 Windows Python
  不可见（临时目录建仓内或用 Windows 可见路径）；pdfplumber 在 py3.8 import 打 CryptographyDeprecationWarning
  （无害）；PySide6 离屏测试打 `QFontDatabase` 警告（无害）。

## 5. 关键命令速查

```bash
# 测试（全程携带 PYTHONDONTWRITEBYTECODE=1）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -rs          # dev 全 extras：179 项
py -X utf8 -m pytest --co -q                                # 只数收集项（防 summary 行被吞）
# 干净 venv（仅 dev）：170 = 151 绿 + 19 skip；[all]：179 = 178 + 1

# CLI（未装则 PYTHONPATH=src py -X utf8 -m invoice_ledger_checker ...）
py -X utf8 -m invoice_ledger_checker doctor|demo|generate|parse|check|export|app|benchmark

# 脱敏门（发布前/发布后复核都跑）
py -X utf8 tools/sensitive_scan.py selftest                 # 阳性+阴性对照（必先跑）
py -X utf8 tools/sensitive_scan.py all                      # 五模式，退出码 0=干净
py -X utf8 tools/sensitive_scan.py dist --dir dist --marker-b64 <b64> [...]   # 产物树
git log --format="%ae %ce" --all | sort -u                  # 元数据邮箱单独查
git cat-file --batch-all-objects --batch | grep -c <字面值>  # 全对象库深度终验

# 打包（务必用 Python 3.12 干净 venv，见 §4）
"$LOCALAPPDATA/Programs/Python/Python312/python.exe" -m venv build-venv312
find build-venv312 -name __pycache__ -type d -exec rm -rf {} +      # 清 ensurepip 坏 pyc（必做）
build-venv312/Scripts/python.exe -m pip install -U pip
build-venv312/Scripts/python.exe -m pip install ".[parse,data,export,desktop,report]" "pyinstaller>=6,<7"
build-venv312/Scripts/python.exe -m PyInstaller packaging/invoice_ledger_checker.spec --noconfirm
# 冻结产物验证：复制 dist 到中立目录 + env -i 剥离 PATH，逐条单跑取真实退出码

# 基准（门槛未达 exit 1 = 回归信号）
py -X utf8 -m invoice_ledger_checker benchmark [--no-report]

# 技术报告（先定稿 md 再生成 docx；产物不入仓）
py -X utf8 docs/make_report_docx.py
```

## 6. 后续可捡起项（非阻塞，按价值排序）

1. **OFD 解析（P2）**：补 OFD 解析器即可让 3 份顺延样本入对账，属唯一明确的加分空缺。
2. **演示 GIF**：本机 Chrome 崩溃下未录；若要补，用另一台健康机器录 GUI 交互，或直接补更多截图。
3. **仓库 topics 扩充**：现有一批主题标签，可按传播需要增补（如 `pyside6`、`e-invoice`）。
4. **LLM 兜底（llm）**：extras 预留未实现——默认路径零 LLM 是全离线纪律的组成部分，若做须保持默认关闭。
5. **PDF 解析对扫描件的边界**：README 已声明不做 OCR；若要扩展须连真值一起扩展（数据先行的前提）。
