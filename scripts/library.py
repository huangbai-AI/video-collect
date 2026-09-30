"""本地选题中台入口：演示、导入、生成与打开。Python 3.10+，不需要安装依赖。"""
from __future__ import annotations

import argparse
import json
import webbrowser
from pathlib import Path

from build_unified_library import build
from import_links import import_file, configure_output
from store import DATA_DIR, DB_PATH


def main():
    configure_output()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['demo', 'import', 'build', 'open'])
    parser.add_argument('file', nargs='?', type=Path)
    parser.add_argument('--output', type=Path, default=Path.home() / 'video-collect-site')
    parser.add_argument('--archive', type=Path, action='append', default=[])
    parser.add_argument('--contributor', default='')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    archive = Path(DATA_DIR) / 'imports'
    try:
        if args.action == 'demo':
            # Keep the demo separate and never merge the user's existing database.
            output = output / 'demo'
            sample = Path(__file__).resolve().parents[1] / 'examples' / 'topics.csv'
            demo_archive = output / 'sample-data'
            imported = import_file(sample, demo_archive)
            print(json.dumps(imported, ensure_ascii=False))
            summary = build(output / 'unused.db', output, [demo_archive])
        elif args.action == 'open':
            if not (output / 'index.html').is_file():
                raise ValueError('还没有生成网页，请先运行 import 或 build')
            summary = {'site': str(output / 'index.html')}
        else:
            if args.action == 'import':
                if not args.file:
                    raise ValueError('请指定 CSV 或 JSON 文件')
                print(json.dumps(import_file(args.file.expanduser(), archive, args.contributor), ensure_ascii=False))
            archives = ([archive] if (archive / 'catalog.json').exists() else [])
            archives.extend(p.expanduser().resolve() for p in args.archive)
            if any(p.resolve() == output for p in archives):
                raise ValueError('网页输出目录不能与原始归档目录相同')
            summary = build(Path(DB_PATH), output, archives)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if not args.no_open:
            webbrowser.open((output / 'index.html').as_uri())
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
