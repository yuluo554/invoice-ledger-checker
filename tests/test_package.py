"""包级冒烟：版本、全部模块可导入（stdlib-only，不依赖任何 extras）。"""

import importlib

import invoice_ledger_checker

ALL_MODULES = [
    "invoice_ledger_checker.cli",
    "invoice_ledger_checker.utils",
    "invoice_ledger_checker.models",
    "invoice_ledger_checker.parsing",
    "invoice_ledger_checker.parsing.base",
    "invoice_ledger_checker.parsing.xml_parser",
    "invoice_ledger_checker.parsing.pdf_parser",
    "invoice_ledger_checker.parsing.ofd_parser",
    "invoice_ledger_checker.storage",
    "invoice_ledger_checker.storage.ledger",
    "invoice_ledger_checker.rules",
    "invoice_ledger_checker.rules.engine",
    "invoice_ledger_checker.rules.checks.arithmetic",
    "invoice_ledger_checker.rules.checks.duplicate",
    "invoice_ledger_checker.generator",
    "invoice_ledger_checker.export",
    "invoice_ledger_checker.app",
]


def test_version():
    assert invoice_ledger_checker.__version__ == "0.1.0"


def test_all_modules_importable():
    for module_name in ALL_MODULES:
        assert importlib.import_module(module_name) is not None, module_name


def test_main_entry_exists():
    from invoice_ledger_checker.cli import main

    assert callable(main)
