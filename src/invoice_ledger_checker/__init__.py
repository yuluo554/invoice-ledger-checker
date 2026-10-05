"""电子发票智能台账与重复报销检测桌面应用。

全离线流水线：数电票 XML/版式 PDF 解析 -> 发票参数卡 -> SQLite 本地台账
-> 规则引擎异常检测（重复报销/连号拆分/时间逻辑/票面算术）-> Excel 导出。

核心逻辑只依赖标准库；重量级库（pdfplumber/PySide6/openpyxl/reportlab）
全部进 pyproject extras 并经 utils.import_optional 惰性导入。
设计契约权威出处：plan/04-模块详设.md。
"""

__version__ = "0.1.0"
