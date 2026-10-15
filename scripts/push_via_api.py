#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通过 GitHub API 推送（绕开被墙的 github.com）
================================================

**为什么需要它**：本机到 `github.com:443` 的连接会被干扰（超时/重置），
`git push` 因此失败；但 `api.github.com` 是通的。
本脚本用 GitHub 的 Git Data API 完成一次原子提交：
    blobs → tree → commit → 更新 ref
效果与 `git push` 等价（一个提交，包含全部改动），走的是能通的域名。

用法：
    python3 scripts/push_via_api.py --message "更新内容"
    python3 scripts/push_via_api.py --message "..." --dry-run    # 只列出行将提交的文件
    python3 scripts/push_via_api.py --message "..." --repo owner/repo

前置条件：
- 已安装并在本机登录 `gh`（`gh auth status` 有输出即可）
- 令牌具备 `repo` 权限

限制（重要）：
- **不会提交 `.github/workflows/` 下的文件**。GitHub 规定写工作流文件需要额外的
  `workflow` 权限，缺失时 API 会返回 404。脚本会明确提示并跳过，不会误删已有的工作流。
- 不做 merge / rebase。若远端已有别人的新提交，脚本以远端为父提交，
  把你本地的文件覆盖上去（本地未同步的远端改动会被覆盖，先 `git fetch` 看看）。
"""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SKIP_DIRS = {".git", "__pycache__", ".vscode", ".idea", "node_modules", ".sites-runtime"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
# 无 workflow 权限时无法写入，必须显式排除（否则会被当成删除，把工作流删掉）
PROTECTED_PREFIX = ".github/workflows/"


def gh(args, body=None, timeout=180):
    cmd = ["gh", "api"] + args
    if body is not None:
        cmd += ["--input", "-"]
        proc = subprocess.run(cmd, input=json.dumps(body), capture_output=True, text=True,
                              timeout=timeout, cwd=ROOT)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    if proc.returncode != 0:
        return {"__error__": proc.stderr.strip()[:500]}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"__raw__": proc.stdout[:300]}


def collect_local():
    """工作区里应当提交的文件。

    用 git 自己来判定，这样 .gitignore 语义完全一致
    （否则会把 __pycache__、content/collected/_state.json 这类运行时文件也提交上去）。
    """
    def listed(args):
        proc = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=ROOT)
        if proc.returncode != 0:
            return []
        return [p for p in proc.stdout.split("\0") if p]

    tracked = listed(["ls-files", "-z"])
    untracked = listed(["ls-files", "--others", "--exclude-standard", "-z"])

    files = {}
    for rel in set(tracked) | set(untracked):
        path = ROOT / rel
        if path.is_file():
            files[rel] = path
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", "-m", required=True, help="提交信息")
    ap.add_argument("--repo", default="uestc-aic/uestc-aic.github.io")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    repo = args.repo
    print(f"目标仓库：{repo}  分支：{args.branch}")

    ref = gh([f"/repos/{repo}/git/ref/heads/{args.branch}"])
    if "object" not in ref:
        print(f"  [错误] 读不到分支：{ref.get('__error__')}")
        return 1
    head = ref["object"]["sha"]
    base_tree = gh([f"/repos/{repo}/git/commits/{head}"])["tree"]["sha"]
    remote_tree = gh([f"/repos/{repo}/git/trees/{base_tree}?recursive=1"])
    remote_paths = {x["path"] for x in remote_tree.get("tree", []) if x["type"] == "blob"}
    print(f"远端当前提交：{head[:8]}（{len(remote_paths)} 个文件）")

    local = collect_local()
    skipped = sorted(p for p in local if p.startswith(PROTECTED_PREFIX))
    local = {k: v for k, v in local.items() if not k.startswith(PROTECTED_PREFIX)}

    if not remote_paths:
        # 分支为空时没人会「被删」，保守起见不做任何删除
        deletions = []
    else:
        deletions = sorted(remote_paths - set(local) - {p for p in remote_paths
                                                        if p.startswith(PROTECTED_PREFIX)})

    print(f"\n将提交 {len(local)} 个文件")
    if deletions:
        print(f"将删除 {len(deletions)} 个文件：")
        for d in deletions[:20]:
            print(f"   - {d}")
        if len(deletions) > 20:
            print(f"   … 另有 {len(deletions) - 20} 个")
    if skipped:
        print(f"\n跳过 {len(skipped)} 个工作流文件（需要 workflow 权限）：")
        for s_ in skipped:
            print(f"   ! {s_}")
        print("   → 授权方式：gh auth refresh -h github.com -s workflow")

    if args.dry_run:
        print("\n--dry-run：未做任何改动。")
        return 0

    print("\n上传文件…")
    entries, failed = [], []
    for i, (rel, path) in enumerate(sorted(local.items()), 1):
        res = gh([f"/repos/{repo}/git/blobs", "--method", "POST"],
                 {"content": base64.b64encode(path.read_bytes()).decode(), "encoding": "base64"})
        if "sha" in res:
            entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": res["sha"]})
        else:
            failed.append((rel, res.get("__error__")))
        if i % 20 == 0:
            print(f"   … {i}/{len(local)}")
    if failed:
        print("\n[错误] 以下文件上传失败，已中止（未做任何提交）：")
        for rel, err in failed:
            print(f"   {rel}: {err}")
        return 1

    tree = gh([f"/repos/{repo}/git/trees", "--method", "POST"],
              {"base_tree": base_tree,
               "tree": entries + [{"path": d, "mode": "100644", "type": "blob", "sha": None}
                                  for d in deletions]})
    if "sha" not in tree:
        print(f"\n[错误] 建树失败：{tree.get('__error__')}")
        return 1

    commit = gh([f"/repos/{repo}/git/commits", "--method", "POST"],
                {"message": args.message, "tree": tree["sha"], "parents": [head]})
    if "sha" not in commit:
        print(f"\n[错误] 建提交失败：{commit.get('__error__')}")
        return 1

    updated = gh([f"/repos/{repo}/git/refs/heads/{args.branch}", "--method", "PATCH"],
                 {"sha": commit["sha"], "force": False})
    if "object" not in updated:
        print(f"\n[错误] 更新分支失败：{updated.get('__error__')}")
        return 1

    print(f"\n完成。新提交：{commit['sha'][:8]}")
    print(f"查看：https://github.com/{repo}/commit/{commit['sha']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
