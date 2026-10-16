#!/usr/bin/env python3
"""构建交付包及文件校验清单，或只读校验现有交付包。仅使用标准库。"""
import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
PREFIX = 'uestc-aic-website/'
MANIFEST = PREFIX + 'DELIVERY.json'


def git(args):
    result = subprocess.run(['git'] + args, cwd=ROOT, capture_output=True)
    if result.returncode:
        raise ValueError('无法读取 Git 仓库；请从完整克隆的仓库生成交付包。')
    return result.stdout.decode('utf-8').strip('\n')


def check_repository():
    if Path(git(['rev-parse', '--show-toplevel'])).resolve() != ROOT.resolve():
        raise ValueError('脚本所在目录必须是仓库根目录。')
    git(['rev-parse', 'HEAD'])


def make_package(output):
    check_repository()
    names = sorted(name for name in git(['ls-files', '-z']).split('\0') if name)
    if not names:
        raise ValueError('文件清单为空，停止打包。')
    payload = {}
    for name in names:
        path = ROOT / name
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('不支持指向仓库外的路径或符号链接：' + name)
        if not path.is_file():
            raise ValueError('文件缺失，请先提交删除或恢复文件：' + name)
        payload[name] = path.read_bytes()
    manifest = {
        'format': 1,
        'repository': 'https://github.com/uestc-aic/uestc-aic.github.io',
        'commit': git(['rev-parse', 'HEAD']),
        'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'working_tree_changes': git(['status', '--porcelain']).splitlines(),
        'files': [
            {'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            for name, data in payload.items()
        ],
    }
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(PREFIX + name, data)
        archive.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    verify_package(output)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_name(output.name + '.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='utf-8')
    return len(payload)


def verify_package(filename):
    with zipfile.ZipFile(filename) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('交付包存在重复路径。')
        for name in names:
            parts = PurePosixPath(name)
            if parts.is_absolute() or '..' in parts.parts or '\\' in name or ':' in name:
                raise ValueError('交付包存在异常路径。')
        manifest = json.loads(archive.read(MANIFEST))
        if manifest.get('format') != 1 or not manifest.get('files'):
            raise ValueError('无法识别交付清单。')
        expected = {MANIFEST}
        for item in manifest['files']:
            name = PREFIX + item['path']
            if name in expected:
                raise ValueError('交付清单存在重复路径。')
            expected.add(name)
            data = archive.read(name)
            if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError('校验失败：' + item['path'])
        if set(names) != expected:
            raise ValueError('交付包文件与清单不一致。')
    return len(manifest['files'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--output', type=Path, help='生成 ZIP 的路径')
    mode.add_argument('--verify', type=Path, help='只读校验已有 ZIP，不需要 Git 仓库')
    args = parser.parse_args(argv)
    try:
        if args.verify:
            count = verify_package(args.verify)
            print(f'校验通过：{count} 个文件，大小与 SHA-256 全部匹配。')
        else:
            check_repository()
            for script in ('build.py', 'verify.py'):
                subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'scripts' / script)], cwd=ROOT, check=True)
            count = make_package(args.output)
            print(f'交付包已生成并通过校验：{args.output}（{count} 个文件）')
        return 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print('交付包操作已停止：' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
