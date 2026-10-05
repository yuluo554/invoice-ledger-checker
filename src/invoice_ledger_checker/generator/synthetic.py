"""合成发票生成器：固定 seed 可复现 + 程序化植入已知异常 + 真值 JSON（M1 交付）。

设计契约权威出处：plan/05-数据计划与里程碑.md §1。M1 定稿时本模块注释
即真值语义的权威定义，要点预告：

- 可复现：random.Random(seed) 显式实例（禁全局 random）；同一 seed+参数
  输出逐字节一致（守门测试断言；.gitattributes eol=lf 防 CRLF 漂移）；
- 发票类型模板：数电普票/数电专票/电子普票/纸质专票/纸质普票；
- 注入异常清单（INJ-DUP-EXACT/INJ-DUP-JOINT/INJ-DUP-FUZZY/INJ-SEQ/
  INJ-ARITH-SUM/INJ-ARITH-CN/INJ-TIME-FUTURE/INJ-TIME-STALE/
  INJ-FIELD-MISS）与 expect/also_expect 语义一一对应 plan/05 §1.3；
- 虚构纪律：公司名/税号/号码全虚构；税号用假格式统一社会信用代码并在
  数据台账登记白名单，不指向真实主体。
"""

from typing import Any, Dict


def generate(out_dir: str, seed: int = 42, n: int = 60, anomaly_rate: float = 0.35) -> Dict[str, Any]:
    """生成合成发票文件 + 真值 JSON 到 out_dir。M1 交付。"""
    raise NotImplementedError(
        "合成发票生成器属 M1 交付（plan/05 §1）；骨架未实现。"
    )
