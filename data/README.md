# data/ 数据台账

> 规则（ai-tool-project-sprint 阶段1）：每份数据登记来源与许可；规范条目挂出处+status；程序化自制带真值数据是核心资产（固定 seed 可复现，可注入已知缺陷做配对评测）。`_private/` 目录不入仓。

## 登记表

| 数据 | 类型 | 来源 | 许可 | 状态 |
|---|---|---|---|---|
| data/invoices/ | 合成发票文件 60 份：XML×35 + PDF×22 + OFD×3，batch_01/02/03 三批次 | 程序化生成：`py -m invoice_ledger_checker generate --out data --seed 42 --n 60 --anomaly-rate 0.35`（重跑逐字节一致，守门测试断言） | 自制，全虚构无隐私 | ✅ M1（2026-10-06） |
| data/ground_truth/ | 真值 JSON：cards.json（按文件路径为键的期望卡）、expectations.json（按号码为键的 expect/also_expect + missing_fields）、manifest.json（参数/批次锚/文件清单） | 与 invoices 同命令产出，一一对应；语义权威定义在 generator/synthetic.py 模块注释 | 自制 | ✅ M1（2026-10-06） |
| data/knowledge/ | 法规知识库：764号令（✅已核对 6 条）、11号公告（✅已核对 6 条）、56号令（✅已核对 4 条） | 官方渠道摘录，逐条挂出处 + 复核锚（reviewed_at/next_review/review_interval），见 knowledge/README.md 渠道记录 | 官方公开文告（逐字条文 + 出处形式） | ✅ M1（2026-10-06）；✅ M5 补核全部取得原文全文 |
| data/samples/ | 格式参考样例：synthetic-v1 XML 样张 + TEMPLATE_REFERENCE.md（三格式字段映射） | 本仓生成器产物抽样 + 自制文档；官方样例未获取（获取后追加登记） | 自制 | ✅ M1（2026-10-06） |

## 依据查证记录（题目阶段 2026-10-05 → M1 2026-10-06）

- 《发票管理办法》（国务院令第764号，2023-07-20 第三次修订）：**已核对 ✅**——第三条第二款（"发票包括纸质发票和电子发票。电子发票与纸质发票具有同等法律效力。国家积极推广使用电子发票。"）、第五条、第二十一条、第二十三条等原文经上海税务局转载页与商务部政策库直连逐字核对，6 条摘录入库（data/knowledge/764号令.json）
- 《发票管理办法实施细则》修改决定（国家税务总局令第56号，2024-03-01 施行）：**已核对 ✅（M5 补核取得原文全文）**——fgk 法规库 PDF 附件直链（HTTP 200 / 17 页 PDF）+ pdfplumber 本地提取，逐字核对实施细则新增第三/四/五条（电子发票数据电文定义·不得拒收·平台·数据安全）与第七条（发票基本内容），4 条摘录入库；M1–M4 未取得原文的渠道探索明细保留在 data/knowledge/56号令.json 的 verification.channels
- 国家税务总局公告2024年第11号（推广应用全面数字化的电子发票）：**已核对 ✅（M5 补核取得原文全文）**——fgk 法规库 content.html 路径（浏览器 UA/Accept-Language，HTTP 200 / 42741 字节）+ 本地剥 HTML 提取，逐字核对第一/二/三/四/十一/十二条（定义·票面要素·20 位号码法定分段·查验途径·施行日期），6 条摘录入库；两处订正（官方标题无「的」字、公告正文与附件不含 XML 格式条款）登记于 verification.corrections
- 查证方法纪律：搜索摘要不采信，只用可直连官方页面原文核对；查不到 → 显式"待核对"+已查渠道，继续推进不空转（M1 轮 4 次直连 2 次成功；M2 补核轮 10+ 次尝试取得官方解读页复核一致、原文全文未取得，未编造任何条文）

## 合成数据纪律（M1 落实 ✅）

- 公司名/品名取自内置虚构词库（28 家虚构企业、28 个服务/商品名），无真实主体；
- 纳税人识别号为 18 位假格式统一社会信用代码：`91 + 4位虚构地区码 + FAKE + 8位数字`——**含 FAKE 字样自证合成**，构成脱敏审查白名单标识；
- 发票号码 20 位 = 12 位虚构类型前缀 + 8 位后缀（前缀为虚构排版，不对应真实发票代码规则，见生成器 TYPE_PREFIX 注释）；
- 生成器唯一随机源 `random.Random(seed)`，同 seed+参数输出逐字节一致（tests/test_generator.py 守门断言，含入仓数据回归）。

## 收尾段（M6 2026-10-06，发布前复核）

- **数据本体脱敏复核**：`tools/sensitive_scan.py binaries` 单独扫二进制样例（文本扫描对二进制的盲区）——
  PDF Info 元数据域仅 `anonymous` / 厂商串 / 合成标题，`/CreationDate` **固定 2000-01-01**（无构建墙钟泄漏）；
  OFD zip 条目时间戳**固定 1980**、`comment` 空、逐条目解压 0 命中。**结论：数据本体无个人痕迹。**
- **位级不变守门**：M6 全历史邮箱改写前后 `git ls-tree -r HEAD -- data | md5sum` 一致 → 历史改写未动冻结数据一个字节；
  干净环境（新 clone + 新 venv）重跑 `generate --out data --seed 42 --n 60` 后 **`git status` 无 data 差异**
  → 生成器可复现性经发布门复验，与入仓冻结数据逐字节一致。
- **依据查证最终态**：三部法规原文**全部逐字核对完成**（764号令 / 11号公告 / 56号令，M5 收口）；
  补核渠道与逐字条文见 `data/knowledge/*.json` 的 `verification` 段与 [knowledge/README.md](knowledge/README.md) 补核履历。
- **复核锚**：三份法规 json 的 `verification` 均带 `reviewed_at` / `next_review` / `review_interval`
  （法规类一年），`status` 为精确枚举值 `已核对`/`待核对`（叙述全部移入 `status_note`）；
  逾期由 `tests/test_knowledge.py` 打印警告（**不改退出码**，避免到期日把构建判红）。
- **依据进产品输出**：8 条内置规则各挂 `basis`（法规 + 条号 + 逐字引文 + `knowledge_ref`），
  `Finding.basis` 随异常落库（`findings.basis_json`），CLI 告警行 / Excel「法规依据」列 /
  GUI 证据面板三处同源展示；代码里的字面引文与 json 的 `quote` 逐字一致由
  `tests/test_knowledge.py` 断言（运行期不读 `data/knowledge`——知识库不进 wheel）。
- **可复现性边界**：PDF 字节依赖生成库 reportlab 主版本（冻结数据由 3.6.13 产出）——现 `data` extra
  为单一 `reportlab>=3.6`（**不再按 Python 版本双向约束**，floor 已抬到 `>=3.12`）；位级复现门在
  XML/OFD/真值上全环境生效、**PDF 字节位级门只在 reportlab 3.x 环境生效**
  （`tests/test_generator.py` 按主版本收敛，CI 装 5.x 时该门不生效，如实披露）。
