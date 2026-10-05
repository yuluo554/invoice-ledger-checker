# 合成发票三格式模板参考（M2 解析器字段映射权威出处）

> 权威顺序：本文件与 `generator/synthetic.py` 模板一致；冲突时以生成器代码
> 为准并回填本文件。官方数据规范获取后追加"官方映射（待核对）"小节。
> 所有样例值均为虚构。

## 1. XML 数据电文（synthetic-v1）

编码 UTF-8；根元素 `ElectronicInvoice version="synthetic-v1"`；注释行含
"程序生成/合成"标识（解析器应忽略注释）。节点路径 -> InvoiceCard 字段：

| XML 节点路径 | InvoiceCard 字段 | 说明 |
|---|---|---|
| `/ElectronicInvoice/InvoiceHeader/InvoiceNumber` | `invoice_number` | 20 位号码，主键 |
| `/ElectronicInvoice/InvoiceHeader/InvoiceType` | `invoice_type` | 数电普票/数电专票/电子普票/纸质专票/纸质普票 |
| `/ElectronicInvoice/InvoiceHeader/IssueDate` | `issue_date` | YYYY-MM-DD |
| `/ElectronicInvoice/InvoiceHeader/Buyer/Name` | `buyer_name` | 可缺失（INJ-FIELD-MISS），缺失 -> 空串 + field_flags |
| `/ElectronicInvoice/InvoiceHeader/Buyer/TaxId` | `buyer_tax_id` | 可缺失；18 位假格式 `91+4位地区码+FAKE+8位数字` |
| `/ElectronicInvoice/InvoiceHeader/Seller/Name` | `seller_name` | 恒存在 |
| `/ElectronicInvoice/InvoiceHeader/Seller/TaxId` | `seller_tax_id` | 恒存在 |
| `/ElectronicInvoice/InvoiceHeader/Items/Item` | `items[]` | 1-5 行；每行含 Name/Amount/TaxRate/TaxAmount |
| `Items/Item/Name` | `items[i].name` | |
| `Items/Item/Amount` | `items[i].amount` | 不含税金额，两位小数文本 |
| `Items/Item/TaxRate` | `items[i].tax_rate` | 如 `0.13`；仅末行可缺失 |
| `Items/Item/TaxAmount` | `items[i].tax_amount` | |
| `/ElectronicInvoice/InvoiceHeader/AmountWithoutTax` | `amount` | 合计金额（不含税） |
| `/ElectronicInvoice/InvoiceHeader/TaxAmount` | `tax_amount` | 合计税额 |
| `/ElectronicInvoice/InvoiceHeader/TotalWithTax` | `total_with_tax` | 价税合计 |
| `/ElectronicInvoice/InvoiceHeader/TotalWithTaxCN` | `total_with_tax_cn` | 价税合计大写 |
| `/ElectronicInvoice/InvoiceHeader/Remark` | `remark` | 可缺失（为空或 FIELD-MISS 时整个节点不存在） |

数值清洗注意（plan/04 §2.1）：千分位/全角/￥ 剥离后必须仍为合法 Decimal，
否则丢弃该值 + 降置信度；本项目生成器恒输出半角两位小数，但解析器按
防御性规则实现。

## 2. 版式 PDF（reportlab，STSong-Light 文本层）

页 240mm×140mm；label 与 value 为相邻 drawString（同 y 轴带），供
pdfplumber `extract_words()` 的 label-slot 匹配。标签全集（解析器标签词典）：

- 头部（固定槽位）：`发票号码：`、`开票日期：`、`购买方名称：`、
  `购买方税号：`、`销售方名称：`、`销售方税号：`（FIELD-MISS 时对应
  标签+值整行不绘制）
- 明细表头：`项目名称`（x=12mm）、`金额`（110mm）、`税率`（140mm）、
  `税额`（160mm）；数据行 y 步进 6mm
- 汇总：`合计：`（值形如 `1000.00（税额 130.00）`）、
  `价税合计（大写）：`、`（小写）￥1130.00`（"（小写）"与金额同串绘制）、
  `备注：`（空备注不绘制）

已知陷阱预演：标签与值是两个独立字符串（非同串）→ 词级配对需按 x 间距；
大写金额整行截取（`价税合计（大写）` 标签之后同 y 的首个词）。

## 3. OFD（简化 GB/T 33190 zip）

zip 成员：`OFD.xml`（DocInfo/DocRoot）、`Doc_0/Document.xml`（Pages 列表）、
`Doc_0/Page_0/Content.xml`（TextObject/TextCode 文本行）。文本语义与 PDF
一致（同一 `_invoice_lines` 产出）：标签串 `XXX：` 与值串相邻 TextObject，
明细行为 4 个 TextObject（名称/金额/税率/税额，x 坐标区分）。解析器按
TextCode 全文拼接后走与 PDF 相同的 label-slot 逻辑。

## 4. 真值与文件名约定

- 文件名 = `<20位发票号码>.<xml|pdf|ofd>`；批次 = 目录名（batch_01/02/03）；
- 同一号码至多两份文件（INJ-DUP-EXACT 逐字节副本 / INJ-DUP-JOINT 再制副本），
  跨批次存放——解析层不得因同号文件报错，交由台账主键与规则层判重；
- 真值卡见 `data/ground_truth/cards.json`（按文件路径为键）；
  注入期望见 `expectations.json`（按号码为键）；语义见生成器模块注释。
