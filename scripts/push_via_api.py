#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在普通 Git 推送不可用时，通过 GitHub API 提交暂存区中的改动。

只支持正确克隆且与远端处于同一提交的仓库。先 git add，再 --dry-run 检查。
默认保留远端文件；删除必须显式指定 --allow-delete。工作流文件始终跳过。
API 提交完成后，本地 HEAD 不会自动移动；继续编辑前需要同步远端。
"""
import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTECTED_PREFIX = ".github/workflows/"
ESSENTIAL_FILES = {
    "content/site.json", "scripts/build.py", "assets/css/style.css",
    "assets/js/app.js", "docs/index.html",
}


def git(args):
    """失败时停止，禁止将 Git 错误当成空文件清单。"""
    proc = subprocess.run(["git"] + args, capture_output=True, cwd=ROOT)
    if proc.returncode:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError("Git 检查失败，请使用完整克隆的仓库：" + detail[:300])
    return proc.stdout


def collect_local():
    actual_root = Path(git(["rev-parse", "--show-toplevel"]).decode("utf-8").strip()).resolve()
    if actual_root != ROOT.resolve():
        raise RuntimeError("脚本目录不是仓库根目录；请勿在解压副本或另一个仓库内运行。")
    records = git(["ls-files", "--stage", "-z"]).split(b"\0")
    files = {}
    for record in records:
        if not record:
            continue
        metadata, raw_name = record.split(b"\t", 1)
        mode, sha, stage = metadata.decode("ascii").split()
        name = raw_name.decode("utf-8")
        if stage != "0":
            raise RuntimeError("存在未解决的合并冲突，请先处理后再提交。")
        if mode not in ("100644", "100755"):
            raise RuntimeError("不支持的文件类型：" + name)
        path = ROOT / name
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise RuntimeError("文件路径超出仓库：" + name)
        files[name] = {"mode": mode, "sha": sha}
    if not files:
        raise RuntimeError("Git 文件清单为空，已停止；不会删除远端文件。")
    missing = sorted(ESSENTIAL_FILES - files.keys())
    missing += sorted(name for name in ESSENTIAL_FILES if not (ROOT / name).is_file())
    if missing:
        raise RuntimeError("网站关键文件缺失，已停止：" + ", ".join(sorted(set(missing))))
    return files


def gh(args, body=None, timeout=180):
    command = ["gh", "api"] + args
    if body is not None:
        command += ["--input", "-"]
    proc = subprocess.run(
        command, input=json.dumps(body) if body is not None else None,
        capture_output=True, text=True, encoding="utf-8", timeout=timeout, cwd=ROOT,
    )
    if proc.returncode:
        raise RuntimeError("GitHub API 请求失败：" + proc.stderr.strip()[:400])
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("GitHub API 未返回有效 JSON，已停止。") from error
    if not isinstance(result, dict):
        raise RuntimeError("GitHub API 返回格式异常，已停止。")
    return result


def check_repository(repo, branch):
    current_branch = git(["symbolic-ref", "--short", "HEAD"]).decode("utf-8").strip()
    if current_branch != branch:
        raise RuntimeError("当前分支与目标分支不一致，已停止。")
    origin = git(["remote", "get-url", "origin"]).decode("utf-8").strip().rstrip("/")
    slug = origin.removesuffix(".git")
    if slug.startswith("https://github.com/"):
        slug = slug[len("https://github.com/"):]
    elif slug.startswith("git@github.com:"):
        slug = slug[len("git@github.com:"):]
    else:
        raise RuntimeError("origin 不是支持的 GitHub 仓库地址，已停止。")
    if slug.lower() != repo.lower():
        raise RuntimeError("origin 与目标仓库不一致，已停止。")
    return git(["rev-parse", "HEAD"]).decode("ascii").strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", "-m", required=True)
    parser.add_argument("--repo", default="uestc-aic/uestc-aic.github.io")
    parser.add_argument("--branch", default="main")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写入远端")
    deletion = parser.add_mutually_exclusive_group()
    deletion.add_argument("--allow-delete", action="store_true", help="明确允许删除暂存区已移除的非关键文件")
    deletion.add_argument("--no-delete", action="store_true", help="兼容旧用法；默认已禁止删除")
    args = parser.parse_args(argv)
    try:
        # 所有本地检查均在访问 GitHub 前进行。
        local = collect_local()
        local_head = check_repository(args.repo, args.branch)
        print(f"目标：{args.repo} / {args.branch}；仅提交 git add 后的暂存区内容。")
        ref = gh([f"repos/{args.repo}/git/ref/heads/{args.branch}"])
        head = (ref.get("object") or {}).get("sha")
        if not head or head != local_head:
            raise RuntimeError("本地 HEAD 与远端不一致；请先同步并处理差异，禁止用旧副本覆盖。")
        commit = gh([f"repos/{args.repo}/git/commits/{head}"])
        tree_sha = (commit.get("tree") or {}).get("sha")
        if not tree_sha:
            raise RuntimeError("无法读取远端文件树，已停止。")
        tree = gh([f"repos/{args.repo}/git/trees/{tree_sha}?recursive=1"])
        if tree.get("truncated") or not isinstance(tree.get("tree"), list):
            raise RuntimeError("远端文件清单不完整，已停止。")
        remote = {item["path"]: item for item in tree["tree"] if item.get("type") == "blob"}
        if not remote:
            raise RuntimeError("远端文件清单为空，已停止。")

        skipped = sorted(name for name in local if name.startswith(PROTECTED_PREFIX))
        local = {name: item for name, item in local.items() if not name.startswith(PROTECTED_PREFIX)}
        changes = {
            name: item for name, item in local.items()
            if name not in remote or any(item[key] != remote[name].get(key) for key in ("sha", "mode"))
        }
        removed = sorted(name for name in remote if name not in local and not name.startswith(PROTECTED_PREFIX))
        deletions = removed if args.allow_delete else []
        if removed and not args.allow_delete:
            print(f"保留远端 {len(removed)} 个文件：删除未获显式授权。")
        if skipped:
            print(f"保留远端工作流配置；本地 {len(skipped)} 个工作流文件不通过此工具提交。")
        print(f"新增或修改 {len(changes)} 个文件，删除 {len(deletions)} 个文件。")
        for name in sorted(changes):
            print("  + " + name)
        for name in deletions:
            print("  - " + name)
        if args.dry_run:
            print("试运行完成，未修改远端。")
            return 0
        if not changes and not deletions:
            print("没有需要提交的改动。")
            return 0

        entries = []
        for name, item in sorted(changes.items()):
            data = git(["cat-file", "blob", item["sha"]])
            blob = gh([f"repos/{args.repo}/git/blobs", "--method", "POST"],
                      {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"})
            if blob.get("sha") != item["sha"]:
                raise RuntimeError("上传校验失败，未创建提交：" + name)
            entries.append({"path": name, "mode": item["mode"], "type": "blob", "sha": blob["sha"]})
        entries += [{"path": name, "mode": remote[name]["mode"], "type": "blob", "sha": None} for name in deletions]
        new_tree = gh([f"repos/{args.repo}/git/trees", "--method", "POST"],
                      {"base_tree": tree_sha, "tree": entries})
        if not new_tree.get("sha"):
            raise RuntimeError("未能创建文件树，已停止。")
        new_commit = gh([f"repos/{args.repo}/git/commits", "--method", "POST"],
                        {"message": args.message, "tree": new_tree["sha"], "parents": [head]})
        if not new_commit.get("sha"):
            raise RuntimeError("未能创建提交，已停止。")
        # 非快进更新会被 GitHub 拒绝，避免覆盖处理期间出现的新提交。
        updated = gh([f"repos/{args.repo}/git/refs/heads/{args.branch}", "--method", "PATCH"],
                     {"sha": new_commit["sha"], "force": False})
        if (updated.get("object") or {}).get("sha") != new_commit["sha"]:
            raise RuntimeError("远端分支未更新，请检查 GitHub。")
        print(f"提交成功：https://github.com/{args.repo}/commit/{new_commit['sha']}")
        print("继续编辑前请同步远端；本工具没有移动本地 HEAD。")
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        print("[已停止] " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
