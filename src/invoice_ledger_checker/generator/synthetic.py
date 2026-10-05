"""合成发票生成器：固定 seed 可复现 + 程序化植入已知异常 + 真值 JSON（M1 交付）。

设计契约权威出处：plan/05-数据计划与里程碑.md §1、plan/04-模块详设.md §5。
按 plan/04 §5 授权，本模块注释是**真值语义的权威定义**；M3 规则实现与
M4 基准对账以本节为准，改动须先改这里并回填 plan/05 §1.3。

==========================================================================
真值语义（权威定稿，2026-10-05）
==========================================================================

1. 产物与键形态
   - data/invoices/<batch_id>/<发票号码>.<xml|pdf|ofd>
     批次 = 目录名；同一发票号码可有 2 份文件（INJ-DUP-EXACT/JOINT 的
     跨批次副本），除此之外号码全局唯一。
   - data/ground_truth/cards.json：**按文件相对路径（正斜杠）为键**的
     "完美解析器"期望卡（InvoiceCard.to_dict 形态）。一文件一解析期望——
     同号副本的两份文件各有一条（EXACT 副本内容相同、JOINT 副本内容不同）。
     evidence/confidence/field_flags/batch_id 不参与基准对账（解析层自由度）。
   - data/ground_truth/expectations.json：**按发票号码为键**：
     {injection, expect: {rule_id: level}, also_expect: {...},
      missing_fields: [...], files: [...]}。expect=注入事件主期望异常；
     also_expect=同一注入隐含触发的其他规则；两者并集即该号码应有的
     **全部非 pass 集合**。
   - data/ground_truth/manifest.json：seed/n/anomaly_rate/formats、批次定义
     （batch_id -> expense_anchor 报销基准日）、文件清单（相对路径 ->
     号码/格式/批次/注入码）。全部路径为相对路径（跨平台可复现 + 防隐私）。

2. 对账语义（防"只验主期望"假绿）
   - 字段解析基准（M4）：真值卡 dict vs 解析卡 dict **字段级**对账
     （items 展开为 items[i].field）；INJ-FIELD-MISS 缺失字段真值为空串，
     解析器产出其他值即计误报。
   - 异常检测基准（M4）：引擎 Finding 按 (发票号码, rule_id) 对账，
     expect ∪ also_expect 为应有集合——多记=误报、少记=漏报、级别不符=错判。

3. 注入码 -> 期望（与 plan/05 §1.3 一一对应；实现以本表为权威，
   常量见 INJECTION_EXPECTATIONS，测试直接导入对拍）
   - INJ-DUP-EXACT   同号文件逐字节复制到另一批次：expect R-DUP-01=error。
                     R-DUP-02 不触发（语义见下 §4 第 1 条）。
   - INJ-DUP-JOINT   同号+同价税合计+同开票日期、购方与备注不同的"再制票"
                     跨批次副本：expect R-DUP-02=error，
                     also_expect R-DUP-01=error（同号必先触发精确判重）。
   - INJ-DUP-FUZZY   同销售方、开票日期差 1 天、价税合计完全相等、号码不同：
                     两张号码各 expect R-DUP-03=suspicious。
   - INJ-SEQ         同销售方 4-5 张同类型连号（后缀 +1 递增）、日期跨度
                     ≤7 天：簇内每张 expect R-SEQ-01=suspicious。
   - INJ-ARITH-SUM   篡改价税合计：数字与大写**同步**改为一致的错误值
                     （R-ARITH-02 保持通过，单触发 R-ARITH-01=error）。
   - INJ-ARITH-CN    仅改大写金额（数字合计不变）：expect R-ARITH-02=error。
   - INJ-TIME-FUTURE 开票日期晚于批次 expense_anchor 180-540 天：
                     expect R-TIME-01=error。
   - INJ-TIME-STALE  开票日期早于批次 expense_anchor ≥180 天（>3 期）：
                     expect R-TIME-02=review。
   - INJ-FIELD-MISS  缺失 1-2 个非关键字段（remark/buyer_name/buyer_tax_id/
                     末行明细税率）：无规则期望；missing_fields 登记缺失
                     字段名，真值卡对应字段为空串。
   - BASELINE        无注入：expect={} also_expect={}。

4. 规则语义补注（M3 实现按此对齐；出入处已回填 plan/04 §3 / plan/05 §1.3）
   - R-DUP-02 定稿语义：联合键 (号码, 价税合计, 开票日期) 跨批次相同，
     **且两卡并非字段完全一致的纯复制件**——纯复制件由 R-DUP-01 完整覆盖
     （plan/05 §1.3 INJ-DUP-EXACT 行 also_expect="—" 即此义），R-DUP-02
     专指"同键不同内容"的再制票。
   - R-DUP-03 的"金额"= 价税合计 total_with_tax；排除 R-DUP-01/02 已命中
     组合（plan/04 §3 既有口径）——同号副本同销售方同日同额但不触发。
   - R-TIME-01/02 的时间基准：基准通路取批次 expense_anchor（manifest
     固化，与墙钟无关——这是 seed 可复现的前提）；实际使用时为导入时刻。
     基线日期窗口（anchor-55 天内）与 STALE（≥180 天）由生成器保证互不串扰。
   - R-SEQ-01 按 8 位后缀连续判定；生成器保证基线号码后缀间隔 ≥2，
     连号簇仅由 INJ-SEQ 产生。

5. 可复现纪律（守门测试断言）
   - 唯一随机源 random.Random(seed)；禁全局 random / 时间 / 路径熵源；
   - 输出逐字节一致：XML 手工模板；OFD zip 固定成员时间戳与 create_system；
     PDF reportlab invariant=1 + UnicodeCIDFont（不嵌字体文件）；
   - 文本输出一律 UTF-8 + LF（.gitattributes eol=lf；EOL 门测试断言冻结
     数据无 CR）。

6. 虚构纪律（脱敏审查白名单）
   - 公司名/品名来自内置虚构词库；统一社会信用代码为 18 位假格式
     "91 + 4 位地区码 + FAKE + 8 位数字"（含 FAKE 字样自证合成，不指向
     真实主体）；发票号码 20 位 = 12 位虚构类型前缀 + 8 位后缀；
   - anomaly_rate 语义 = 注入事件涉及的文件数 / 总文件数（round 取整）。
"""

import copy
import hashlib
import io
import json
import os
import random
import zipfile
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

from ..cn_amount import encode_amount
from ..models import InvoiceCard, LineItem
from ..utils import import_optional

# ---------------------------------------------------------------- 虚构词库

FICTIONAL_COMPANIES = (
    "星辰科技", "云图商贸", "山海实业", "青竹文化传媒", "远航物流",
    "光年信息技术", "望舒餐饮", "临江建材", "北斗精密仪器", "白泽咨询",
    "梧桐服饰", "拾光摄影", "青云软件", "恒岳建筑工程", "南风电气",
    "九州测绘", "墨白设计", "砚台文教用品", "若水环保科技", "初阳新能源",
    "兰台档案服务", "牧野农业开发", "长风医疗器械", "听雨茶业",
    "照夜照明工程", "知行教育培训", "峻岭矿业", "澄江水务",
)
COMPANY_SUFFIXES = ("有限公司", "股份有限公司")

ITEM_NAMES = (
    "信息技术服务费", "咨询服务费", "会议服务费", "培训服务费", "运输服务费",
    "仓储服务费", "装卸搬运费", "广告服务费", "办公用品", "办公耗材",
    "检测服务费", "设备维修费", "场地租赁费", "软件维护费", "系统集成费",
    "差旅服务费", "劳务费", "设计服务费", "印刷费", "物业管理费",
    "水电费", "加工费", "委托研发费", "数据服务费", "云服务费",
    "安保服务费", "绿化养护费", "审计费",
)

REMARK_TEMPLATES = (
    "合同编号 HT-%06d",
    "项目第 %03d 期结算",
    "差旅报销（第 %03d 批）",
    "办公用品采购 %03d",
    "服务费 %03d 号结算单",
)

# ---------------------------------------------------------------- 类型与格式

INVOICE_TYPES = ("数电普票", "数电专票", "电子普票", "纸质专票", "纸质普票")
TYPE_WEIGHTS = {
    "数电普票": 0.30, "数电专票": 0.25, "电子普票": 0.20,
    "纸质专票": 0.15, "纸质普票": 0.10,
}
# 12 位号码前缀为虚构排版（不对应真实发票代码规则），见模块注释 §6
TYPE_PREFIX = {
    "数电普票": "259100000000", "数电专票": "269100000000",
    "电子普票": "144100000000", "纸质专票": "081000000000",
    "纸质普票": "082000000000",
}
TYPE_PDF_TITLE = {
    "数电普票": "电子发票（普通发票）", "数电专票": "电子发票（增值税专用发票）",
    "电子普票": "增值税电子普通发票", "纸质专票": "增值税专用发票",
    "纸质普票": "增值税普通发票",
}
TAX_RATES = ("0.01", "0.03", "0.06", "0.09", "0.13")
REGION_CODES = ("1101", "3101", "3301", "4403", "5101", "4201")

# ---------------------------------------------------------------- 批次定义
# expense_anchor = 报销基准日（R-TIME-01/02 基准通路的时间锚，见模块注释 §4）

BATCHES = (
    ("batch_01", "2026-07-15"),
    ("batch_02", "2026-08-15"),
    ("batch_03", "2026-09-15"),
)

# ---------------------------------------------------------------- 注入定义

# 每类注入一事件的文件数（SEQ 一簇 4 张，可扩到 5）
EVENT_UNITS = {
    "INJ-DUP-EXACT": 2, "INJ-DUP-JOINT": 2, "INJ-DUP-FUZZY": 2, "INJ-SEQ": 4,
    "INJ-ARITH-SUM": 2, "INJ-ARITH-CN": 2, "INJ-TIME-FUTURE": 2,
    "INJ-TIME-STALE": 2, "INJ-FIELD-MISS": 2,
}
# INJ-DUP-EXACT 的 R-DUP-02 排除、JOINT 的同号隐含触发，见模块注释 §3/§4
INJECTION_EXPECTATIONS = {
    "INJ-DUP-EXACT": ({"R-DUP-01": "error"}, {}),
    "INJ-DUP-JOINT": ({"R-DUP-02": "error"}, {"R-DUP-01": "error"}),
    "INJ-DUP-FUZZY": ({"R-DUP-03": "suspicious"}, {}),
    "INJ-SEQ": ({"R-SEQ-01": "suspicious"}, {}),
    "INJ-ARITH-SUM": ({"R-ARITH-01": "error"}, {}),
    "INJ-ARITH-CN": ({"R-ARITH-02": "error"}, {}),
    "INJ-TIME-FUTURE": ({"R-TIME-01": "error"}, {}),
    "INJ-TIME-STALE": ({"R-TIME-02": "review"}, {}),
    "INJ-FIELD-MISS": ({}, {}),
    "BASELINE": ({}, {}),
}
# FIELD-MISS 候选字段；末行明细税率用专用键登记
MISSING_ITEM_TAX_RATE = "items[-1].tax_rate"
MISSING_FIELD_CHOICES = ("remark", "buyer_name", "buyer_tax_id", MISSING_ITEM_TAX_RATE)

SEQ_CLUSTER_MIN, SEQ_CLUSTER_MAX = 4, 5
SEQ_SUFFIX_LEN = 8

# ---------------------------------------------------------------- 分配器


def allocate_events(n: int, anomaly_rate: float) -> Tuple[Dict[str, int], int]:
    """确定性分配注入事件：返回 ({注入码: 事件数}, SEQ 簇成员数)。

    anomaly_rate 语义 = 注入文件数 / 总文件数（round 取整）。余量按
    EVENT_UNITS 固定顺序补整事件（游标只前进、不回头重复吃满）；余 1 时
    优先扩 SEQ 簇（4->5）；仍放不下的余量归还基线（manifest 如实记录）。
    """
    target = int(round(n * anomaly_rate))
    target = max(0, min(n, target))
    counts = {code: 0 for code in EVENT_UNITS}
    unit_total = sum(EVENT_UNITS.values())
    full, rest = divmod(target, unit_total)
    for code in counts:
        counts[code] += full
    seq_members = SEQ_CLUSTER_MIN
    order = list(EVENT_UNITS.items())
    pos = 0
    while rest > 0:
        if rest == 1 and counts["INJ-SEQ"] > 0 and seq_members < SEQ_CLUSTER_MAX:
            seq_members += 1  # 扩簇消化 1 文件余量
            break
        placed = False
        while pos < len(order):
            code, unit = order[pos]
            if unit <= rest:
                counts[code] += 1
                rest -= unit
                pos += 1
                placed = True
                break
            pos += 1
        if not placed:
            break  # 余量不足以成事件 -> 归还基线
    return counts, seq_members


# ---------------------------------------------------------------- 构建状态


@dataclass
class _Entry:
    """一份发票文件的生成中间态（最终写出为文件 + 真值各一条）。"""

    card: InvoiceCard
    code: str                      # 注入码或 "BASELINE"
    batch_id: str = ""
    fmt: str = "xml"
    rel_path: str = ""             # 相对 out_dir 的正斜杠路径（真值键）
    missing_fields: List[str] = field(default_factory=list)
    is_copy: bool = False
    copy_of_path: str = ""         # 副本指向原件相对路径（EXACT 要求字节级一致）
    event_key: str = ""            # 事件标识（FUZZY/SEQ 成员归组用）
    member_idx: int = 0


class _Factory:
    """受 rng 驱动的号码/金额/主体工厂：全部随机性经显式 Random 实例。"""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self._suffix = 10000101          # 8 位后缀计数：普通号码间隔 >=2（防伪连号）
        self._used_totals = set()        # 价税合计（分）全局唯一，除注入要求的相等
        pool = list(FICTIONAL_COMPANIES)
        rng.shuffle(pool)
        self._pool = pool                # 基线主体池（可复用）
        self._exclusive = pool.pop()     # 事件专属销售方从池尾取（与基线隔离）

    # -- 号码 ------------------------------------------------------------
    def next_number(self, invoice_type: str) -> str:
        self._suffix += self.rng.randint(2, 9)
        return TYPE_PREFIX[invoice_type] + ("%0" + str(SEQ_SUFFIX_LEN) + "d") % self._suffix

    def next_cluster(self, invoice_type: str, size: int) -> List[str]:
        """连号簇：size 个后缀 +1 递增的号码（唯一允许间隔 1 的场景）。"""
        start = self._suffix + 1
        self._suffix = start + size - 1
        prefix = TYPE_PREFIX[invoice_type]
        return [prefix + ("%0" + str(SEQ_SUFFIX_LEN) + "d") % (start + i) for i in range(size)]

    # -- 主体 ------------------------------------------------------------
    def tax_id(self) -> str:
        rng = self.rng
        body = "".join(str(rng.randrange(10)) for _ in range(8))
        return "91" + rng.choice(REGION_CODES) + "FAKE" + body

    def company(self) -> Tuple[str, str]:
        name = self.rng.choice(self._pool) + self.rng.choice(COMPANY_SUFFIXES)
        return name, self.tax_id()

    def exclusive_seller(self) -> Tuple[str, str]:
        name = self._exclusive + self.rng.choice(COMPANY_SUFFIXES)
        return name, self.tax_id()

    # -- 金额与明细 --------------------------------------------------------
    def amount_block(self) -> Tuple[List[LineItem], int, int, int]:
        """明细 1-5 行：行金额精确到分、行税额=行金额×税率（四舍五入到分）。

        返回 (items, 合计金额分, 合计税额分, 价税合计分)；价税合计全局唯一。
        """
        rng = self.rng
        while True:
            amount_cents = rng.randrange(50_000, 10_000_000)  # 500.00 ~ 99999.99 元
            n_lines = rng.randint(1, 5)
            if n_lines == 1:
                cuts = []
            else:
                cuts = sorted(rng.sample(range(100, amount_cents - 100), n_lines - 1))
            pieces, prev = [], 0
            for cut in cuts + [amount_cents]:
                pieces.append(cut - prev)
                prev = cut
            items, tax_sum = [], 0
            for piece in pieces:
                rate = rng.choice(TAX_RATES)
                tax_cents = int(
                    (Decimal(piece) * Decimal(rate)).quantize(Decimal("1"), ROUND_HALF_UP)
                )
                tax_sum += tax_cents
                items.append(LineItem(
                    name=rng.choice(ITEM_NAMES),
                    amount=_fmt_cents(piece),
                    tax_rate=rate,
                    tax_amount=_fmt_cents(tax_cents),
                ))
            total_cents = amount_cents + tax_sum
            if total_cents not in self._used_totals:
                self._used_totals.add(total_cents)
                return items, amount_cents, tax_sum, total_cents

    def reserve_total(self, total_cents: int) -> bool:
        """注入产生的派生合计纳入全局唯一集（防串扰触发判重）；占用返回 False。"""
        if total_cents in self._used_totals:
            return False
        self._used_totals.add(total_cents)
        return True

    # -- 其他 --------------------------------------------------------------
    def remark(self) -> str:
        if self.rng.random() < 0.3:
            return ""
        return self.rng.choice(REMARK_TEMPLATES) % self.rng.randrange(1000)


def _fmt_cents(cents: int) -> str:
    return "%d.%02d" % divmod(cents, 100)


def _shift_days(anchor: date, days: int) -> str:
    return (anchor + timedelta(days=days)).isoformat()


def _weighted_type(rng: random.Random) -> str:
    x = rng.random()
    cum = 0.0
    for invoice_type in INVOICE_TYPES:
        cum += TYPE_WEIGHTS[invoice_type]
        if x < cum:
            return invoice_type
    return INVOICE_TYPES[-1]


# ---------------------------------------------------------------- 卡片构建


def _base_card(factory: _Factory, issue_date: str = "") -> InvoiceCard:
    rng = factory.rng
    invoice_type = _weighted_type(rng)
    items, amount_c, tax_c, total_c = factory.amount_block()
    seller_name, seller_tax = factory.company()
    while True:
        buyer_name, buyer_tax = factory.company()
        if buyer_name != seller_name:
            break
    return InvoiceCard(
        invoice_number=factory.next_number(invoice_type),
        invoice_type=invoice_type,
        issue_date=issue_date,
        buyer_name=buyer_name,
        buyer_tax_id=buyer_tax,
        seller_name=seller_name,
        seller_tax_id=seller_tax,
        items=items,
        amount=_fmt_cents(amount_c),
        tax_amount=_fmt_cents(tax_c),
        total_with_tax=_fmt_cents(total_c),
        total_with_tax_cn=encode_amount(_fmt_cents(total_c)),
        remark=factory.remark(),
    )


def _pick_missing_fields(rng: random.Random) -> List[str]:
    return sorted(rng.sample(MISSING_FIELD_CHOICES, rng.randint(1, 2)))


def _apply_missing_fields(card: InvoiceCard, missing: List[str]) -> None:
    """把缺失字段从卡上抹为空串（真值卡与文件缺省一致，防解析器造值）。"""
    if "remark" in missing:
        card.remark = ""
    if "buyer_name" in missing:
        card.buyer_name = ""
    if "buyer_tax_id" in missing:
        card.buyer_tax_id = ""
    if MISSING_ITEM_TAX_RATE in missing and card.items:
        card.items[-1].tax_rate = ""


def _build_events(alloc: Dict[str, int], seq_members: int,
                  factory: _Factory) -> List[_Entry]:
    """按固定码序构建注入事件；日期留空（批次分配后统一填充）。"""
    rng = factory.rng
    entries: List[_Entry] = []
    for code, event_count in alloc.items():
        for event_no in range(event_count):
            event_key = "%s#%d" % (code, event_no)
            if code == "INJ-DUP-EXACT":
                original = _Entry(card=_base_card(factory), code=code, event_key=event_key)
                duplicate = _Entry(card=copy.deepcopy(original.card), code=code,
                                   is_copy=True, event_key=event_key)
                entries.extend([original, duplicate])
            elif code == "INJ-DUP-JOINT":
                original = _Entry(card=_base_card(factory), code=code, event_key=event_key)
                twin = copy.deepcopy(original.card)
                while True:  # 再制票：购方换成另一虚构主体（联合键之外的内容差异）
                    twin.buyer_name, twin.buyer_tax_id = factory.company()
                    if twin.buyer_name != original.card.buyer_name:
                        break
                twin.remark = factory.remark()
                entries.extend([
                    original,
                    _Entry(card=twin, code=code, is_copy=True, event_key=event_key),
                ])
            elif code == "INJ-DUP-FUZZY":
                seller_name, seller_tax = factory.exclusive_seller()
                first = _base_card(factory)
                first.seller_name, first.seller_tax_id = seller_name, seller_tax
                if first.buyer_name == first.seller_name:
                    first.buyer_name, first.buyer_tax_id = factory.company()
                near = copy.deepcopy(first)  # 同销售方同额近似票：换号/换日/换一个品名
                near.invoice_number = factory.next_number(near.invoice_type)
                old_name = near.items[0].name
                near.items[0].name = rng.choice(
                    [name for name in ITEM_NAMES if name != old_name])
                near.remark = factory.remark()
                entries.extend([
                    _Entry(card=first, code=code, event_key=event_key, member_idx=0),
                    _Entry(card=near, code=code, event_key=event_key, member_idx=1),
                ])
            elif code == "INJ-SEQ":
                invoice_type = _weighted_type(rng)
                seller_name, seller_tax = factory.exclusive_seller()
                numbers = factory.next_cluster(invoice_type, seq_members)
                for idx, number in enumerate(numbers):
                    card = _base_card(factory)
                    card.invoice_number = number
                    card.invoice_type = invoice_type
                    card.seller_name, card.seller_tax_id = seller_name, seller_tax
                    if card.buyer_name == card.seller_name:
                        card.buyer_name, card.buyer_tax_id = factory.company()
                    entries.append(_Entry(card=card, code=code, event_key=event_key,
                                          member_idx=idx))
            elif code == "INJ-ARITH-SUM":
                for _ in range(EVENT_UNITS[code]):
                    card = _base_card(factory)
                    while True:  # 篡改后合计仍全局唯一（防串扰触发判重）
                        delta = rng.choice((100, 1000, 10_000, 50_000, 200_000))
                        total_cents = int(Decimal(card.total_with_tax) * 100) + delta
                        if factory.reserve_total(total_cents):
                            break
                    card.total_with_tax = _fmt_cents(total_cents)
                    # 数字与大写同步改错：R-ARITH-02 保持通过（模块注释 §3）
                    card.total_with_tax_cn = encode_amount(card.total_with_tax)
                    entries.append(_Entry(card=card, code=code, event_key=event_key))
            elif code == "INJ-ARITH-CN":
                for _ in range(EVENT_UNITS[code]):
                    card = _base_card(factory)
                    delta = rng.choice((100, 200, 500))
                    cn_total = int(Decimal(card.total_with_tax) * 100) + delta
                    card.total_with_tax_cn = encode_amount(_fmt_cents(cn_total))
                    entries.append(_Entry(card=card, code=code, event_key=event_key))
            elif code == "INJ-TIME-FUTURE" or code == "INJ-TIME-STALE":
                for _ in range(EVENT_UNITS[code]):
                    entries.append(_Entry(card=_base_card(factory), code=code,
                                          event_key=event_key))
            elif code == "INJ-FIELD-MISS":
                for _ in range(EVENT_UNITS[code]):
                    card = _base_card(factory)
                    missing = _pick_missing_fields(rng)
                    _apply_missing_fields(card, missing)
                    entries.append(_Entry(card=card, code=code, event_key=event_key,
                                          missing_fields=list(missing)))
            else:
                raise AssertionError("未知注入码: %s" % code)
    return entries


def _build_dataset(rng: random.Random, n: int, anomaly_rate: float) -> List[_Entry]:
    """构建全部文件条目：注入事件 + 基线 + 批次分配 + 日期填充。"""
    factory = _Factory(rng)
    alloc, seq_members = allocate_events(n, anomaly_rate)
    entries = _build_events(alloc, seq_members, factory)
    if len(entries) > n:
        raise AssertionError("注入文件数 %d 超过 n=%d" % (len(entries), n))
    while len(entries) < n:
        entries.append(_Entry(card=_base_card(factory), code="BASELINE"))

    # 批次分配：事件成员同批（日期窗口依赖同一 anchor）；副本强制跨批次
    # （R-DUP-01/02 前提）；基线逐张轮转
    batch_of = {batch_id: date.fromisoformat(anchor) for batch_id, anchor in BATCHES}
    batch_ids = [batch_id for batch_id, _ in BATCHES]
    cursor = 0
    placed: List[_Entry] = []
    event_batch: Dict[str, str] = {}
    for entry in entries:
        if entry.is_copy:
            original = placed[[e.event_key for e in placed].index(entry.event_key)]
            batch_id = batch_ids[(batch_ids.index(original.batch_id) + 1) % len(batch_ids)]
        elif entry.event_key:
            if entry.event_key not in event_batch:
                event_batch[entry.event_key] = batch_ids[cursor % len(batch_ids)]
                cursor += 1
            batch_id = event_batch[entry.event_key]
        else:
            batch_id = batch_ids[cursor % len(batch_ids)]
            cursor += 1
        entry.batch_id = batch_id
        placed.append(entry)

    # 日期填充（列表序消费 rng；副本继承原件日期，不再抽签）
    seq_dates: Dict[str, List[int]] = {}
    for entry in placed:
        anchor = batch_of[entry.batch_id]
        code = entry.code
        if entry.is_copy:
            original = placed[[e.event_key for e in placed].index(entry.event_key)]
            entry.card.issue_date = original.card.issue_date
            continue
        if code == "INJ-TIME-FUTURE":
            entry.card.issue_date = _shift_days(anchor, rng.randint(180, 540))
        elif code == "INJ-TIME-STALE":
            entry.card.issue_date = _shift_days(anchor, -rng.randint(180, 720))
        elif code == "INJ-DUP-FUZZY":
            if entry.member_idx == 0:
                base = -rng.randint(10, 55)
                seq_dates[entry.event_key] = [base]
                entry.card.issue_date = _shift_days(anchor, base)
            else:
                base = seq_dates[entry.event_key][0]
                entry.card.issue_date = _shift_days(anchor, base + rng.choice((-1, 1)))
        elif code == "INJ-SEQ":
            if entry.member_idx == 0:
                base = -rng.randint(10, 45)
                offsets = sorted(rng.choices(range(0, 8), k=len(
                    [e for e in placed if e.event_key == entry.event_key])))
                seq_dates[entry.event_key] = [base] + offsets
                entry.card.issue_date = _shift_days(anchor, base + offsets[0])
            else:
                base = seq_dates[entry.event_key][0]
                offset = seq_dates[entry.event_key][1 + entry.member_idx]
                entry.card.issue_date = _shift_days(anchor, base + offset)
        else:  # BASELINE / ARITH-SUM / ARITH-CN / FIELD-MISS / DUP 原件
            entry.card.issue_date = _shift_days(anchor, -rng.randint(1, 55))
    return placed


# ---------------------------------------------------------------- 版式文本行


def _invoice_lines(card: InvoiceCard, missing: List[str]) -> Dict[str, Any]:
    """版式行（PDF/OFD 共用文本语义）：头字段/明细行/汇总行。"""
    has = lambda f: f not in missing
    header = [("发票号码", card.invoice_number), ("开票日期", card.issue_date)]
    if has("buyer_name"):
        header.append(("购买方名称", card.buyer_name))
    if has("buyer_tax_id"):
        header.append(("购买方税号", card.buyer_tax_id))
    header.append(("销售方名称", card.seller_name))
    header.append(("销售方税号", card.seller_tax_id))
    items = []
    for idx, item in enumerate(card.items):
        rate = "" if (idx == len(card.items) - 1 and MISSING_ITEM_TAX_RATE in missing) \
            else item.tax_rate
        items.append((item.name, item.amount, rate, item.tax_amount))
    footer = [
        ("合计金额", card.amount), ("合计税额", card.tax_amount),
        ("价税合计（大写）", card.total_with_tax_cn),
        ("价税合计（小写）", "￥" + card.total_with_tax),
    ]
    if has("remark") and card.remark:
        footer.append(("备注", card.remark))
    return {"header": header, "items": items, "footer": footer}


# ---------------------------------------------------------------- 发射器


def _emit_xml(card: InvoiceCard, missing: List[str]) -> bytes:
    """数电票风格 XML 数据电文（synthetic-v1 模板即 M2 权威字段映射）。"""
    has = lambda f: f not in missing
    item_blocks = []
    for idx, item in enumerate(card.items):
        last = idx == len(card.items) - 1
        rate_line = "" if (last and MISSING_ITEM_TAX_RATE in missing) \
            else "        <TaxRate>%s</TaxRate>\n" % escape(item.tax_rate)
        item_blocks.append(
            "      <Item>\n"
            "        <Name>%s</Name>\n"
            "        <Amount>%s</Amount>\n"
            "%s"
            "        <TaxAmount>%s</TaxAmount>\n"
            "      </Item>\n" % (escape(item.name), escape(item.amount),
                                 rate_line, escape(item.tax_amount))
        )
    buyer_lines = ""
    if has("buyer_name"):
        buyer_lines += "      <Name>%s</Name>\n" % escape(card.buyer_name)
    if has("buyer_tax_id"):
        buyer_lines += "      <TaxId>%s</TaxId>\n" % escape(card.buyer_tax_id)
    buyer_block = "    <Buyer />\n" if not buyer_lines \
        else "    <Buyer>\n%s    </Buyer>\n" % buyer_lines
    remark_line = "" if (not card.remark or not has("remark")) \
        else "    <Remark>%s</Remark>\n" % escape(card.remark)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- 合成测试数据：invoice-ledger-checker synthetic-v1，"
        "公司/税号/号码全虚构，与任何真实主体无关 -->\n"
        '<ElectronicInvoice version="synthetic-v1">\n'
        "  <InvoiceHeader>\n"
        "    <InvoiceNumber>%s</InvoiceNumber>\n"
        "    <InvoiceType>%s</InvoiceType>\n"
        "    <IssueDate>%s</IssueDate>\n"
        "%s"
        "    <Seller>\n"
        "      <Name>%s</Name>\n"
        "      <TaxId>%s</TaxId>\n"
        "    </Seller>\n"
        "    <Items>\n%s    </Items>\n"
        "    <AmountWithoutTax>%s</AmountWithoutTax>\n"
        "    <TaxAmount>%s</TaxAmount>\n"
        "    <TotalWithTax>%s</TotalWithTax>\n"
        "    <TotalWithTaxCN>%s</TotalWithTaxCN>\n"
        "%s"
        "  </InvoiceHeader>\n"
        "</ElectronicInvoice>\n"
    ) % (
        escape(card.invoice_number), escape(card.invoice_type), escape(card.issue_date),
        buyer_block,
        escape(card.seller_name), escape(card.seller_tax_id),
        "".join(item_blocks),
        escape(card.amount), escape(card.tax_amount),
        escape(card.total_with_tax), escape(card.total_with_tax_cn),
        remark_line,
    )
    return xml.encode("utf-8")


_PDF_FONT_READY = False


def _emit_pdf(card: InvoiceCard, missing: List[str]) -> bytes:
    """版式 PDF（reportlab invariant=1 保证逐字节可复现；文本层供 M2 抽取）。"""
    import_optional("reportlab", "data")
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen.canvas import Canvas

    global _PDF_FONT_READY
    if not _PDF_FONT_READY:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        _PDF_FONT_READY = True

    lines = _invoice_lines(card, missing)
    buf = io.BytesIO()
    page_w, page_h = 240 * mm, 140 * mm
    cvs = Canvas(buf, pagesize=(page_w, page_h), invariant=1)
    cvs.setTitle(TYPE_PDF_TITLE[card.invoice_type])
    cvs.setFont("STSong-Light", 16)
    cvs.drawCentredString(page_w / 2, 128 * mm, TYPE_PDF_TITLE[card.invoice_type])
    cvs.setFont("STSong-Light", 10.5)

    def field_line(y_mm, label, value, x_mm=12, value_dx_mm=30):
        cvs.drawString(x_mm * mm, y_mm * mm, label + "：")
        cvs.drawString((x_mm + value_dx_mm) * mm, y_mm * mm, value)

    # 标签 -> 固定槽位 (y_mm, x_mm)：缺字段按标签落位，其余槽位不受影响
    header_slots = {
        "发票号码": (118, 12), "开票日期": (118, 108),
        "购买方名称": (111, 12), "购买方税号": (104, 12),
        "销售方名称": (111, 108), "销售方税号": (104, 108),
    }
    for label, value in lines["header"]:
        y_mm, x_mm = header_slots[label]
        field_line(y_mm, label, value, x_mm=x_mm)

    table_y = 92
    cvs.drawString(12 * mm, table_y * mm, "项目名称")
    cvs.drawString(110 * mm, table_y * mm, "金额")
    cvs.drawString(140 * mm, table_y * mm, "税率")
    cvs.drawString(160 * mm, table_y * mm, "税额")
    row_y = table_y - 7
    for name, amount, rate, tax in lines["items"]:
        cvs.drawString(12 * mm, row_y * mm, name)
        cvs.drawString(110 * mm, row_y * mm, amount)
        cvs.drawString(140 * mm, row_y * mm, rate)
        cvs.drawString(160 * mm, row_y * mm, tax)
        row_y -= 6

    summary_y = row_y - 4
    footer_labels = dict(lines["footer"])
    field_line(summary_y, "合计", "%s（税额 %s）"
               % (footer_labels.get("合计金额", ""), footer_labels.get("合计税额", "")))
    summary_y -= 8
    field_line(summary_y, "价税合计（大写）", footer_labels["价税合计（大写）"])
    cvs.drawString(110 * mm, summary_y * mm, "（小写）"
                   + footer_labels["价税合计（小写）"])
    summary_y -= 8
    if "备注" in footer_labels:
        field_line(summary_y, "备注", footer_labels["备注"])
    cvs.showPage()
    cvs.save()
    return buf.getvalue()


def _emit_ofd(card: InvoiceCard, missing: List[str]) -> bytes:
    """OFD（GB/T 33190 简化结构 zip，固定成员元数据保证逐字节可复现）。"""
    doc_id = hashlib.md5(card.invoice_number.encode("utf-8")).hexdigest().upper()
    lines = _invoice_lines(card, missing)

    ofd_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ofd:OFD xmlns:ofd="http://www.ofdspec.org/2016" '
        'xmlns:synthetic="urn:invoice-ledger-checker:synthetic-v1" '
        'synthetic:note="程序合成虚构发票">\n'
        "  <ofd:DocInfo>\n"
        "    <ofd:DocID>%s</ofd:DocID>\n"
        "    <ofd:Title>%s</ofd:Title>\n"
        "    <ofd:Author>invoice-ledger-checker synthetic</ofd:Author>\n"
        "  </ofd:DocInfo>\n"
        "  <ofd:DocBody>\n"
        "    <ofd:DocRoot>Doc_0/Document.xml</ofd:DocRoot>\n"
        "  </ofd:DocBody>\n"
        "</ofd:OFD>\n"
    ) % (doc_id, escape(TYPE_PDF_TITLE[card.invoice_type]))

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ofd:Document xmlns:ofd="http://www.ofdspec.org/2016">\n'
        "  <ofd:CommonData><ofd:MaxUnitID>9999</ofd:MaxUnitID></ofd:CommonData>\n"
        "  <ofd:Pages>\n"
        '    <ofd:Page ID="1" BaseLoc="Page_0/Content.xml"/>\n'
        "  </ofd:Pages>\n"
        "</ofd:Document>\n"
    )

    objects = []

    def text_object(obj_id, x, y, text, width=520):
        objects.append(
            '    <ofd:TextObject ID="%d" Boundary="%d %d %d 42">\n'
            "      <ofd:TextCode>%s</ofd:TextCode>\n"
            "    </ofd:TextObject>\n"
            % (obj_id, x, y, width, escape(text))
        )

    obj_id = 1
    title = TYPE_PDF_TITLE[card.invoice_type]
    text_object(obj_id, 800, 1240, title, width=800)
    obj_id += 1
    y = 1150
    for label, value in lines["header"]:
        text_object(obj_id, 60, y, label + "：")
        text_object(obj_id + 1, 420, y, value)
        obj_id += 2
        y -= 62
    y -= 20
    for label, x in (("项目名称", 60), ("金额", 1050), ("税率", 1350), ("税额", 1550)):
        text_object(obj_id, x, y, label)
        obj_id += 1
    y -= 62
    for name, amount, rate, tax in lines["items"]:
        for x, value in ((60, name), (1050, amount), (1350, rate), (1550, tax)):
            text_object(obj_id, x, y, value)
            obj_id += 1
        y -= 62
    y -= 20
    for label, value in lines["footer"]:
        text_object(obj_id, 60, y, label + "：")
        text_object(obj_id + 1, 420, y, value)
        obj_id += 2
        y -= 62

    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<ofd:Page xmlns:ofd="http://www.ofdspec.org/2016" '
        'xmlns:synthetic="urn:invoice-ledger-checker:synthetic-v1" '
        'synthetic:note="程序合成虚构发票" Width="2400" Height="1400">\n'
        "  <ofd:Content>\n%s  </ofd:Content>\n"
        "</ofd:Page>\n"
    ) % "".join(objects)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=8) as zf:
        for name, text in (("OFD.xml", ofd_xml),
                           ("Doc_0/Document.xml", document_xml),
                           ("Doc_0/Page_0/Content.xml", content_xml)):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


# ---------------------------------------------------------------- 不变量自检


def _verify_invariants(entries: List[_Entry]) -> None:
    """生成期大声失败：任何注入串扰/算术不一致都在此暴露（防真值被污染）。"""
    anchor_of = {batch_id: date.fromisoformat(anchor) for batch_id, anchor in BATCHES}
    by_number: Dict[str, List[_Entry]] = {}
    for entry in entries:
        by_number.setdefault(entry.card.invoice_number, []).append(entry)
        if not entry.card.issue_date:
            raise AssertionError("日期未填充: %s" % entry.card.invoice_number)

    for number, group in by_number.items():
        codes = {e.code for e in group}
        if len(group) == 2:
            if codes != {"INJ-DUP-EXACT"} and codes != {"INJ-DUP-JOINT"}:
                raise AssertionError("号码 %s 出现 2 次但注入码为 %s" % (number, codes))
            first, second = group
            if first.card.total_with_tax != second.card.total_with_tax \
                    or first.card.issue_date != second.card.issue_date:
                raise AssertionError("副本 %s 联合键与原件不一致" % number)
            if first.batch_id == second.batch_id:
                raise AssertionError("副本 %s 未跨批次" % number)
            if codes == {"INJ-DUP-EXACT"} and first.card != second.card:
                raise AssertionError("EXACT 副本与原件卡面不一致: %s" % number)
        elif len(group) != 1:
            raise AssertionError("号码 %s 出现 %d 次" % (number, len(group)))

    totals: Dict[str, List[str]] = {}
    for entry in entries:
        card = entry.card
        items_amount = sum(Decimal(i.amount) for i in card.items)
        items_tax = sum(Decimal(i.tax_amount) for i in card.items)
        if items_amount != Decimal(card.amount) or items_tax != Decimal(card.tax_amount):
            raise AssertionError("明细合计不一致: %s" % card.invoice_number)
        if entry.code == "INJ-ARITH-SUM":
            if Decimal(card.amount) + Decimal(card.tax_amount) == Decimal(card.total_with_tax):
                raise AssertionError("ARITH-SUM 未生效: %s" % card.invoice_number)
        else:
            if Decimal(card.amount) + Decimal(card.tax_amount) != Decimal(card.total_with_tax):
                raise AssertionError("价税合计不一致: %s" % card.invoice_number)
        expected_cn = encode_amount(card.total_with_tax)
        if entry.code == "INJ-ARITH-CN":
            if card.total_with_tax_cn == expected_cn:
                raise AssertionError("ARITH-CN 未生效: %s" % card.invoice_number)
        else:
            if card.total_with_tax_cn != expected_cn:
                raise AssertionError("大写金额不一致: %s" % card.invoice_number)
        totals.setdefault(card.total_with_tax, []).append(card.invoice_number)

    fuzzy_numbers = {e.card.invoice_number for e in entries if e.code == "INJ-DUP-FUZZY"}
    for total, numbers in totals.items():
        distinct = set(numbers)
        if len(distinct) > 1 and not (
                len(numbers) == 2 and distinct <= fuzzy_numbers):
            raise AssertionError("异号卡共享价税合计 %s 但无 FUZZY 事件支撑: %s"
                                 % (total, sorted(distinct)))

    for entry in entries:
        if entry.is_copy:
            continue
        card, anchor = entry.card, anchor_of[entry.batch_id]
        delta = (anchor - date.fromisoformat(card.issue_date)).days
        if entry.code == "INJ-TIME-FUTURE":
            if delta >= 0:
                raise AssertionError("FUTURE 未生效: %s" % card.invoice_number)
        elif entry.code == "INJ-TIME-STALE":
            if delta < 180:
                raise AssertionError("STALE 未生效: %s" % card.invoice_number)
        elif not 0 < delta <= 70:
            raise AssertionError("常规日期越窗: %s（delta=%d）" % (card.invoice_number, delta))

    seq_events: Dict[str, List[_Entry]] = {}
    for entry in entries:
        if entry.code == "INJ-SEQ":
            seq_events.setdefault(entry.event_key, []).append(entry)
    for event_key, members in seq_events.items():
        if len(members) < 3:
            raise AssertionError("连号簇不足 3 张: %s" % event_key)
        suffixes = [int(c.invoice_number[-SEQ_SUFFIX_LEN:]) for c in
                    (m.card for m in members)]
        if sorted(suffixes) != list(range(min(suffixes), min(suffixes) + len(suffixes))):
            raise AssertionError("连号簇后缀不连续: %s" % event_key)
        sellers = {m.card.seller_tax_id for m in members}
        if len(sellers) != 1:
            raise AssertionError("连号簇销售方不一致: %s" % event_key)
        days = sorted(m.card.issue_date for m in members)
        span = (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days
        if span > 7:
            raise AssertionError("连号簇日期跨度 >7 天: %s" % event_key)

    fuzzy_by_event: Dict[str, List[_Entry]] = {}
    for entry in entries:
        if entry.code == "INJ-DUP-FUZZY":
            fuzzy_by_event.setdefault(entry.event_key, []).append(entry)
    for event_key, pair in fuzzy_by_event.items():
        first, second = pair
        if first.card.seller_tax_id != second.card.seller_tax_id:
            raise AssertionError("FUZZY 对销售方不一致: %s" % event_key)
        if abs((date.fromisoformat(first.card.issue_date)
                - date.fromisoformat(second.card.issue_date)).days) != 1:
            raise AssertionError("FUZZY 对日期差 != 1 天: %s" % event_key)
        if first.card.total_with_tax != second.card.total_with_tax:
            raise AssertionError("FUZZY 对金额不相等: %s" % event_key)

    for entry in entries:
        card, missing = entry.card, entry.missing_fields
        if "remark" in missing and card.remark:
            raise AssertionError("missing_fields 与卡片不一致: %s" % card.invoice_number)
        if "buyer_name" in missing and card.buyer_name:
            raise AssertionError("missing_fields 与卡片不一致: %s" % card.invoice_number)
        if "buyer_tax_id" in missing and card.buyer_tax_id:
            raise AssertionError("missing_fields 与卡片不一致: %s" % card.invoice_number)
        if MISSING_ITEM_TAX_RATE in missing and card.items and card.items[-1].tax_rate:
            raise AssertionError("missing_fields 与卡片不一致: %s" % card.invoice_number)


# ---------------------------------------------------------------- 产物写出


def _write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)


def _write_json(path: str, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    _write_bytes(path, text.encode("utf-8"))


def generate(out_dir: str, seed: int = 42, n: int = 60, anomaly_rate: float = 0.35,
             formats: Optional[List[str]] = None) -> Dict[str, Any]:
    """生成合成发票文件 + 真值 JSON 到 out_dir（同参数逐字节可复现）。

    返回摘要 dict（CLI 展示/测试断言用）；产物布局见模块注释 §1。
    """
    formats = tuple(formats) if formats else ("xml", "pdf", "ofd")
    if not formats or "xml" not in formats \
            or not set(formats) <= {"xml", "pdf", "ofd"}:
        raise ValueError("formats 必须为 xml/pdf/ofd 的非空子集且包含 xml: %r" % (formats,))

    rng = random.Random(seed)
    entries = _build_dataset(rng, n, anomaly_rate)
    _verify_invariants(entries)

    # 格式指派：OFD 约 5%、PDF 约 40%、其余 XML；副本随原件格式
    desired = []
    for idx in range(len(entries)):
        if idx % 20 == 19:
            desired.append("ofd")
        elif idx % 5 in (1, 3):
            desired.append("pdf")
        else:
            desired.append("xml")
    for idx, entry in enumerate(entries):
        if entry.is_copy:
            entry.fmt = entries[idx - 1].fmt  # 副本紧跟原件（EXACT 要求同格式）
        else:
            entry.fmt = desired[idx] if desired[idx] in formats else "xml"

    invoices_root = os.path.join(out_dir, "invoices")
    truth_root = os.path.join(out_dir, "ground_truth")

    file_records = []
    number_to_files: Dict[str, List[str]] = {}
    emitted: Dict[str, bytes] = {}
    original_path_by_event: Dict[str, str] = {}
    for entry in entries:
        number = entry.card.invoice_number
        filename = "%s.%s" % (number, entry.fmt)
        rel_path = "invoices/%s/%s" % (entry.batch_id, filename)  # 正斜杠：跨平台键
        abs_path = os.path.join(invoices_root, entry.batch_id, filename)
        data = _emit_xml(entry.card, entry.missing_fields) if entry.fmt == "xml" \
            else _emit_pdf(entry.card, entry.missing_fields) if entry.fmt == "pdf" \
            else _emit_ofd(entry.card, entry.missing_fields)
        if entry.is_copy:
            entry.copy_of_path = original_path_by_event[entry.event_key]
            if entry.code == "INJ-DUP-EXACT" and emitted[entry.copy_of_path] != data:
                raise AssertionError("EXACT 副本与原件字节不一致: %s" % rel_path)
        else:
            original_path_by_event.setdefault(entry.event_key, rel_path)
        emitted[rel_path] = data
        entry.rel_path = rel_path
        _write_bytes(abs_path, data)
        file_records.append({
            "path": rel_path,
            "invoice_number": number,
            "format": entry.fmt,
            "batch_id": entry.batch_id,
            "injection": entry.code,
        })
        number_to_files.setdefault(number, []).append(rel_path)

    cards_payload = {}
    expectations_payload = {}
    for entry in entries:
        number = entry.card.invoice_number
        cards_payload[entry.rel_path] = entry.card.to_dict()
        if number not in expectations_payload:
            expect, also_expect = INJECTION_EXPECTATIONS[entry.code]
            expectations_payload[number] = {
                "injection": entry.code,
                "expect": expect,
                "also_expect": also_expect,
                "missing_fields": list(entry.missing_fields),
                "files": sorted(number_to_files[number]),
            }
        elif expectations_payload[number]["missing_fields"] != list(entry.missing_fields):
            raise AssertionError("同号文件真值冲突: %s" % number)

    batch_records = []
    for batch_id, anchor in BATCHES:
        batch_records.append({
            "batch_id": batch_id,
            "expense_anchor": anchor,
            "file_count": sum(1 for r in file_records if r["batch_id"] == batch_id),
        })
    manifest = {
        "seed": seed,
        "n": n,
        "anomaly_rate": anomaly_rate,
        "injected_files": sum(1 for e in entries if e.code != "BASELINE"),
        "formats": list(formats),
        "batches": batch_records,
        "files": file_records,
        "counts": {
            "baseline": sum(1 for e in entries if e.code == "BASELINE"),
            "by_injection": {
                code: sum(1 for e in entries if e.code == code)
                for code in sorted({e.code for e in entries} - {"BASELINE"})
            },
            "by_format": {
                fmt: sum(1 for e in entries if e.fmt == fmt)
                for fmt in sorted({e.fmt for e in entries})
            },
        },
    }

    _write_json(os.path.join(truth_root, "cards.json"), cards_payload)
    _write_json(os.path.join(truth_root, "expectations.json"), expectations_payload)
    _write_json(os.path.join(truth_root, "manifest.json"), manifest)

    return {
        "out_dir": out_dir,
        "seed": seed,
        "n": n,
        "anomaly_rate": anomaly_rate,
        "formats": list(formats),
        "files": len(file_records),
        "injected": manifest["injected_files"],
        "baseline": manifest["counts"]["baseline"],
        "by_injection": manifest["counts"]["by_injection"],
        "by_format": manifest["counts"]["by_format"],
        "batches": batch_records,
        "truth_files": ["ground_truth/cards.json", "ground_truth/expectations.json",
                        "ground_truth/manifest.json"],
    }
