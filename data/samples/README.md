# data/samples/ 格式参考样例

> 本目录存放格式参考样例与模板说明。所有样例均为**程序合成虚构数据**
>（与 data/invoices 同一生成器产出，来源登记见 data/README.md），不含任何
> 真实主体。官方样例（数电票 XML 数据规范/官方票样）尚未获取，获取后按
> data/README.md 纪律追加登记。

## 文件

| 文件 | 内容 | 来源/许可 |
|---|---|---|
| [08100000000010000237.xml](08100000000010000237.xml) | 数电票 XML 数据电文样例（synthetic-v1 模板） | 本仓生成器 `generate --seed 42 --n 60` 产物抽样，自制 |
| [TEMPLATE_REFERENCE.md](TEMPLATE_REFERENCE.md) | 三格式（XML/PDF/OFD）的版式与字段映射说明 | 自制文档 |

## 模板即权威映射（plan/04 §2.1 口径）

M1 阶段生成器模板（`generator/synthetic.py`）即解析字段映射的权威出处：
M2 解析器按 TEMPLATE_REFERENCE.md 的字段映射实现；官方样例获取后追加第二套
映射并标注"待核对"，不推翻第一套。
