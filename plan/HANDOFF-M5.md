# HANDOFF-M5（M4 收尾 → M5 桌面交付 续接快照）

> 用法：新对话启动命令 `/goal 读取 plan/HANDOFF-M5.md 继续完成任务`（相对路径；启动命令由用户侧拼绝对路径）。
> 本快照落盘于 2026-10-06，M4（内置基准）收尾时。方法论：ai-tool-project-sprint。

## 1. 当前进度（M4 已完成）

- **基准模块** `benchmarks/benchmark.py`（包内，与 field_match.py 同目录）：
  - 字段解析基准 = 冻结 60 份 vs cards.json 字段级对账，**复用 field_match.flatten_card**
    同口径（items 展开、空==空计正确、evidence/confidence/field_flags/batch_id 不参与），
    且逐文件 P/R/F1 与 `field_match.compare()` 的一致性由内部断言守门（防两套判定漂移）；
    产出微平均 + 宏平均 + 分字段表（items[i] 归并为 items[*]，16 字段）。
  - 异常检测基准 = 八规则引擎 vs expect ∪ also_expect 全集：对账键 (号码, rule_id)、
    级别并入三元组；检出率=TP/真值异常、误报率=FP/全部告警、判定准确率=级别一致
    三元组/真值异常；多号码 finding 按号码展开；OFD 顺延号码无期望（无结构缺口）。
  - 门槛断言 `gate_failures()`：F1≥0.95、检出率 100%、误报 0、判定准确率 100%
    + 零容忍项（冻结数据解析失败/未知号码告警/批次锚点缺失 anchors_missing）。
  - 确定性报告 `write_report()`：无墙钟（无时间戳/路径/环境），LF 行尾，
    **同输入重跑逐字节一致**（测试守门）；OFD 3 份顺延逐份显式登记。
- **CLI `benchmark` 命令**：`--data`（默认 data）/`--report`（默认 benchmarks/report.md）/
  `--no-report`；一条命令出指标表（stdout 与报告同数字）；退出码：通过=0、
  门槛未达=1（回归信号）、目录/真值缺失或缺 pdfplumber=2（与 parse/check 契约一致）。
- **冻结报告入仓** `benchmarks/report.md`（生成物，README 引用）。实测：宏平均
  F1=1.0000（微平均同）、检出率 100%（**18/18 对**真值异常）、误报 0、判定准确率
  100%；13 findings 形态与 M3 锚点一致；58 号码对账无未知告警。
- **回归纪律落地**：CI 新增 `benchmark` 作业（win-3.8 + `[dev,parse,data]` extras，
  `--no-report`）；本地一键重跑 `py -m invoice_ledger_checker benchmark`。
- **README 回填**：指标表实测值、特性表/路线图 M2/M3/M4 状态、快速开始 + benchmark 命令。
- **测试**：tests/test_benchmark.py 6 项（门槛全对、报告确定性+OFD 登记、CLI exit 0/2、
  门槛触发逐项断言）；pytest **144 全绿**（=M3 138 + 新增 6）；干净 venv **131 绿/13 skip**
  （=129+2 新跑、9+4 新 skip，CI 平价维持——skip 全为 pdfplumber/reportlab 依赖路径）。
- **法规补核（顺带项，未取得原文）**：多轮检索首次定位 fgk 内容页直链
  `/zcfgk/c100012/c5236067`（摘要确认对应 11 号公告），但 WAF+JS 渲染双拦截
  （WebFetch/web_reader/curl+浏览器 UA 三通道均 403 或网络错误；agent-browser 真实
  浏览器因本机 Chrome 启动崩溃不可用）——两份 knowledge JSON 与 data/knowledge/README.md
  已登记本轮，status 维持待核对。

## 2. M5 待办（桌面交付，DoD 见 plan/05 §2 M5 行）

1. **环境复核先行**：安装 `.[desktop]` 复核 PySide6 cp38 wheel（plan/03 §3 待核对项：
   6.7 起 cp38 无 wheel → pyproject 已锁 `>=6.5,<6.7; python_version<'3.9'`，装最新
   6.5/6.6 实测并回写 plan/03 表格标注）；QtCharts 在 PySide6-Addons。
2. **Excel 导出** `export/excel.py`（openpyxl，extras: export；当前为结构桩）：
   发票 sheet + 异常清单 sheet + 条件格式标红；CLI `export` 命令接通（现为 stub 打印 M5）。
3. **GUI** `app/main.py`（PySide6；当前仅依赖门+桩）：六窗口组件按 plan/04 §6——
   导入向导 / 台账表格（分页+多维筛选+增删改查）/ 异常清单（level 着色+证据面板）/
   看板（QtCharts 月度趋势/供应商 Top-N/类型分布）/ 导出对话框 / 设置+状态栏
   （免责声明常驻）；CLI `app` 命令接通；数据源复用 Ledger 查询（storage 已就绪）。
4. **extras 覆盖运行期真实 import 断言测试**（plan/03 §4 纪律）：export/desktop 组件
   缺依赖路径显式 skip 计数上报。
5. **PyInstaller 打包**：extras dev 打包子集（py3.8 锁 `<7`）；onedir 模式（启动快）；
   主 .spec 入仓；打包机 = win-3.8 CI 同环境；exe 干净环境（无 Python）双击实测。
6. **技术报告** `docs/技术报告.md`（plan/05 §4：解析方案/检测算法/打包与离线设计；
   + docx 生成器脚本入仓）。
7. 演示 GIF 录制（M6 Release 材料，可延至 M6 初）。
8. 里程碑收尾：plan/00、05 状态回写 ✅；写 plan/HANDOFF-M6.md；本文件头部标注过时。
9. （顺带）11号公告/56号令补核：需健康浏览器环境（本机 Chrome 启动崩溃，见 §4），
   fgk 直链已定位 `/zcfgk/c100012/c5236067`（11 号公告）。

## 3. 既定口径清单（M0-M4 定稿收口速查区；改前先对照，动一笔须回写 plan）

**M4 新增（基准/报告/CI）**：

1. 字段级对账复用 `field_match.py`（flatten_card 同口径）；基准逐文件与
   `field_match.compare()` 一致性由内部断言守门，改 field_match 必须同步 benchmark；
2. 检测指标：对账键 (号码, rule_id)、级别并入三元组；检出率=TP/真值异常、
   误报率=FP/全部告警、判定准确率=级别一致三元组/真值异常；多号码 finding 按号码展开；
3. 门槛：解析宏平均 F1≥0.95；检出率=100%、误报=0、判定准确率=100%；零容忍项=
   冻结数据解析失败>0、未知号码告警>0、批次锚点缺失（anchors_missing 非空）；
4. `benchmark` 退出码：通过=0 / 门槛未达=1（回归信号）/ 目录不存在、真值缺失、
   缺 pdfplumber=2；
5. 零 API 可重复 = 纯规则通路 + 固定输入 + 无墙钟：基准引擎只传 manifest 批次
   anchor（**不传 default_anchor**，禁墙钟兜底；缺映射=门槛失败）；报告
   `benchmarks/report.md` 不含时间戳/路径/环境，`write_report` 强制 LF，同输入
   逐字节一致（tests/test_benchmark.py 守门）；报告为生成物入仓，改数据/规则后重跑刷新；
6. benchmark CLI 形态：`--data`（默认 data）/ `--report`（默认 benchmarks/report.md）/
   `--no-report`（CI 用）；
7. **基准锚点数字**（改数据/规则/引擎/接口会打挂 tests/test_benchmark.py 与
   tests/test_baseline_detection.py，属预期回归门）：58 号码、57 解析卡、
   真值异常 18 对、告警 18、13 findings（形态见两测试文件）、分字段 16；
8. CI：test 作业（win3.8/win3.12/ubuntu3.12，仅 dev extras，PDF 路径 skip）
   + benchmark 作业（win-3.8，dev+parse+data extras，`--no-report`）；两作业职责
   分离——改 CI 装机清单会改变 skip 计数口径。

**M0-M3 既有口径全部有效（速查版）**：

- InvoiceCard schema（plan/04 §1）；解析映射权威 = TEMPLATE_REFERENCE（synthetic-v1）；
  PDF label-slot 三条实测口径（双栏截断/大写合并词/明细 x 列聚类）；
- 真值双键：cards.json 按文件路径、expectations.json 按号码；对账 = expect∪also_expect
  全集（防"只验主期望"假绿）；权威出处 = generator/synthetic.py 模块注释；
- 数值清洗/失败语义：解析不到留空串+field_flags，不造默认值；对账口径
  evidence/confidence/field_flags/batch_id 不参与，空==空计正确；confidence 语义；
- 八规则注册顺序 = 执行顺序（plan/04 §3.1）；入库与判重分离（引擎输入=全部解析卡
  含被拒副本，R-DUP-01=批内重复∪existing_numbers）；R-DUP-02 排除纯复制件（语义字段
  全等）；R-DUP-03 金额=total_with_tax、tol=0.00、窗 1d；R-SEQ-01 跨前缀不产出
  finding；R-TIME-02 仅追溯方向（未来票 R-TIME-01 全覆盖）；
- 引擎 `run(cards, ctx_extra=None)`：ctx 三键 batch_anchors/default_anchor/
  existing_numbers；finding_id = rule_id + ":" + "|".join(全部号码)（无号码 "-"）；
  规则参数键名：arith_tolerance/dup_date_window_days/dup_amount_tol/seq_suffix_len/
  seq_min_len/seq_date_window_days/time_n_period；字段缺失一律跳过不硬判；
- check 命令：--anchor-manifest 基准通路 / 缺省 anchor=导入当天；退出码同 parse
  （坏文件=0，目录不存在/无可解析文件/缺依赖=2）；create_batch 幂等；findings 按
  finding_id 幂等拒收；重复检测需新 --db（重复导入本身是 R-DUP-01 信号）；
  demo=端到端（生成→解析→入库→检测，临时目录自清理，内存库）；
- 测试纪律：stdlib+pytest 模块级，重依赖函数内 import_optional+显式 skip；
  干净 venv 与 dev 环境**收集数必须一致**（skip 计数上报）；核心零依赖；
  requires-python≥3.8 语法（无 match/PEP604）；退出码契约（未交付/缺依赖=2）；
- 生成器：唯一随机源 random.Random(seed)，同 seed 位级一致（EOL=LF 门）；OFD zip
  固定时间戳；PDF invariant=1；合成数据 FAKE 税号自证虚构。

## 4. 本机环境坑（M4 实测增量 + 存量）

- **M4 新增**：本机 **Chrome 启动崩溃**（agent-browser 自动起 Chrome exit 3 无
  DevToolsActivePort；`--no-sandbox --user-data-dir --disable-gpu` 参数组合变挂起，
  需 TaskStop）——真实浏览器自动化当前不可用：GUI 录屏/演示、fgk 补核需先解决
  （排查已开 Chrome 实例占用/公司策略/换 Edge channel）；
- **M4 新增**：fgk.chinatax.gov.cn 有 WAF 反爬 + JS 渲染双拦截（curl 带浏览器 UA
  也 403 挑战页），静态抓取通道全部不可达——别再浪费轮次试 WebFetch/reader/curl；
- **M4 新增**：干净 venv 由 `py -m venv` 生成后用 `Scripts/python.exe`（venv 里没有
  `py.exe`）；老 pip 20.2.3 需先 `python -m pip install -U pip` 才能可编辑安装
  （README 已登记）；
- **M4 重申**：pytest `-q` 输出经 bash 管道时 summary 行偶发被吞——重定向到文件后
  单独 grep；整轮 pytest 收集也可能偶发 `AttributeError: 'Compare' object has no
  attribute 'push_format_context'`（断言重写抖动，同命令重跑即绿，勿当真失败）；
- **存量（仍有效）**：Python 3.8.8 唯一解释器（`py` 即 3.8）；pip 清华镜像 +
  `NO_PROXY="*" no_proxy="*"`；`PYTHONDONTWRITEBYTECODE=1` 全程携带；统一
  `py -m invoice_ledger_checker`；Git Bash 下 `py -X utf8`，测试内 subprocess 显式
  PYTHONIOENCODING=utf-8；pdfplumber 在 py3.8 import 时打
  CryptographyDeprecationWarning（无害，比对输出注意过滤）；Git Bash `/tmp` 对
  Windows Python 不可见（临时目录建仓内）；PySide6 未装（M5 首项复核 cp38 wheel）；
  *.db 已在 .gitignore（测试一律 tmp_path，防仓库根残留 ledger.db）。

## 5. M5 DoD checklist（收尾逐项打勾，没做到的写偏差说明）

- [ ] PySide6 cp38 wheel 复核结论回写 plan/03 §3 表格（消除"待核对"标注）
- [ ] `export` 命令：Excel 发票+异常清单双 sheet，条件格式标红正确（用例断言样式）
- [ ] `app` 命令：六窗口组件可演示（导入/台账/异常清单/看板/导出/设置+状态栏）
- [ ] 看板 QtCharts 三图（月度趋势/供应商 Top-N/类型分布）
- [ ] extras 覆盖运行期真实 import 断言测试（export/desktop 缺依赖显式 skip 计数）
- [ ] PyInstaller onedir + 主 .spec 入仓；exe 干净环境（无 Python 机器）双击实测
- [ ] 技术报告 docs/技术报告.md（解析方案/检测算法/打包与离线设计）+ docx 脚本
- [ ] 基准不回退：`benchmark` 门槛全过（benchmarks/report.md 刷新后 diff 仅指标不变）
- [ ] pytest 全绿且收集数与 M4 的 144 项对账清楚（新增多少、为何）
- [ ] 演示 GIF 录制落 docs/（M6 Release 材料）
- [ ] plan/00、05 状态回写；HANDOFF-M6 落盘；本文件头部标注已过时
- [ ] （顺带）11号公告/56号令补核：健康浏览器环境抓 fgk 直链原文，逐字核对改 status

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
    --anchor-manifest data/ground_truth/manifest.json
# 注意：重复对同一 --db 跑 check 会把全部号码判 R-DUP-01（重复导入=异常信号）；基准请用新库

# 基准（M4；门槛未达 exit 1 = 回归信号）
py -X utf8 -m invoice_ledger_checker benchmark                 # 出指标表 + 刷新 benchmarks/report.md
py -X utf8 -m invoice_ledger_checker benchmark --no-report     # 只看指标不落盘（CI 形态）

# 冻结对账（改解析器/生成器/规则后必跑）
# pytest 内置：tests/test_parsing.py 字段冻结对账 + tests/test_baseline_detection.py 检测对拍
#              + tests/test_generator.py 位级回归 + tests/test_benchmark.py 门槛与报告确定性

# 安装（pip 代理规避 + 不写 pyc；venv 内用 Scripts/python.exe 且先升级 pip）
NO_PROXY="*" no_proxy="*" PYTHONDONTWRITEBYTECODE=1 py -m pip install -e ".[all]" -i https://pypi.tuna.tsinghua.edu.cn/simple

# git（提交前三核对：pwd / git log --oneline -1 / git remote -v）
git add -A && git commit -m "..."
```
