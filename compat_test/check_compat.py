#!/usr/bin/env python3
"""清茶云订阅兼容性校验:对多个 mihomo 内核版本运行 `mihomo -t` 配置校验矩阵。

用途:
  背景:2026 年 clash-verge-rev v2.5.2+ 搭载的新内核曾出现同类订阅"节点 Unknown/解析失败"
  的回归。本脚本用脱敏的清茶云订阅样本(qingcha_sample.yaml)持续盯住这类回归:
  新内核一旦解析不了清茶云的配置写法,CI 会立刻红。

  qingcha_sample.yaml            修复后的配置形态 —— 必须 PASS(校验失败则本脚本退出码 1)
  qingcha_sample_upstream_dns.yaml  上游原始 DNS(境外 fallback)对照 —— 仅报告,不影响退出码
                                    (其故障是运行时的 DNS 解析失败,`-t` 静态校验无法复现)

用法:
  python check_compat.py                     # 校验 PINNED + LATEST 两个版本
  python check_compat.py v1.19.25 v1.19.31   # 校验指定版本
"""

import glob
import os
import platform
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

PINNED = "v1.19.25"  # clash-verge-rev v2.5.1 时代内核,已知兼容基线
LATEST_API = "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest"
DOWNLOAD = "https://github.com/MetaCubeX/mihomo/releases/download/{tag}/mihomo-{asset}-{tag}.zip"
HERE = os.path.dirname(os.path.abspath(__file__))
MUST_PASS = os.path.join(HERE, "qingcha_sample.yaml")
REPORT_ONLY = os.path.join(HERE, "qingcha_sample_upstream_dns.yaml")


def latest_tag():
    req = urllib.request.Request(LATEST_API, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json_tag(resp.read())


def json_tag(blob):
    import json

    return json.loads(blob)["tag_name"]


def asset_name(tag):
    system = platform.system().lower()  # linux / windows / darwin
    machine = platform.machine().lower()
    if system == "windows":
        return f"mihomo-windows-amd64-v2-{tag}.exe"
    if system == "darwin":
        return f"mihomo-darwin-arm64-{tag}" if "arm" in machine else f"mihomo-darwin-amd64-v2-{tag}"
    return f"mihomo-linux-amd64-v2-{tag}"


def fetch_core(tag, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    exe = os.path.join(cache_dir, f"mihomo-{tag}" + (".exe" if platform.system() == "windows" else ""))
    if os.path.exists(exe):
        return exe
    asset = asset_name(tag)
    url = DOWNLOAD.format(tag=tag, asset=asset[: asset.rfind("-" + tag)])
    zpath = os.path.join(cache_dir, f"mihomo-{tag}.zip")
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=300) as resp, open(zpath, "wb") as f:
        f.write(resp.read())
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(cache_dir)
    inner = glob.glob(os.path.join(cache_dir, f"mihomo-*{tag}*"))
    for cand in inner:
        if cand.endswith((".exe",)) or ("windows" not in cand and os.access(cand, os.X_OK)):
            if os.path.isfile(cand) and not cand.endswith(".zip"):
                os.replace(cand, exe)
                break
    os.chmod(exe, 0o755)
    os.remove(zpath)
    return exe


def run_test(core, tag, config):
    workdir = tempfile.mkdtemp(prefix=f"mihomo-{tag}-")
    cmd = [core, "-t", "-d", workdir, "-f", config]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    output = proc.stdout + proc.stderr
    ok = "test is successful" in output
    reason = ""
    if not ok:
        match = re.search(r'level=(?:error|fatal) msg="([^"]+)"', output)
        reason = match.group(1) if match else output.strip().splitlines()[-1] if output.strip() else "unknown"
    return ok, reason


def main():
    tags = sys.argv[1:] or [PINNED, latest_tag()]
    print(f"qingcha cloud compat matrix: {tags}")
    cache = os.path.join(HERE, "bin")
    failures = 0
    for tag in tags:
        core = fetch_core(tag, cache)
        ok, reason = run_test(core, tag, MUST_PASS)
        print(f"  [{tag}] MUST-PASS qingcha_sample.yaml          -> {'PASS' if ok else 'FAIL: ' + reason}")
        if not ok:
            failures += 1
        ok2, reason2 = run_test(core, tag, REPORT_ONLY)
        print(f"  [{tag}] report-only upstream-dns variant     -> {'PASS' if ok2 else 'FAIL(static): ' + reason2}")
        print("         (its real-world failure is runtime DNS, see docs/COMPAT.md)")
    if failures:
        print(f"RESULT: {failures} required check(s) FAILED — latest mihomo broke qingcha cloud parsing")
        sys.exit(1)
    print("RESULT: all required checks passed")


if __name__ == "__main__":
    main()
