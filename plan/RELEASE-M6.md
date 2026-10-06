# RELEASE-M6：脱敏发布留档（v0.1.0）

> **本文件随仓库公开**：一切敏感字面值（真实个人邮箱、个人目录、账号相关串）一律以类别/指代
> 呈现，不复述原文——否则"全历史 0 命中"的验证永远过不了（系列实录：为此返工过一轮重写）。
> 落盘 2026-10-06，方法论 ai-tool-project-sprint 阶段 7（脱敏四步 + 产物本体扫描 + 干净环境验证）。

留档结构 = 脱敏第 0/1/2/3 步 + 产物本体扫描（第 5 步）+ 发布前置元数据邮箱 + 干净环境验证 +
发布后复核。每条记录**命令与结论**，不写"已验证"式空断言。

---

## 1. 脱敏第 0 步：姊妹/系列表述处置（品牌隔离的发布前复核）

**规则**：plan 文档互相提及姊妹项目的前提 = 对方**已公开**。先核实公开性；均已公开 → 保留系列
表述；有未公开 → 从 plan 移除后再过历史扫描。

**核实命令**：

```bash
gh api "users/<owner>/repos?per_page=100" --jq '.[] | "\(.name)\t\(.private)"'   # 公开仓库
gh api "user/repos?per_page=100"        --jq '.[] | "\(.name)\t\(.visibility)"' # 含私有
```

**结论（2026-10-06 实测）**：账号下共 14 个仓库，**13 个 public**（唯一 private 是与本系列无关的
私人笔记库）；本系列**前作五题全部 public**——建造 / 电力 / 医疗 / 招投标 / 食品五题均在公开列表内。

→ **前作已全部公开，无需掩码**，plan/00 头行的前作名称与领域保留（系列品牌连续性）。
→ 掩码分支未触发，故**未**引入"同系列第 N 题"匿名化表述，扫描器也**未**内置前作词表。
→ 结论已登记 plan/06 §3 缓议清零表。

---

## 2. 脱敏第 1 步：密钥/凭据扫描

```bash
git ls-files | grep -iE "\.env$|\.key$|secret|token"    # 期望为空
```

**结论**：0 命中（`git ls-files` 145 个跟踪文件无 `.env`/`.key`/凭据文件）。
`.gitignore` 覆盖确认：`.env`、`*.key`、`*_private/`、`*.db`、`*.sqlite`、`output/`、
`reports/`、`*.log`、`docs/*.docx`、两条构建 venv、`dist/`。

---

## 3. 脱敏第 2 步：内容级扫描（工具化，入仓可复跑）

工具：`tools/sensitive_scan.py`（stdlib-only、3.8 兼容、退出码 0/1/2）。

| 模式 | 扫描面 |
|---|---|
| `selftest` | 阳性+阴性双对照：六类目（密钥/邮箱/手机号/身份证/个人目录/内网 IP）全有阳性样本；**15 个阴性对照**必须不命中 |
| `tracked` | 全部跟踪文件（工作树） |
| `history` | 全历史提交引入过的每一行（`git log -p` 的 `+` 行） |
| `binaries` | 二进制样例本体（PDF Info 元数据域 / ZIP·OFD 逐条目解压）——见 §4 |
| `messages` | 全部提交信息 |
| `metadata` | 提交作者/提交者姓名与邮箱（内容级扫描覆盖不到的元数据面） |
| `dist` | 构建产物树（强标记 + 禁区成分）——见 §5 |

**工具自身纪律**：类目正则与 selftest 夹具一律**片段拼接构造**（`"gh"+"o_"`、`"pass"+"word"`），
使扫描器源码自身在朴素 grep 下同样干净；输出**掩码化**（`文件:行号 [类别] x次数`），
不回显命中字面值，扫描报告因此可随仓留档。

### 3.1 自测首轮抓出的检测器缺陷（阳性对照不是形式）

| # | 缺陷 | 处置 |
|---|---|---|
| 1 | 身份证 `\d{17}[\dXx]` 无结构校验 → 20 位合成发票号码的 18 位前缀误报 | 加省级行政区码 + 出生日期双重校验 |
| 2 | 邮箱顶级域允许单字母 → 二进制噪声 `x@E.M` 误报 | 顶级域要求 ≥2 位字母 |
| 3 | 整文件 NUL 判据判二进制 → PDF 的 **ASCII85 流是纯可打印 ASCII**，压缩流随机字符撞邮箱正则 | 二进制容器按后缀跳过（数据资产内容由被扫描的生成器源码程序化产出） |
| 4 | 密钥关键字赋值用宽口径 `\S{6,}` → **扫描器自命中**（`_RE_SECRET = re.compile(`） | 赋值分支只认字符串字面量或裸高熵令牌 |

缺陷 4 是对照"工具与产物同一套口径"的直接印证：规则过宽时，第一时间被自己的源码打脸。

### 3.2 终验（改写完成后，2026-10-06）

| 扫描 | 结果 |
|---|---|
| `sensitive_scan.py all`（tracked/history/binaries/messages/metadata 五模式） | **全部 0 命中** |
| 逐提交树 `git rev-list --all` + `git grep`（朴素模式，边界感知） | 唯一命中 = 1 份 PDF 的 ASCII85 压缩流（**二进制容器**，见下） |
| 全历史补丁 `git log --all -p \| grep` | 同上（同一份 PDF 的补丁行） |
| 提交信息 | 0 |
| 提交元数据 `git log --format='%an <%ae>' --all \| sort -u` | 仅 GitHub noreply |
| **全对象库**（含不可达对象）`git cat-file --batch-all-objects --batch` 搜个人邮箱/个人目录字面量 | **0 / 0**（扫描 1.25 MB 全对象） |
| `git fsck` | 无错误（改写后完整性） |
| **阳性对照**（确认扫描命令本身有效） | 已知存在串命中（`git grep -c` >0）+ `sensitive_scan.py selftest` PASS |

**关于唯一残留命中（如实登记）**：`data/invoices/batch_01/…269.pdf` 的字节流中含随机
ASCII85 字符序列，恰好匹配朴素邮箱正则。该文件是 M1 冻结的合成数据资产，其内容由
`generator/synthetic.py` 程序化产出（源码在 tracked 扫描面内，0 命中）；对二进制容器做逐字节
文本匹配属**已知噪声源**，故本工具按容器后缀跳过（§3.1 缺陷 3）。此登记为分类说明，非豁免未查项。

**关于扫描模式本身可能是字面值**：本文件与 plan/06 相关表述一律用类别/指代，不复述敏感串原文；
扫描模式亦统一参数化。

---

## 4. 脱敏第 3 步：二进制样例单独扫描

`git grep` 与文本扫描**跳过二进制**，这是独立盲区，故单列一步（工具 `binaries` 模式常驻）。

**PDF（22 份）Info 元数据域实测值**：

| 域 | 实测值 | 判定 |
|---|---|---|
| `/Author` | `anonymous` | 非个人 |
| `/Creator`、`/Producer` | `ReportLab PDF Library - www.reportlab.com` | 厂商公共串 |
| `/Subject` | `unspecified` | 非个人 |
| `/Title` | UTF-16BE 合成发票标题 | 合成 |
| `/CreationDate`、`/ModDate` | `D:20000101000000+00'00'` | **固定时间戳**（无构建墙钟泄漏，位级复现前提） |

**OFD（3 份，zip 容器）**：条目仅 `OFD.xml` / `Doc_0/Document.xml` / `Doc_0/Page_0/Content.xml`；
条目时间戳**固定 1980-01-01**（zip epoch）；`comment` 为空；逐条目解压后过分类器 0 命中。

**docx 类样例**：本仓不含 tracked 的 docx（`docs/*.docx` 为生成物且已 `.gitignore`），
故无 `docProps/core.xml` 元数据（真实姓名重灾区）暴露面。

---

## 5. 脱敏第 5 步：构建产物本体扫描

"仓库树干净"证明不了"冻结产物干净"——产物内嵌的源码路径、构建机痕迹要单独扫。

**构建通道**（沿用 M5 结论，plan/06 决策行）：Python **3.12.10** 干净 venv +
PyInstaller **6.22.3** + PySide6 6.11.2（3.8 通道构建工具级不稳定，详见 HANDOFF-M6 §4）。

**产物与发布源码同基线**：

```bash
git diff <M5 提交>..HEAD -- src/     # 空 → 产物构建所用 src/ 与发布源码一致
```

**扫描（`sensitive_scan.py dist`）**：

```bash
python tools/sensitive_scan.py dist --dir dist --marker-b64 <b64> [...]   # 标记现场传入
```

- 打前产物：206 文件 / 156.6 MB → **0 命中**；打后（含 pdfplumber，见 §7）：**378 文件 / 184.3 MB → 0 命中**。
- 强标记 = 个人邮箱 / 个人目录前缀 / 姊妹项目名（**一律 base64 经 `--marker-b64` 现场传入，字面值不入仓**）。
- 刻意**不跑**邮箱/手机号等宽正则：上游厂商 DLL/SBOM 的公共串与二进制噪声不是本项目泄漏面，跑必刷屏。
- 禁区成分复核：产物树无仓库数据集文件（无 `.pdf`/`.ofd`/`.xlsx`/`cards.json`/`expectations.json`/`manifest.json`），
  与 spec 的 `datas` 白名单为空互为双保险。
- **上游噪声甄别**（记录以免被误判为泄漏）：产物内"用户目录"形态唯一命中是 **CPython 官方构建机
  残留的 macOS 用户目录路径**（位于 `base_library.zip` 的 stdlib 字节码内，属上游产物，非本项目数据）；
  GPU 厂商名命中是 Qt6Gui.dll 的**厂商串表**（`ASUSTek COMPUTER INC`）。二者均非本项目数据。
- 阳性对照：以"本项目 CLI 名/已知入包库名"为标记跑同一命令必须命中——
  实测 `reportlab` 在双 exe 各命中 99 次，证明产物扫描通路有效（而非静默失效）。

**Release 附件**：`dist/invoice-ledger-checker/` 打包为
`invoice-ledger-checker-v0.1.0-win64.zip`（378 条目，83.3 MB，zip 完整性校验 OK），

| 附件 | sha256 |
|---|---|
| `invoice-ledger-checker-v0.1.0-win64.zip` | `e6140c0fa74134b08527c28540fd1841fb6b343b7a814015ebf5408ff2956f2c` |

（zip 时间戳使重打包哈希必变：重打包后请同步更新本表与 Release 附件。）

---

## 6. 发布前置：提交元数据邮箱（四步覆盖不到的盲区）

**为何单列**：内容级扫描扫的是 blob，**扫不到 git 元数据**。本项目本地 git 身份邮箱为
真实个人邮箱（**字面值不复述**）。

| 项 | 记录 |
|---|---|
| 命中面 | 7 个提交 × 作者+提交者 = 14 处元数据字段（内容级扫描 0 命中，佐证"只在元数据"） |
| 改写 | `git filter-branch --env-filter` 全历史 → `<uid>+<user>@users.noreply.github.com`（uid 取 `gh api user --jq .id`） |
| 双滤合一 | 同一次 filter-branch 内一并消除 plan/HANDOFF-M6 正文里的 C 盘用户目录字面量（改文字描述） |
| 本地 config | `git config user.email <noreply>`（仓库级 `.git/config`；**全局配置未动**，不影响其他项目） |
| 对象清理 | 删 `refs/original` + `git reflog expire --expire=now --all` + `git gc --prune=now`；**不清则 `--all` 类扫描继续见到旧对象，白验** |
| 位级守门 | 改写前后 `git ls-tree -r HEAD -- data \| md5sum` 一致（`59ce1250…`）——历史改写未动冻结数据一个字节 |
| 终验 | 全对象库（含不可达）搜个人邮箱/个人目录字面量：**0 / 0** |
| 完整性 | `git fsck` 无错误 |

**两个坑的处置记录**（供后续里程碑复用）：
1. `filter-branch` 输出**接管道有 SIGPIPE 杀进程、写坏 ref 的风险**——本项目实测两次改写后
   `git fsck` 干净、ref 正常，但纪律仍应遵守：命令输出重定向到文件或直跑，不接 `head`/`grep`。
2. **Git-for-Windows 的 sed 在 BRE 里不匹配字面反斜杠**（实测 `s/`` `C:\Users\...` ``/前缀/` 静默不生效，
   而同一脚本里不含反斜杠的替换正常生效）→ 处置：改用 `git filter-branch --index-filter` +
   `git update-index --cacheinfo` 做**预计算 blob 替换**（无内容编辑、无引号地狱、可先 diff 验证
   "旧 blob→新 blob 只差目标行"）。

---

## 7. 干净环境验证（发布门核心）

**流程**：临时新目录 `git clone`（从本仓 file:// 克隆，用完即删）+ 全新 `py -3.8 -m venv`
（venv 建在 clone **之外**，使 `git status` 保持可用信号）+ **逐条照 README 快速开始执行**。

### 7.1 计数对账（dev 与干净环境逐项归因）

| 环境 | 收集/执行项 | passed | skipped |
|---|---|---|---|
| dev 全 extras（本机，dist 在场） | 177 | **177** | 0 |
| 干净 venv（仅 `[dev]`） | 168 | 149 | **19** |
| 干净 venv（`[all]`，CI `desktop` 作业等价） | 177 | 176 | 1 |

- **差 9 项** = `tests/test_app.py` 模块级 `importorskip("PySide6")` 把 10 项收成 1 个 skip 条目
  （dev 170→160 的老口径同源）。**"全绿"不可直接比 passed 数**，故按收集项对账。
- **19 skip 明细**：test_app 1（模块级）+ pdfplumber 11（parsing 3 / baseline_detection 2 /
  benchmark 4 / cli 2）+ test_cli openpyxl 1 + test_export openpyxl 2 + test_extras PySide6 1 +
  test_generator reportlab 2 + test_packaging dist 1。`-rs` 每项可见，无静默少跑。
- `[all]` 干净 venv 与 dev 完全同构（176+1 vs 177+0，唯一 skip 同为 dist 缺席）→ CI 平价成立。

### 7.2 README 逐条执行结果（干净 venv，锁生效后）

| 步骤 | 结果 |
|---|---|
| `pip install -U pip` | venv 自带 pip 20.2.3 → 升 25.0.1（README 前置行确有必要） |
| `pip install -U setuptools wheel` | 防 `invalid command 'bdist_wheel'`（README 已写） |
| `pip install -e ".[dev]"` / `".[all]"` | 成功；`[all]` 解析到 **reportlab 3.6.13**（锁生效）、PySide6 6.6.3.1 |
| `pytest` | 见 §7.1 |
| `demo` / `doctor` | exit 0；doctor 正确报告可选依赖面 |
| `generate --out data --seed 42 --n 60` | exit 0，且 **`git status` 无 data 差异 → 与入仓冻结数据逐字节一致** |
| `parse data/invoices --report` | exit 0，57 张（xml 35 + pdf 22）、0 失败、OFD 顺延 3、拒绝清单空 |
| `check … --anchor-manifest …` | exit 0，57 张卡、13 条异常（error 9 / suspicious 2 / review 2） |
| `export ledger.db` | exit 0，发票 55 张 + 异常 13 条，双 sheet + 三级条件格式 |
| `benchmark` | exit 0，门槛全过（宏平均 F1=1.0000 / 检出 100% / 误报 0 / 判定 100%），
且 `benchmarks/report.md` **无 diff**（同输入逐字节一致） |
| `app --db ledger.db` | offscreen 启动探针：事件循环真跑起来（被 timeout 掐断，退出码 124） |

### 7.3 干净环境门抓出的两个真问题（均已修复 + 加回归锁）

**问题 1：`generate` 在 3.8 上直接崩**（README 步骤不可用）

```
reportlab/pdfbase/pdfdoc.py: sig = self.signature = md5(usedforsecurity=False)
TypeError: 'usedforsecurity' is an invalid keyword argument for openssl_md5()
```

根因：`data` extra 原为 `reportlab>=3.6` **无上界** → 解析到 4.4.3，而 `usedforsecurity`
是 py3.9 才有的参数。**影响面不止 README**：CI 的 `desktop` / `benchmark` 作业（win-3.8 装
`data` extras）**从未跑过**（仓库此前无 remote），首跑同样会挂。

修复过程本身也踩了一次坑：第一版统一锁 `<4` → **3.12 通道装不上**（3.6.13 无 wheel、
sdist 构建失败）。故改为**双向环境标记**：

```toml
data = [
  "reportlab>=3.6,<4; python_version < '3.9'",
  "reportlab>=3.6;   python_version >= '3.9'",
]
```

连带把生成器的位级复现门改成分层守门（`tests/test_generator.py`）：冻结 PDF 字节由 3.6.13 产出，
故**只在 reportlab 3.x 环境比对 `.pdf` 字节**；XML/OFD 与 `ground_truth` **任何环境全量比对**
（不做整块 skip，防静默少跑）。回归锁：`tests/test_extras.py::test_reportlab_locked_below_4_on_py38`。
实测 py3.12 通道（reportlab 5.0.1）`generate` 正常产出 63 文件。

**问题 2：冻结 exe 缺 pdfplumber → 发行包解析不了 PDF（发布阻断）**

M5 产出的发行 exe 实测：`doctor` 报 pdfplumber 未安装；`check` **退出码 2**、
`[缺少依赖] 22 个文件未解析`、台账不生成；`export` 级联失败。GUI 导入向导是同一通路，
即"双击即用"名不副实。**为何此前未发现（两处叠加）**：

1. pdfplumber 经 `utils.import_optional` 在函数体内**惰性导入**，PyInstaller 静态分析看不见，
   而 spec 的 `hiddenimports` 只声明了 `openpyxl`；
2. M5 记录的"CLI 五连全过"把 **bash 管道退出码**（`tail`/`head` 的 `$?`）当成了 exe 的退出码——
   实际 `check`/`export` 早已非 0。**假绿**。本次全程单命令取真实退出码。

修复：spec `hiddenimports` 增 `pdfplumber`（连带 pdfminer.six / PIL / pypdfium2 / cryptography
入包，产物 157M → 186M）；回归锁
`tests/test_packaging.py::test_spec_hiddenimports_cover_lazy_optional_deps`。

**修复后冻结产物实测**（中立目录 + `env -i` 剥离 PATH，逐条取真实退出码）：

| 命令 | 结果 |
|---|---|
| `doctor` | exit 0，pdfplumber/reportlab/openpyxl/PySide6 均已安装 |
| `demo` | exit 0 |
| `generate --out data --seed 42 --n 60` | exit 0（reportlab 已入包） |
| `check data/invoices --db ledger.db --anchor-manifest …` | **exit 0**，60 文件成功解析 **57 张卡（pdf 22 + xml 35，0 失败）**，台账 339 KB 落盘 |
| `export ledger.db` | exit 0，xlsx 产出（15724 B，与源码环境同尺寸） |
| `benchmark --no-report` | exit 0，门槛全过（F1=1.0000 / 检出 100% / 误报 0） |
| `invoice-ledger.exe`（GUI 冒烟探针） | exit 0，**2599 ms**（Qt 启动 + 1.5 s 定时自动退出） |

### 7.4 环境 flake 甄别（本机崩溃体质，不与产品缺陷混淆）

本机为已知不稳定环境（HANDOFF-M6 §4：段错误 / 0xC0000005 / "不可能错误"族）。本次验证中出现
两类**一次性**异常，均按"先证伪、再定性"处置：

| 现象 | 甄别过程 | 结论 |
|---|---|---|
| 全量 pytest 偶发单条 PDF 解析失败（dev 一次、干净 venv 一次，**每次文件不同**） | 对全部 22 份 PDF 连续解析 **30 轮 = 660 次**，0 失败；失败文件在隔离重跑中必绿；文件字节与 git blob 一致 | **环境级随机**，非数据/解析缺陷 |
| 干净 venv 首次 all-extras pytest 段错误（exit 139） | 同命令重跑即绿（`-rs` 无异常、退出码 0） | 环境级随机 |

→ 处置：如实登记 + 重跑取绿；CI 跑在 GitHub runner（环境不同）不受本机体质影响。
**但零容忍门槛不因此放宽**：基准门槛（解析失败数=0）保持原样，只是把本机随机失败与真实回归区分开。

---

## 8. 发布后复核（GitHub 全新 clone）

发布完成后以 GitHub 端全新 clone 复核（不复用本机任何工作树）：

- [ ] `git clone` 新目录 → `git log --format='%ae %ce' --all | sort -u` 仅 noreply
- [ ] 重跑 `tools/sensitive_scan.py all` 全 0；`dist` 模式另行现场传标记
- [ ] 全新 venv 按 README 跑通（计数与 §7.1 一致）
- [ ] `gh run list` 对账：push 次数 = workflow run 数，全部作业绿
- [ ] `gh api` 回读仓库元信息与 topics；README 渲染与关键数值核对
- [ ] Release 资产可下载且 sha256 与 §5 表一致

（本节勾选状态在发布动作完成当轮回填。）
