#!/usr/bin/env python3
"""清茶云订阅兼容性校验:对多个 mihomo 内核版本运行 `mihomo -t` 配置校验矩阵。

用途:
  背景:2026 年 clash-verge-rev v2.5.2+ 搭载的新内核曾出现同类订阅"节点 Unknown/解析失败"
  的回归。本脚本用脱敏的清茶云订阅样本(qingcha_sample.yaml)持续盯住这类回归:
  新内核一旦解析不了清茶云的配置写法,CI 会立刻红。

  qingcha_sample.yaml               修复后的配置形态 —— 必须 PASS(校验失败则本脚本退出码 1)
  qingcha_sample_upstream_dns.yaml  上游原始 DNS(境外 fallback)对照 —— 仅报告,不影响退出码
                                    (其故障是运行时的 DNS 解析失败,`-t` 静态校验无法复现)

用法:
  python check_compat.py                     # 校验 PINNED + LATEST 两个版本
  python check_compat.py v1.19.25 v1.19.31   # 校验指定版本
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

PINNED = "v1.19.25"  # clash-verge-rev v2.5.1 时代内核,已知兼容基线
LATEST_API = "https://api.github.com/repos/MetaCubeX/mihomo/releases/latest"
RELEASE_API = "https://api.github.com/repos/MetaCubeX/mihomo/releases/tags/{tag}"
GEOIP = "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/geoip.metadb"
HERE = os.path.dirname(os.path.abspath(__file__))
MUST_PASS = os.path.join(HERE, "qingcha_sample.yaml")
REPORT_ONLY = os.path.join(HERE, "qingcha_sample_upstream_dns.yaml")


def gh_get(url):
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def latest_tag():
    return json.loads(gh_get(LATEST_API))["tag_name"]


def core_slug(tag):
    """release 资产的平台命名段,如 windows-amd64-v2 / linux-amd64-v2。"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "windows":
        return "windows-amd64-v2"
    if system == "darwin":
        return "darwin-arm64" if ("arm" in machine or "aarch" in machine) else "darwin-amd64-v2"
    return "linux-amd64-v2"


def fetch_core(tag, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    exe = os.path.join(cache_dir, f"mihomo-{tag}{'.exe' if platform.system() == 'windows' else ''}")
    if os.path.exists(exe):
        return exe
    slug = core_slug(tag)
    assets = json.loads(gh_get(RELEASE_API.format(tag=tag))).get("assets", [])
    # windows 资产是 zip(内含单文件),linux/macos 是 gz(单文件);按实际命名取
    candidates = [a for a in assets if a["name"] in
                  (f"mihomo-{slug}-{tag}.zip", f"mihomo-{slug}-{tag}.gz")]
    if not candidates:
        raise RuntimeError(f"no asset for {slug} in release {tag}: {[a['name'] for a in assets][:8]}")
    url = candidates[0]["browser_download_url"]
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    arch = os.path.join(cache_dir, candidates[0]["name"])
    with urllib.request.urlopen(req, timeout=300) as resp, open(arch, "wb") as f:
        f.write(resp.read())
    if arch.endswith(".zip"):
        with zipfile.ZipFile(arch) as zf:
            members = [n for n in zf.namelist() if n.startswith("mihomo") and not n.endswith("/")]
            if not members:
                raise RuntimeError(f"no core binary in {arch}: {zf.namelist()}")
            zf.extract(members[0], cache_dir)
            extracted = os.path.join(cache_dir, members[0])
            if extracted != exe:
                os.replace(extracted, exe)
    else:
        import gzip
        with gzip.open(arch, "rb") as src, open(exe, "wb") as dst:
            dst.write(src.read())
    os.remove(arch)
    os.chmod(exe, 0o755)
    return exe


def fetch_geoip(cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    db = os.path.join(cache_dir, "geoip.metadb")
    if not os.path.exists(db):
        print(f"  downloading {GEOIP}")
        req = urllib.request.Request(GEOIP, headers={"Accept": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(db + ".tmp", "wb") as f:
            f.write(resp.read())
        os.replace(db + ".tmp", db)
    return db


def run_test(core, config, geoip):
    workdir = tempfile.mkdtemp(prefix="mihomo-test-")
    shutil.copy(geoip, os.path.join(workdir, "geoip.metadb"))
    proc = subprocess.run([core, "-t", "-d", workdir, "-f", config],
                          capture_output=True, text=True, timeout=180)
    output = proc.stdout + proc.stderr
    if "test is successful" in output:
        return True, ""
    for line in output.splitlines():
        if 'level=error' in line or 'level=fatal' in line:
            return False, line.split('msg="')[-1].rstrip('"')
    return False, (output.strip().splitlines() or ["unknown"])[-1]


def main():
    tags = sys.argv[1:] or [PINNED, latest_tag()]
    print(f"qingcha cloud compat matrix: {tags}")
    cache = os.path.join(HERE, "bin")
    geoip = fetch_geoip(cache)
    failures = 0
    for tag in tags:
        core = fetch_core(tag, cache)
        ok, reason = run_test(core, MUST_PASS, geoip)
        print(f"  [{tag}] MUST-PASS qingcha_sample.yaml          -> {'PASS' if ok else 'FAIL: ' + reason}")
        if not ok:
            failures += 1
        ok2, reason2 = run_test(core, REPORT_ONLY, geoip)
        print(f"  [{tag}] report-only upstream-dns variant     -> {'PASS' if ok2 else 'FAIL(static): ' + reason2}")
        print("         (its real-world failure is runtime DNS, see docs/COMPAT.md)")
    if failures:
        print(f"RESULT: {failures} required check(s) FAILED — latest mihomo broke qingcha cloud parsing")
        sys.exit(1)
    print("RESULT: all required checks passed")


if __name__ == "__main__":
    main()
