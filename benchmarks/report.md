# 内置评测基准报告（M4 生成物）

> 由 `py -m invoice_ledger_checker benchmark` 生成；零 API 可重复——纯规则通路、
> 固定输入（冻结数据 + manifest 批次 expense_anchor）、无墙钟，同输入重跑本文件
> 逐字节一致（守门测试断言）。口径权威：plan/05 §3 与 generator/synthetic.py
> 模块注释；字段级对账复用包内 [field_match.py](../src/invoice_ledger_checker/benchmarks/field_match.py) 同一实现。

## 1. 数据概览

| 项 | 值 |
|---|---|
| seed / n / anomaly_rate | 42 / 60 / 0.35 |
| 格式分布 | ofd 3 / pdf 22 / xml 35 |
| 批次 | batch_01（anchor 2026-07-15，21 文件）；batch_02（anchor 2026-08-15，19 文件）；batch_03（anchor 2026-09-15，20 文件） |
| 解析 | 成功 57 / 60（OFD 顺延 3 份 P2 不参与指标，失败 0） |

### OFD 顺延登记（P2 加分项未交付，显式登记）

- `invoices/batch_03/26910000000010000196.ofd`
- `invoices/batch_01/26910000000010000303.ofd`
- `invoices/batch_03/25910000000010000414.ofd`

OFD 顺延号码不挂任何规则期望（对真值全集对账无结构性缺口，tests/test_baseline_detection.py 守门）。

## 2. 字段解析基准（冻结数据 vs cards.json，字段级）

| 口径 | P | R | F1 |
|---|---|---|---|
| 微平均（全字段聚总） | 1.0000 | 1.0000 | 1.0000 |
| 宏平均（分字段再平均，门槛 0.95） | 1.0000 | 1.0000 | 1.0000 |

分字段表（items[*] 为明细行字段按行聚合；空==空计正确，口径同 field_match.py）：

| 字段 | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|
| amount | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| buyer_name | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| buyer_tax_id | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| invoice_number | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| invoice_type | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| issue_date | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| remark | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| seller_name | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| seller_tax_id | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| tax_amount | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| total_with_tax | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| total_with_tax_cn | 57 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| items[*].amount | 171 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| items[*].name | 171 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| items[*].tax_amount | 171 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| items[*].tax_rate | 171 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

不一致清单：无。

## 3. 异常检测基准（八规则 vs expect ∪ also_expect 全集）

对账语义：引擎 Finding 按发票号码展开为 (号码, rule_id) 对与真值全集对拍——多记=误报、少记=漏报、级别不符=错判；时间基准 = manifest 批次 expense_anchor（基准通路，与墙钟无关）。

| 指标 | 值 |
|---|---|
| 真值异常（expect ∪ also_expect 对数） | 18 |
| 引擎告警（按号码展开） | 18（13 条 finding） |
| TP / FP / FN / 级别不符 | 18 / 0 / 0 / 0 |
| 检出率（TP/真值异常） | 100.00% |
| 误报率（FP/全部告警） | 0.00% |
| 判定准确率（级别一致/真值异常） | 100.00% |

finding 形态（rule_id × 级别 × 条数）：

| rule_id | 级别 | 条数 |
|---|---|---|
| R-ARITH-01 | error | 2 |
| R-ARITH-02 | error | 2 |
| R-DUP-01 | error | 2 |
| R-DUP-02 | error | 1 |
| R-DUP-03 | suspicious | 1 |
| R-SEQ-01 | suspicious | 1 |
| R-TIME-01 | error | 2 |
| R-TIME-02 | review | 2 |

## 4. 门槛断言（plan/05 §2 M4 行）

| 门槛 | 要求 | 实测 | 结果 |
|---|---|---|---|
| 解析宏平均 F1 | >= 0.9500 | 1.0000 | 通过 |
| 检出率 | = 100% | 100.00% | 通过 |
| 误报率 | = 0% | 0.00% | 通过 |
| 判定准确率 | = 100% | 100.00% | 通过 |
| 冻结数据解析失败 | = 0 | 0 | 通过 |
| 未知号码告警 | = 0 | 0 | 通过 |
| 批次锚点覆盖（禁墙钟兜底） | 全部 | 3/3 | 通过 |

全部门槛通过。

## 5. 复现

```bash
py -m invoice_ledger_checker generate --out data --seed 42 --n 60   # 冻结数据重建（位级一致）
py -m invoice_ledger_checker benchmark                              # 本报告一键重跑
py -m pytest                                                      # 测试形态基准同源回归
```

> 回归纪律：改数据/改规则/改接口后必须重跑本基准确认不回退（门槛未达退出码 1）。
