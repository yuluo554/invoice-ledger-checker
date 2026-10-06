#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脱敏扫描器：发布前对"密钥/邮箱/手机号/身份证/个人目录/内网 IP"做全量排查（可复跑）。

用法（子命令）::

    python tools/sensitive_scan.py selftest   # 阳性+阴性对照：构造样本断言各类别可命中、易误报样本不命中
    python tools/sensitive_scan.py tracked    # 全部跟踪文件内容（工作树）
    python tools/sensitive_scan.py history    # 全部历史提交引入过的每一行（git log --all -p，扫描 + 行）
    python tools/sensitive_scan.py binaries   # 二进制样例本体（PDF Info 元数据域 / ZIP·OFD 逐条目解压）
    python tools/sensitive_scan.py messages   # 全部提交信息
    python tools/sensitive_scan.py metadata   # 提交作者/提交者姓名与邮箱（内容扫描覆盖不到，必须单独查）
    python tools/sensitive_scan.py all        # 五模式连跑（仓库树 release 门形态）
    python tools/sensitive_scan.py dist --dir dist --marker-b64 <b64> [...]
                                              # 构建产物本体扫描（强标记+禁区成分；
                                              # 标记以 base64 传入，字面值不入仓库）

退出码：0=无命中 / 1=有命中 / 2=环境或用法错误。

设计要点
--------
* **模式片段拼接构造**：本文件源码里不出现任何敏感字面值或完整的敏感匹配式——
  类目正则由 ``_AT`` / ``_BS`` / ``_SECRET_TOKENS`` 等片段在运行期拼出，
  否则扫描器自身会被自己的规则命中（系列纪律：工具与产物同一套口径）。
* **输出掩码化**：只报 ``来源:定位 [类别] x次数``，绝不回显命中的敏感字面值，
  便于留档与 CI 日志公开。
* **阴性对照进 selftest**：git 的 SSH 远端地址、20 位合成发票号码、``C:\\Users\\...``
  这类"文档里的模式占位"必须**不**命中——扫描器的假阳性同样是要防的回归。
"""

import base64
import io
import os
import re
import subprocess
import sys
import zipfile

# --------------------------------------------------------------------------- #
# 类目正则：片段拼接构造（本文件不留敏感字面值）
# --------------------------------------------------------------------------- #
_AT = "@"
_COLON = ":"
_BS = chr(92)                      # 反斜杠（Windows 路径分隔符）
_DOT = re.escape(".")
_USERS = "Users"
_HOME = "home"

# 二进制容器后缀：逐字节文本扫描无意义（内容由生成器源码程序化产出，源码已入扫描面）
_BINARY_EXTS = (".pdf", ".ofd", ".zip", ".png", ".jpg", ".jpeg", ".gif",
                ".webp", ".ico", ".gz", ".7z", ".exe", ".dll", ".whl")

# 产物树禁区成分：仓库数据集不得进入冻结产物（spec 的 datas 白名单为空）
_FORBIDDEN_OUTPUT_NAMES = ("cards.json", "expectations.json", "manifest.json")
_FORBIDDEN_OUTPUT_EXTS = (".pdf", ".ofd", ".xlsx")

_SECRET_TOKENS = [
    "gh" + "o_",                   # GitHub OAuth token
    "gh" + "p_",                   # GitHub personal access token
    "gh" + "s_",                   # GitHub server-to-server token
    "gh" + "u_",                   # GitHub user-to-server token
    "github" + "_pat_",            # GitHub fine-grained PAT
    "sk" + "-",                    # 通用 API key 前缀
]
_SECRET_WORDS = ["pass" + "word", "pass" + "wd", "api" + "_key", "api" + "key",
                 "secret", "token", "credential"]
_PRIVATE_KEY_MARK = "PRIVATE" + " KEY"

# 个人目录：Windows（盘符 + 冒号 + 反斜杠 + Users + 反斜杠 + 用户名）与 POSIX
# 三形态（根下 Users、根下 home、以及 c 盘挂载前缀）。本注释刻意不写出字面路径，
# 使工具自身在朴素 grep 下也干净（片段拼接纪律）。
# 目录名必须"含或尾随字母数字"——文档里的模式占位（Users 后跟省略号、无用户名）因此不命中。
_WIN_USER_DIR = (re.escape("C" + _COLON + _BS + _USERS) +
                 r"[\\/](?=[A-Za-z0-9._-]{2,})[A-Za-z0-9._-]*[A-Za-z0-9]")
_POSIX_USER_DIR = (r"/(?:[cC]/)?(?:" + _USERS + "|" + _HOME + r")/"
                   r"(?=[A-Za-z0-9._-]*[A-Za-z0-9])[A-Za-z0-9._-]+")

_INTRANET_OCTET = r"[0-9]{1,3}"
_RE_INTRANET = re.compile(
    r"(?<![0-9])(?:"
    r"10\." + _INTRANET_OCTET + r"\." + _INTRANET_OCTET + r"\." + _INTRANET_OCTET +
    r"|192\.168\." + _INTRANET_OCTET + r"\." + _INTRANET_OCTET +
    r"|172\.(?:1[6-9]|2[0-9]|3[01])\." + _INTRANET_OCTET + r"\." + _INTRANET_OCTET +
    r")(?![0-9])")

# 邮箱：local part 必须以字母数字开头（排除 ``+@pytest.fixture`` 这类装饰器）；
# 顶级域至少两位字母（真实 TLD 无单字母）。
_RE_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9][A-Za-z0-9._%+-]*"
    + _AT + r"[A-Za-z0-9-]+(?:" + _DOT + r"[A-Za-z0-9-]+)*"
    + _DOT + r"[A-Za-z]{2,}")

# 手机号：两侧数字边界
_RE_PHONE = re.compile(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])")
# 身份证号：18 位 + 省级行政区码 + 合法出生日期。加结构与日期两道校验后，
# 合成发票号码的 18 位前缀（如 ``259100000000100001``，省级码 25 不存在）不再误报。
_RE_IDCARD = re.compile(
    r"(?<![0-9A-Za-z])"
    r"(?:1[1-5]|2[1-3]|3[1-7]|4[1-6]|5[0-4]|6[1-5])"      # 省级行政区码
    r"[0-9]{4}"                                            # 市/县级码
    r"(?:19|20)[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])"   # 出生日期
    r"[0-9]{3}[0-9Xx]"                                     # 顺序码 + 校验位
    r"(?![0-9A-Za-z])")
_RE_USERPATH = re.compile(_WIN_USER_DIR + r"|" + _POSIX_USER_DIR)
_RE_SECRET = re.compile(
    # ① 令牌前缀 + 高熵主体
    r"(?:" + "|".join(re.escape(t) for t in _SECRET_TOKENS) + r")[A-Za-z0-9_\-]{16,}"
    # ② PEM 私钥头
    + r"|" + _PRIVATE_KEY_MARK
    # ③ 关键字赋值：值必须是**字符串字面量或高熵令牌**。
    #    不能宽到 ``\S{6,}``——那样 ``_RE_SECRET = re.compile(`` 与
    #    ``secret = _SECRET_TOKENS[0]`` 这类源码标识符会被自己的规则命中（M6 实测）。
    + r"|(?:" + "|".join(_SECRET_WORDS) + r")\s*[:=]\s*(?:"
      + r'"[^"]{6,}"'                      # 双引号字面量
      + r"|'[^']{6,}'"                     # 单引号字面量
      + r"|[A-Za-z0-9+/_\-]{12,}(?![A-Za-z0-9_\-\[\(.])"   # 裸令牌（非属性访问/下标）
    + r")",
    re.IGNORECASE)

CATEGORIES = (
    ("secret", _RE_SECRET),
    ("email", _RE_EMAIL),
    ("phone", _RE_PHONE),
    ("idcard", _RE_IDCARD),
    ("userpath", _RE_USERPATH),
    ("intranet_ip", _RE_INTRANET),
)

# 邮箱白名单域名：git 远端地址、GitHub 系统地址、RFC 示例域
_EMAIL_ALLOW_DOMAINS = (
    "github.com",
    "githubusercontent.com",
    "example.com", "example.org", "example.net",
    "localhost", "invalid",
)


def _email_allowed(addr):
    domain = addr.rsplit(_AT, 1)[-1].lower()
    for d in _EMAIL_ALLOW_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return True
    return False


def classify(line):
    """返回该行命中的类目集合（已做邮箱白名单过滤）。"""
    hits = set()
    for name, rx in CATEGORIES:
        for m in rx.finditer(line):
            if name == "email" and _email_allowed(m.group(0)):
                continue
            hits.add(name)
            break
    return hits


def classify_text(text):
    """(类别 -> 命中行数) 统计；用于非逐行来源（跟踪文件、提交信息）。"""
    counts = {}
    for line in text.splitlines():
        for name in classify(line):
            counts[name] = counts.get(name, 0) + 1
    return counts


# --------------------------------------------------------------------------- #
# 来源读取
# --------------------------------------------------------------------------- #
def _run(args):
    """跑 git 子进程（args 为列表，绕过 shell 与 MSYS 参数转写）。"""
    try:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate()
    except OSError as exc:                                   # git 不在 PATH
        raise SystemExit("ERROR: 无法执行 %r：%s" % (args[0], exc))
    if proc.returncode != 0:
        raise SystemExit("ERROR: %s 退出码 %d：%s"
                         % (" ".join(args[:2]), proc.returncode,
                            err.decode("utf-8", "replace").strip()[:400]))
    return out


def _is_binary(blob, path):
    """二进制判据：整文件 NUL 或已知二进制容器后缀。

    两道都要——① 只看文件头会漏判（M6 实测：PDF 前 8KB 无 NUL）；② PDF 的
    ASCII85/FlateDecode 流是**可打印 ASCII**，NUL 判据照样漏（M6 实测假阳性：压缩
    流随机字符撞上邮箱正则）。冻结的合成 PDF/OFD 是数据资产，其内容由被扫描的
    生成器源码程序化产出；对二进制容器做逐字节文本扫描无意义。
    """
    if isinstance(path, str) and os.path.splitext(path)[1].lower() in _BINARY_EXTS:
        return True
    return b"\x00" in blob


def scan_tracked():
    """扫描全部跟踪文件的工作树内容（二进制/容器文件跳过，避免压缩流假阳性）。"""
    raw = _run(["git", "ls-files", "-z"])
    paths = [p for p in raw.decode("utf-8", "surrogateescape").split("\x00") if p]
    findings, scanned, skipped = [], 0, 0
    for path in sorted(paths):
        try:
            with io.open(path, "rb") as fh:
                blob = fh.read()
        except OSError:
            skipped += 1
            continue
        if _is_binary(blob, path):
            skipped += 1
            continue
        scanned += 1
        text = blob.decode("utf-8", "replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for name in sorted(classify(line)):
                findings.append(("%s:%d" % (path, lineno), name))
    return findings, "%d 个跟踪文件（跳过二进制/不可读 %d）" % (scanned, skipped)


def scan_history():
    """扫描全部历史提交引入过的每一行（``git log --all -p`` 的 ``+`` 行）。

    任何版本出现过的任何一行，必然在某个提交里以 ``+`` 行出现，故覆盖全历史内容。
    """
    raw = _run(["git", "log", "--all", "-p", "--no-color", "-U0"])
    text = raw.decode("utf-8", "replace")
    findings = []
    commit = "-"
    lineno_in_patch = 0
    for line in text.splitlines():
        if line.startswith("commit "):
            commit = line.split(None, 1)[1][:12]
            lineno_in_patch = 0
            continue
        lineno_in_patch += 1
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for name in sorted(classify(line[1:])):
            findings.append(("%s:%d" % (commit, lineno_in_patch), name))
    n_commits = len([1 for ln in text.splitlines() if ln.startswith("commit ")])
    return findings, "%d 个提交的全量补丁（+ 行）" % n_commits


def scan_binaries():
    """二进制样例单独扫（内容级文本扫描跳过二进制，这是盲区）。

    两项分开处理：
    * **PDF**：只抽 Info 字典的元数据域（Author/Creator/Producer/Title/Subject/
      Keywords）逐值过分类器——构建机路径、真实姓名/邮箱最爱藏在这里；不扫
      ASCII85/Flate 压缩流（随机字节会撞上邮箱正则，是已知噪声源）。
    * **OFD/ZIP**：按条目解压后逐行扫描（压缩流必须解压才看得见），并复核
      zip 注释与条目名。
    """
    raw = _run(["git", "ls-files", "-z"])
    paths = [p for p in raw.decode("utf-8", "surrogateescape").split("\x00") if p]
    findings = []
    n_pdf = n_zip = 0
    for path in sorted(paths):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            n_pdf += 1
            try:
                blob = io.open(path, "rb").read()
            except OSError:
                continue
            for key, value in _pdf_info_values(blob):
                for name in sorted(classify(value)):
                    findings.append(("%s#/%s" % (path, key), name))
        elif ext in (".ofd", ".zip"):
            n_zip += 1
            try:
                with zipfile.ZipFile(path) as zf:
                    if zf.comment:
                        for name in sorted(classify(zf.comment.decode("utf-8", "replace"))):
                            findings.append(("%s#zip-comment" % path, name))
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        for name in sorted(classify(info.filename)):
                            findings.append(("%s#entries" % path, name))
                        data = zf.read(info)
                        if _is_binary(data, info.filename):
                            continue
                        for lineno, line in enumerate(
                                data.decode("utf-8", "replace").splitlines(), 1):
                            for name in sorted(classify(line)):
                                findings.append(
                                    ("%s#%s:%d" % (path, info.filename, lineno), name))
            except (zipfile.BadZipFile, OSError):
                continue
    return findings, "PDF %d 份（Info 元数据域）+ ZIP/OFD %d 份（逐条目解压）" % (n_pdf, n_zip)


def _pdf_info_values(blob):
    """抽取 PDF Info 字典的元数据域值（未压缩，可安全正则）。"""
    values = []
    for key in ("Author", "Creator", "Producer", "Title", "Subject", "Keywords"):
        pattern = (r"/" + key + r"\s*\(([^)]*)\)").encode("ascii")
        for match in re.finditer(pattern, blob):
            values.append((key, match.group(1).decode("latin-1")))
    return values


def scan_dist(root="dist", markers=()):
    """构建产物本体扫描（仓库树干净 ≠ 冻结产物干净，这是第 5 步单独的扫描面）。

    只跑**强标记**（个人标记/姊妹词），由调用方经 ``--marker-b64`` 传入——
    字面值不入仓库。刻意**不跑**邮箱/手机号等宽正则：上游厂商 SBOM/LICENSE 的
    公共邮箱与二进制噪声不是本项目泄漏面，跑必刷屏（系列纪律）。
    另复核产物树无仓库数据集成分（spec 的 datas 白名单为空，属设计断言）。
    """
    if not os.path.isdir(root):
        raise SystemExit("ERROR: 产物目录不存在：%s（先构建再扫）" % root)
    findings = []
    n_files = 0
    n_bytes = 0
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            try:
                blob = io.open(path, "rb").read()
            except OSError:
                continue
            n_files += 1
            n_bytes += len(blob)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            for index, marker in enumerate(markers, 1):
                if marker and marker in blob:
                    findings.append((rel, "marker#%d x%d" % (index, blob.count(marker))))
            if (name.lower() in _FORBIDDEN_OUTPUT_NAMES
                    or os.path.splitext(name)[1].lower() in _FORBIDDEN_OUTPUT_EXTS):
                findings.append((rel, "forbidden-data"))
    return findings, ("%d 个产物文件 / %.1f MB（强标记 %d 个 + 禁区成分复核）"
                      % (n_files, n_bytes / 1048576.0, len(markers)))


def scan_messages():
    """扫描全部提交信息。"""
    raw = _run(["git", "log", "--all", "--format=%H%x00%B%x01"])
    text = raw.decode("utf-8", "replace")
    findings = []
    for record in text.split("\x01"):
        record = record.strip("\x00\n")
        if not record:
            continue
        sha, _, body = record.partition("\x00")
        for lineno, line in enumerate(body.splitlines(), 1):
            for name in sorted(classify(line)):
                findings.append(("%s#msg:%d" % (sha[:12], lineno), name))
    n = len([r for r in text.split("\x01") if r.strip("\x00\n")])
    return findings, "%d 条提交信息" % n


def scan_metadata():
    """扫描提交作者/提交者姓名与邮箱（git 元数据，内容级扫描覆盖不到）。"""
    raw = _run(["git", "log", "--all", "--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00"])
    text = raw.decode("utf-8", "replace")
    findings = []
    seen = set()
    for field in text.split("\x00"):
        field = field.strip()
        if not field or _RE_EMAIL.fullmatch(field) is None:
            continue
        if _email_allowed(field):
            continue
        if field in seen:                       # 同一邮箱多提交只报一次
            continue
        seen.add(field)
        findings.append(("git-metadata", "email"))
    n = len([1 for f in text.split("\x00") if f.strip()])
    return findings, "%d 个元数据字段" % n


# --------------------------------------------------------------------------- #
# selftest：阳性 + 阴性对照
# --------------------------------------------------------------------------- #
def _positive_samples():
    """构造阳性样本（片段拼接，不在源码里出现完整敏感字面值）。"""
    user = "zcode" + "probe"
    secret = _SECRET_TOKENS[0] + "A" * 24
    key_line = "api" + "_key = " + "Z" * 12
    return {
        "secret": [secret, key_line, "-----BEGIN RSA PRIVATE" + " KEY-----"],
        "email": ["zhang" + "san" + _AT + "mail" + ".com",
                  "a" + _AT + "corp" + ".cn"],
        "phone": ["1" + "3800138000", "联系：1" + "5912345678。"],
        "idcard": ["11" + "0101" + "1990" + "01" + "01" + "123" + "4",
                   "31" + "0101" + "1985" + "05" + "12" + "143" + "X"],
        "userpath": ["C" + _COLON + _BS + _USERS + _BS + user + _BS + "proj",
                     "/c/" + _USERS + "/" + user + "/proj",
                     "/" + _HOME + "/" + user + "/proj"],
        "intranet_ip": ["10" + ".12" + ".34" + ".56",
                        "192" + ".168" + ".1" + ".10",
                        "172" + ".20" + ".0" + ".1"],
    }


def _negative_samples():
    """阴性样本：真实工程里常见、必须**不**命中的形态（防假阳性回归）。"""
    return [
        "git" + _AT + "github.com:owner/repo.git",          # SSH 远端地址
        "Hi yuluo554! You've successfully authenticated",
        "25910000000010000101",                              # 20 位合成发票号码
        'build_card(number="259100000000100001' + "%02d" + '" % (i + 1),',
        "C" + _COLON + _BS + _USERS + _BS + "..." + "/内网 IP/邮箱",   # 文档里的模式占位
        "+" + _AT + "pytest.fixture(scope=\"session\")",      # 装饰器
        _AT + "pytest.mark.parametrize(\"raw,expected\", [",
        "31234",                                             # 短数字（非手机号/身份证）
        "0.13", "2026-10-06 12:30:00",
        "https://github.com/yuluo554/invoice-ledger-checker",
        # 源码里的标识符赋值：不是密钥（M6 实测：宽 \S{6,} 口径会让扫描器自命中）
        "_RE_SECRET = re.compile(",
        "    " + "secret" + " = _SECRET_TOKENS[0] + " + '"A"' + " * 24",
        "token = self.client.token",
        "pass" + "word" + ' = os.environ["APP_PW"]',
    ]


def selftest():
    """阳性对照必须全命中、阴性对照必须全不命中。返回 (ok, 报告行列表)。"""
    report, ok = [], True
    for name, samples in sorted(_positive_samples().items()):
        missing = [s for s in samples if name not in classify(s)]
        if missing:
            ok = False
            report.append("FAIL 阳性对照缺失 [%s] x%d（%d 个样本该类别未命中）"
                          % (name, len(missing), len(samples)))
        else:
            report.append("ok   阳性对照 [%s] x%d" % (name, len(samples)))
    for sample in _negative_samples():
        hit = classify(sample)
        if hit:
            ok = False
            report.append("FAIL 阴性对照误报 %s（类别 %s）"
                          % (sample[:40], ",".join(sorted(hit))))
    report.append("ok   阴性对照 x%d 全部未命中" % len(_negative_samples()))
    known = set(n for n, _ in CATEGORIES)
    covered = set(_positive_samples().keys())
    if covered == known:
        report.append("ok   类目覆盖 %d/%d 全部有阳性对照" % (len(covered), len(known)))
    else:
        ok = False
        report.append("FAIL 类目缺少阳性对照：%s" % sorted(known - covered))
    return ok, report


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def _emit(mode, findings, scope):
    counts = {}
    for loc, name in findings:
        counts[name] = counts.get(name, 0) + 1
    distinct = sorted(set(findings))
    print("[%s] %s" % (mode, scope))
    for loc, name in distinct:
        print("  %s [%s] x%d" % (loc, name, counts[name]))
    total = sum(counts.values())
    print("[%s] 命中 %d 行（%d 类）" % (mode, len(distinct), len(counts)))
    return len(distinct)


def main(argv):
    modes = {"tracked": scan_tracked, "history": scan_history,
             "binaries": scan_binaries,
             "messages": scan_messages, "metadata": scan_metadata}
    usage = ("用法：python tools/sensitive_scan.py "
             "{[selftest|all|" + "|".join(sorted(modes)) + "]}")
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(usage)
        return 2
    mode = args[0]
    if mode == "selftest":
        ok, report = selftest()
        for line in report:
            print(line)
        print("[selftest] %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    if mode == "all":
        selected = sorted(modes)
    elif mode == "dist":
        root, markers, rest = "dist", [], args[1:]
        while rest:
            if rest[0] == "--dir" and len(rest) > 1:
                root, rest = rest[1], rest[2:]
            elif rest[0] == "--marker-b64" and len(rest) > 1:
                markers.append(base64.b64decode(rest[1]))
                rest = rest[2:]
            else:
                print(usage)
                return 2
        findings, scope = scan_dist(root, markers)
        return 0 if _emit("dist", findings, scope) == 0 else 1
    elif mode in modes:
        selected = [mode]
    else:
        print(usage)
        return 2

    total = 0
    for name in selected:
        try:
            findings, scope = modes[name]()
        except SystemExit as exc:
            print(str(exc))
            return 2
        total += _emit(name, findings, scope)
    print("[all] 命中 %d 行" % total)
    return 0 if total == 0 else 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")             # py3.7+
    except (AttributeError, ValueError):
        pass
    sys.exit(main(sys.argv))
