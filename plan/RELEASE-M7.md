# RELEASE-M7：二次迭代发布留档（v0.2.0）

> **本文件随仓库公开**：一切敏感字面值（真实个人邮箱、个人目录、账号相关串）一律以类别/指代
> 呈现，不复述原文。落盘 2026-10-21。
>
> 结构 = 决策记录 + 五批次改动与门禁 + 干净环境复验 + 打包与产物扫描 + CI 与 Release。
> 每条记录**命令与结论**，不写"已验证"式空断言。

---

## 1. 决策（用户拍板，2026-10-21）

| 决策 | 选定 | 内容 |
|---|---|---|
| DEC-1 | **A** | 法规条号进产品输出：8 条规则各挂 `basis`，`Finding.basis` 随异常落库，CLI / Excel / GUI 三处显示「依据」 |
| DEC-2 | **A** | Python floor `>=3.8` → **`>=3.12`**；删两组 `python_version<'3.9'` 分支；CI 矩阵 3 腿 → 2 腿 |
| DEC-3 | **A** | README 测试数分两条口径（`.[dev]` / `.[all]`）+ 新增 `tests/test_doc_counts.py` 守门 |
| DEC-4 | **B** | 升 **0.2.0** + 重打包 exe + tag `v0.2.0` + Release（发布物与代码对齐） |

---

## 2. 改动清单（按批次；精确到文件）

### 批次一：法规依据进产品 + 知识库守门

| 文件 | 改动 |
|---|---|
| `src/invoice_ledger_checker/rules/engine.py` | `Finding` 加 `basis: Dict[str, Any] = field(default_factory=dict)`；`Rule` 加同名末位字段；`Finding.to_dict()` 加 `"basis": dict(self.basis)`；`DetectionEngine.run` 在「级别校验后、finding_id 生成前」加 `if not finding.basis and rule.basis: finding.basis = dict(rule.basis)` |
| `src/invoice_ledger_checker/rules/checks/__init__.py` | 新增 5 条条文常量（`_Q_764_21_1` / `_Q_764_21_2` / `_Q_NO11_DEFINITION` / `_Q_NO11_NUMBER_RULE`）+ 4 个 `_basis_*()` 工厂 + `_HEURISTIC_NOTE`；8 条 `Rule(...)` 各挂 `basis=` |
| `src/invoice_ledger_checker/storage/ledger.py` | `findings` 表加 `basis_json TEXT NOT NULL DEFAULT '{}'`；`add_finding` 写入；`list_findings` 读出 `basis`；新增 `_migrate_findings_basis()`（旧库 `ALTER TABLE ADD COLUMN`，幂等） |
| `src/invoice_ledger_checker/cli.py` | 新增 `format_basis()`（三处输出的唯一格式化入口）；`_print_findings` 在每条告警行后按需打印 `依据：<法规简称> <条号>[（工程口径，法规无直接条款）]` |
| `src/invoice_ledger_checker/export/excel.py` | `FINDING_HEADERS` 末位加「法规依据」；`_fill_finding_sheet` 追加该列（值走 `format_basis`）；列宽加第 10 列；发票 sheet 未动 |
| `src/invoice_ledger_checker/app/tabs.py` | `FindingsTab._show_evidence` 在证据 JSON 后追加 `\n\n依据: <basis_text>`；import 加 `format_basis` |
| `tests/test_knowledge.py`（新，12 项） | 结构层（entries/article_no/quote/status 精确枚举/复核锚/verification 键集统一/逾期只 warn）+ 一致性层（8 条规则 basis 完整、knowledge_ref 可解析、article 与 entry 一致、**quote 逐字相等**、弱关联必带 note、强关联不许带 note）+ 透传层（finding.basis == rule.basis 且进 to_dict） |
| `data/knowledge/764号令.json` | verification 加 `status_note: ""` / `corrections: []` / `reviewed_at` / `next_review` / `review_interval` |
| `data/knowledge/11号公告.json` | `status` 去后缀 → `已核对`；叙述移入 `status_note`；`checked_at` 只留 ISO；加三锚点 |
| `data/knowledge/56号令.json` | 同上 |
| `data/README.md` | 登记表第 11 行「⬜待核对 4 条 / ⬜待核对 3 条」→「✅已核对 6 条 / ✅已核对 4 条」；查证记录两段「待核对 ⬜」→「已核对 ✅（M5 补核取得原文全文）」并保留渠道叙述；收尾段加「复核锚」与「依据进产品输出」两条 |

**规则 → 条文映射（8 条）**：

| 规则 | 法规 | 条号 | knowledge_ref | note |
|---|---|---|---|---|
| R-ARITH-01 | 发票管理办法（2023 修订） | 第二十一条第一款 | `764号令.json#764-21-1` | — |
| R-ARITH-02 | 同上 | 第二十一条第一款 | `764号令.json#764-21-1` | — |
| R-DUP-01 | 11 号公告（数电票推广应用） | 第一条 | `11号公告.json#no11-definition` | — |
| R-DUP-02 | 发票管理办法（2023 修订） | 第二十一条第二款 | `764号令.json#764-21-2` | — |
| R-DUP-03 | 同上 | 第二十一条第二款 | `764号令.json#764-21-2` | — |
| R-SEQ-01 | 11 号公告（数电票推广应用） | 第四条 | `11号公告.json#no11-number-rule` | ✅ 工程口径 |
| R-TIME-01 | 发票管理办法（2023 修订） | 第二十一条第一款 | `764号令.json#764-21-1` | ✅ 工程口径 |
| R-TIME-02 | 同上 | 第二十一条第一款 | `764号令.json#764-21-1` | ✅ 工程口径 |

> **为什么运行期不读 json**：知识库不在 wheel 里（`data/` 不入包），装成 wheel 后该目录不存在。
> 故 quote 写字面常量，由 `test_knowledge.py` 断言与 json 逐字相等——单一事实源 + 零运行期依赖。

### 批次二：floor 与 extras 收口

| 文件 | 改动 |
|---|---|
| `pyproject.toml` | `requires-python ">=3.8" → ">=3.12"`；`license = { text = "MIT" }` → `license = "MIT"` + `license-files = ["LICENSE"]`；`setuptools>=61 → >=77`；删 `License :: OSI Approved :: MIT License` 与 `Programming Language :: Python :: 3.8`；`desktop` 4 条 → 2 条（`PySide6>=6.5` / `PySide6-Addons>=6.5`）；`data` 2 条 → 1 条（`reportlab>=3.6`）；注释改写为历史记录 |
| `.github/workflows/ci.yml` | `test` 矩阵 3 条 → 2 条（win3.12 / ubuntu3.12）；`desktop` / `benchmark` 的 `python-version "3.8" → "3.12"`；三处 `checkout@v4 → @v7`、三处 `setup-python@v5 → @v7`；注释同步 |
| `tests/test_ci_workflow.py` | `assert len(matrix) == 3 → == 2` + 新增「矩阵全为 3.12」断言；新增 `test_ci_actions_use_current_majors()`（checkout/setup-python 主版本 >= 7） |
| `tests/test_extras.py` | 两条 `py<3.9 锁` 断言改写为「无环境标记」断言（`test_desktop_has_no_python_version_markers` / `test_reportlab_single_unpinned_upper_bound`）+ 新增 `test_requires_python_floor_is_312()` |
| `README.md` | 限制节 GUI/reportlab 两段改为「当前 + 历史记录」双段，如实写「PDF 位级门在 CI（reportlab 5.x）上不生效」；「CI 作业分工」段改两矩阵 + 3.12 |
| `data/README.md` | 「可复现性边界」段改「当前 extra 不锁上界；PDF 位级门只在 reportlab 3.x 生效」 |
| `packaging/invoice_ledger_checker.spec` | 文档头「打包机 = win-3.8 CI 同环境」改为「Python 3.12 干净 venv」（floor 统一后的实际形态） |

### 批次三：测试数口径 + 版本单一来源

| 文件 | 改动 |
|---|---|
| `README.md` | 快速开始拆两条：`.[dev]` →「191 收集 / 174 passed + 18 skipped」；另起 `.[all]` →「201 收集 / 201 passed + 0 skipped」（并注明 dist 缺席时 test_packaging 动态层记 1 skip） |
| `tests/test_doc_counts.py`（新，5 项） | 两口径都存在 + 各自算术自洽 + 实测收集数与当前环境一致 + 两口径差值 == `tests/test_app.py` 用例数 |
| `tests/test_version_single_source.py`（新，3 项） | pyproject 与 `__version__` 一致 + PEP 440 形态 + 无第二处版本字面量 |
| `tests/test_cli.py` | `--version` 断言改为「与 `__version__` 一致」（不再硬编码版本号） |
| `tests/test_package.py` | 硬编码 `"0.2.0"`（按计划保留，与上一条互补） |
| `plan/HANDOFF-FINAL.md` | 第 38/95/169 行「170 = 151 绿 + 19 skip」→ 括号追加「2026-10-21 复核订正：实测 169 = 152 绿 + 18 skip」+ M7 后新值 |

### 批次四：清洁度

| 文件 | 改动 |
|---|---|
| `code/` | 空目录（0 文件、未跟踪）→ `rmdir`（保留 `code/` 在 .gitignore 之外，本来就不存在该条目） |
| `.gitignore` | 新增 `update/`（二次迭代交接物；防误推 + 防脱敏 tracked 模式命中本机路径） |
| `README.md` | 特性表 OFD 行 `P2` → `⬜ P2（未交付，导入时登记顺延）`，与上方 ✅ 行视觉区分 |

### 版本与发布（DEC-4=B）

| 文件 | 改动 |
|---|---|
| `pyproject.toml` / `src/invoice_ledger_checker/__init__.py` | `0.1.0` → **`0.2.0`** |
| `README.md` | 状态条 → 「v0.2.0 已发布（M0-M7 完成）」+ v0.2.0 变更摘要；路线图加 M7 行 |
| `make_m7_shots.py`（新，仓根） | 六页签离屏截图脚本（复用 M6 方法：offscreen + `QFontDatabase.addApplicationFont` 挂 CJK 字体 + 整窗 grab；异常清单页自动选中首行以显示「依据」） |

---

## 3. 门禁实测（逐条命令 + 输出）

### 批次一

```
$ python -m pytest tests/test_knowledge.py -o addopts=""
12 passed in 0.07s                                    # rc=0

负控：把 764号令.json 的 status 改成 "已核对X" 再跑
1 failed, 11 passed in 0.18s                          # 红（test_verification_status_is_exact_enum）
恢复后：12 passed in 0.07s

$ python -m invoice_ledger_checker check data/invoices --db %TEMP%/k.db 2>&1 | grep -c "依据："
29                                                    # 与告警条数一致

$ 读 xlsx 异常清单表头
['finding_id','规则ID','规则名称','级别','关联发票号码','说明','批次','状态','检出时间','法规依据']
首行末列 = '发票管理办法（2023 修订） 第二十一条第一款'

$ git status --porcelain data/invoices data/ground_truth benchmarks/
（空）

$ python -m pytest
191 passed in 23.77s                                  # 179 + 12
```

### 批次二

```
$ python -m build --sdist --wheel --outdir %TEMP%/dist-iter2 2>&1 | grep -ci "deprecat"
0                                                     # 改前 3+ 条（project.license 表 + License classifier ×2）

$ 读 wheel METADATA
Metadata-Version: 2.4
License-Expression: MIT
Classifier: Programming Language :: Python :: 3
Classifier: Programming Language :: Python :: 3.12
Requires-Python: >=3.12
License-File: LICENSE
Requires-Dist: reportlab>=3.6; extra == "data"
Requires-Dist: PySide6>=6.5; extra == "desktop"
Requires-Dist: PySide6-Addons>=6.5; extra == "desktop"
entries: 39 / data/ entries: []                       # 零 data/（与改前一致）

$ python -c "import PySide6; print(PySide6.__version__)"
6.12.0

$ python -m pytest tests/test_ci_workflow.py tests/test_extras.py -o addopts=""
11 passed in 0.79s

$ python -m pytest
193 passed in 29.55s

$ rm -rf build && git status --porcelain   # 构建临时目录已清
```

### 批次三

```
$ pytest --co -q -o addopts=""        # 全 extras
201 tests collected
$ pytest --co -q -o addopts=""        # 仅 dev
191 tests collected
$ pytest -o addopts=""                # 全 extras
201 passed in 23.52s
$ pytest -o addopts=""                # 仅 dev
174 passed, 18 skipped in 13.55s       # 174 + 18 = 191 + 1（test_app 模块级 skip）

负控 A：README「全在）：201 收集」改成 202
3 failed, 2 passed                    # 红（算术自洽 + 实测一致 + 差值==GUI 用例数）
恢复后：5 passed

负控 B：__version__ 改成 9.9.9
1 failed, 2 passed                    # 红（test_version_matches_pyproject）
恢复后：8 passed
```

### 批次四

```
$ test ! -d code && echo removed
removed
$ grep -n "^update/" .gitignore
26:update/
$ git status --porcelain
（只剩本次改动；update/ 不再出现）
```

---

## 4. 干净环境复验（批次五）

**克隆**：`git clone git@github.com:yuluo554/invoice-ledger-checker.git %TEMP%/verify-clone` → HEAD `74edaf9`
（工作树干净；后续修复提交 `716e826` 另跑一次，见 §6）。

**新 venv**（`py -3.12 -m venv .venv` + `pip install -U pip` + `pip install -e ".[all]"`）：

```
$ .venv/Scripts/python -m pytest -o addopts=""
200 passed, 1 skipped in 23.03s        # rc=0
skip 唯一项 = test_packaging.py:77（dist 未构建，新 clone 天然缺席）

$ .venv/Scripts/python -m invoice_ledger_checker --version
invoice-ledger 0.2.0                  # rc=0
$ ... demo                            # rc=0，输出含 13 处「依据：」
$ ... check data/invoices --db %TEMP%/v.db
rc=0；grep -c "依据：" = 29；台账 55 张（主键拒收同号副本 2 张）
$ ... benchmark --no-report
rc=0；门槛断言全部通过（F1>=0.95 / 检出率 100% / 误报 0 / 判定准确率 100%）
$ ... export %TEMP%/v.db
rc=0；Excel 异常清单表头末列 = 法规依据，首行 = 发票管理办法（2023 修订） 第二十一条第一款

$ git status --porcelain benchmarks/report.md
（空 —— 跑过 benchmark 后仍逐字节可复现）
$ sha256sum benchmarks/report.md
9dc7da75fddb236c156527179edf3c1efa75626b3fc9beccae7fd72552a9e4f4   # 与基线一致
$ git diff --stat HEAD~5..HEAD -- data/invoices data/ground_truth
（空 —— 冻结数据 60 份 + 3 份真值零差异）

$ python tools/sensitive_scan.py selftest
6 类阳性全报（email×2/idcard×2/intranet_ip×3/phone×2/secret×3/userpath×3）
+ 阴性对照 15 项全部未命中 + 类目覆盖 6/6 → [selftest] PASS      # rc=0
$ python tools/sensitive_scan.py all
tracked 128 文件 / history 20 提交 / messages 20 条 / metadata 100 字段 /
binaries PDF 22 + ZIP-OFD 3 → 全部 0 命中                        # rc=0
```

---

## 5. 打包与产物扫描（DEC-4=B）

**构建**（`build-venv312`：Python 3.12.10 + PyInstaller 6.22.3 + PySide6 6.11.2）：

```
$ build-venv312/Scripts/python -m PyInstaller packaging/invoice_ledger_checker.spec \
      --distpath %TEMP%/ilc-build/dist --workpath %TEMP%/ilc-build/build --noconfirm
rc=0；Build complete!（115 秒）

注：`pyinstaller.exe` 直接调用会静默退出（rc=1、stdout/stderr 均空），
    必须用 `python -m PyInstaller` 才能拿到日志与真实退出码——本轮踩到，记此。
```

**产物冒烟（六命令真实退出码，单跑不看管道 `$?`）**：

| 命令 | rc | 证据 |
|---|---|---|
| `invoice-ledger-cli.exe --version` | 0 | `invoice-ledger 0.2.0` |
| `invoice-ledger-cli.exe doctor` | 0 | 六组件全「已安装」 |
| `invoice-ledger-cli.exe demo` | 0 | 13 处「依据：」 |
| `invoice-ledger-cli.exe generate --out … --seed 42 --n 60` | 0 | 生成成功 |
| `invoice-ledger-cli.exe check <绝对路径>/data/invoices --db …` | 0 | 入库 55 张、29 处「依据：」 |
| `invoice-ledger-cli.exe export …` | 0 | Excel 含「法规依据」列 |
| `invoice-ledger-cli.exe benchmark --data <绝对路径>/data --no-report` | 0 | 四门槛全过 |
| `INVOICE_LEDGER_GUI_SMOKE=1 invoice-ledger.exe` | 0 | 1.5s 自动退出、无输出（冒烟通路） |

> **路径坑**：exe 的工作目录不是仓库根，`check data/invoices` 用相对路径会 `rc=2`（「目录不存在」）——
> 这是正确行为（参数校验），不是缺陷；验收用绝对路径。首轮相对路径跑出的 `ledger.db` 落在产物树里，
> 已删除并用 `sensitive_scan.py dist` 复核（见下）。

**产物树扫描**：

```
$ python tools/sensitive_scan.py dist --dir %TEMP%/ilc-build/dist
[dist] 378 个产物文件 / 184.3 MB（强标记 0 个 + 禁区成分复核）
[dist] 命中 0 行（0 类）                      # rc=0

$ 逐条复核 test_packaging 的 forbidden 正则（.env/.key/_private/ledger.db/.sqlite）
forbidden hits: []
```

**打包 zip**（`zipfile` `ZIP_DEFLATED` compresslevel=6，条目按相对路径排序）：

```
entries 378 / testzip None / 87,383,299 B
sha256 e8095227e4c894590487e026dd8949a572d123736ddfdffb71ef9ea47d70694f
zip 内禁区成分（.db/.sqlite/.xlsx/.env/.key/_private）：[]
```

> **与 v0.1.0 的可比性**：v0.1.0 = 378 条目 / 87,377,464 B；v0.2.0 = 378 条目 / 87,383,299 B。
> 条目数相同（同一 spec、同一 hiddenimports 面），字节差 5.8 KB 来自源码与 Qt 版本差异。
> **重打包哈希必变**（zip 内条目时间戳为构建时刻），故 sha256 只对同一份 zip 有意义。

**六页签截图**（`make_m7_shots.py`，offscreen + CJK 字体 + 整窗 grab）：

```
shot-1-导入.png / shot-2-台账.png / shot-3-异常清单.png /
shot-4-看板.png / shot-5-导出.png / shot-6-设置.png     各 1280 x 820
```

`shot-3-异常清单.png` 证据面板底部可见：`依据: 发票管理办法（2023 修订） 第二十一条第一款`
—— DEC-1=A 的 GUI 侧落地证据。状态栏显示相对路径 `dist/shot.db`，无本机目录信息。

---

## 6. CI 与 Release

### 6.1 首次 push 红（如实记录）

`74edaf9` 的 run **39624487152**：`desktop` job 失败，其余 3 job success。

**根因**：`tests/test_doc_counts.py` 的口径选择器写的是「任一重依赖缺失 → `.[dev]` 口径」。
CI 的 desktop 作业装 `[dev,parse,data,export,desktop]`（**缺 report/docx**），
于是被误判为 dev 口径（expected 191），而实测 201（GUI 模块在收集列表内）。

**事实**：收集数**只**由 `tests/test_app.py` 的模块级 `pytest.importorskip("PySide6")` 决定，
与其它 extras 无关。修复 = 改按 PySide6 可导入性选口径，并把踩坑写进 docstring。

**修复提交** `716e826`；三种环境实测各 5 项全过（dev-only / full extras / desktop-like 缺 docx）。

### 6.2 修复后 CI（run 39625628026 @ `716e826`）

| job | 结论 |
|---|---|
| `test (windows-latest, 3.12)` | success |
| `test (ubuntu-latest, 3.12)` | success |
| `desktop` | success |
| `benchmark` | success |

**注解核查**：

```
job 119309973411 (benchmark):        0 条注解
job 119309974086 (test ubuntu):      1 条注解
job 119309974231 (desktop):          0 条注解
job 119309974265 (test windows):     0 条注解
```

唯一 1 条为 `notice`：`The ubuntu-latest label will migrate to Ubuntu 26 beginning
October 19, 2026.` —— **平台迁移通知，与 actions 版本无关**（改前每个 job 各 1 条
`Node.js 20 is deprecated … checkout@v4, setup-python@v5`，现已归零）。

> **纪律**：`test` 作业只装 dev，GUI 模块整模块不进收集，故 CI 的 `test` 腿跑的是
> 191 收集口径；`desktop` 作业装齐后跑 201。两作业对 `test_doc_counts` 的期望值不同，
> 这正是修复点。

---

## 7. 残留与待办（如实登记）

1. **PDF 位级门在 CI 上不生效**：CI 装 reportlab 5.x，`tests/test_generator.py` 按主版本收敛，
   PDF 字节比对只在 reportlab 3.x 环境断言。已写进 README 限制节与 `data/README.md`。
2. **sdist 不自足**（73 条目，缺 `data/`/`.github/`/`packaging/`）：本仓发布形态是 GitHub Release 的
   exe zip，不是 PyPI；此项**不在本轮范围**（与诊断方口径一致）。
3. **OFD 解析仍未实现**（P2 顺延，`NotImplementedError` 保持 14 行原样）。
4. **GUI 六页签未做真实双击目检**：本轮只做离屏渲染截图 + `INVOICE_LEDGER_GUI_SMOKE=1` 冒烟
   （rc=0）。真实双击目检需用户在 Windows 上执行。
5. **`update/` 已入 .gitignore**：交接物不入仓；执行记录留在本地 `update/03-执行记录.md`。

---

## 8. 复现命令速查

```bash
# 1) 全 extras 测试（仓根）
python -m pip install -e ".[all]" && python -m pytest -o addopts=""

# 2) 依据进输出
python -m invoice_ledger_checker check data/invoices --db %TEMP%/k.db | grep -c "依据："

# 3) 知识库守门 + 负控
python -m pytest tests/test_knowledge.py -o addopts=""

# 4) 构建（零弃用警告 + 元数据）
python -m build --sdist --wheel --outdir %TEMP%/dist-iter 2>&1 | grep -ci deprecat

# 5) 打包（必须用 python -m PyInstaller，直接调 exe 会静默退出）
python -m PyInstaller packaging/invoice_ledger_checker.spec \
    --distpath %TEMP%/ilc-build/dist --workpath %TEMP%/ilc-build/build --noconfirm

# 6) 产物扫描
python tools/sensitive_scan.py dist --dir %TEMP%/ilc-build/dist

# 7) 截图
python make_m7_shots.py <db_path> <out_dir>
```