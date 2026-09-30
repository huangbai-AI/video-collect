"""把采集库和可选的媒体归档合成一个可离线打开的网页。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path

from store import DB_PATH

TEMPLATE = Path(__file__).with_name('unified_library_template.html')
PLATFORM_NAMES = {
    'instagram': 'Instagram', 'xiaohongshu': '小红书', 'xhs': '小红书',
    'bilibili': 'B 站', 'douyin': '抖音', 'tiktok': 'TikTok', 'x': 'X',
    'youtube': 'YouTube', 'wechat': '视频号',
}
FAVORITES = {'saved', 'fav', 'favorite_collection', 'favorite'}


def post_id(platform: str, url: str) -> str:
    patterns = {
        'instagram': r'/(?:p|reel)/([^/?#]+)',
        'bilibili': r'/video/([^/?#]+)',
        'douyin': r'/(?:video|note)/(\d+)',
        'x': r'/status/(\d+)',
    }
    match = re.search(patterns.get(platform, r'/(?:explore|discovery/item|video)/([^/?#]+)'), url)
    return match.group(1) if match else url.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1]


def base(platform: str, vid: str) -> dict:
    return {
        'id': f'{platform}:{vid}', 'platform': platform,
        'platform_label': PLATFORM_NAMES.get(platform, platform),
        'origins': [], 'source_names': [], 'title': '', 'author': '',
        'likes': None, 'comments': None, 'published_at': '', 'captured_at': '',
        'keyword': '', 'url': '', 'video': None, 'poster': None, 'images': [],
        'description': '', 'duration': None, 'media_type': 'video',
        'status': 'link', 'order': 0, 'month': '', 'kind': '媒体',
    }


def add_origin(item: dict, name: str) -> None:
    kind = 'favorite' if name in FAVORITES else 'like' if name in {'liked', 'like'} else 'search'
    label = {'favorite': '收藏', 'like': '点赞', 'search': '导入'}[kind]
    if kind not in item['origins']:
        item['origins'].append(kind)
    source = f"{item['platform_label']} · {label}"
    if source not in item['source_names']:
        item['source_names'].append(source)


def media_path(archive: Path, value: str | None, output: Path) -> str | None:
    if not value:
        return None
    root = archive.resolve()
    target = (archive / value).resolve()
    if not target.is_file() or not target.is_relative_to(root):
        return None
    return os.path.relpath(target, output.resolve()).replace(os.sep, '/')


def load_database(items: dict[str, dict], db_path: Path) -> None:
    if not db_path.is_file():
        return
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        for row in conn.execute('SELECT * FROM videos ORDER BY first_seen DESC'):
            platform = 'xiaohongshu' if row['platform'] == 'xhs' else row['platform']
            item = base(platform, row['vid'])
            item.update(url=row['url'] or '', title=row['title'] or '',
                        author=row['author'] or '', likes=row['likes'],
                        published_at=row['published_at'] or '',
                        captured_at=row['first_seen'] or '',
                        media_type='images' if row['type'] == 'normal' else 'video')
            for list_name in (row['lists'] or '').split(','):
                if list_name:
                    add_origin(item, list_name)
            items[item['id']] = item
    finally:
        conn.close()


def load_archives(items: dict[str, dict], archives: list[Path], output: Path) -> None:
    for archive in archives:
        manifest = archive / 'catalog.json'
        if not manifest.is_file():
            raise FileNotFoundError(f'归档缺少 catalog.json：{archive}')
        rows = json.loads(manifest.read_text(encoding='utf-8'))
        if isinstance(rows, dict):
            rows = rows.get('items', [])
        if not isinstance(rows, list):
            raise ValueError(f'归档格式有误：{manifest}')
        for number, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                continue
            url = row.get('url') or row.get('source') or ''
            if not url:
                continue
            platform = row.get('platform') or ('x' if 'x.com/' in url else 'instagram' if 'instagram.com/' in url else 'xiaohongshu' if 'xiaohongshu.com/' in url else 'web')
            platform = 'xiaohongshu' if platform == 'xhs' else platform
            vid = str(row.get('vid') or post_id(platform, url))
            key = f'{platform}:{vid}'
            item = items.setdefault(key, base(platform, vid))
            video = media_path(archive, row.get('video'), output)
            images = [path for value in row.get('images', [])
                      if (path := media_path(archive, value, output))]
            poster = media_path(archive, row.get('poster'), output)
            item.update(
                url=url, title=row.get('title_zh') or row.get('title') or item['title'],
                author=row.get('author_display') or row.get('author') or item['author'],
                likes=row.get('likes') if row.get('likes') is not None else item['likes'],
                comments=row.get('comments'),
                published_at=row.get('published_at') or item['published_at'],
                captured_at=row.get('captured_at') or item['captured_at'],
                keyword=row.get('keyword') or item['keyword'],
                description=row.get('description') or row.get('caption') or item['description'],
                duration=row.get('duration'), order=row.get('order') or row.get('number') or row.get('like_order') or number,
                video=video or item['video'], poster=poster or item['poster'],
                images=images or item['images'],
                media_type='images' if images else 'video',
            )
            item['status'] = 'downloaded' if item['video'] else 'images' if item['images'] else 'link'
            add_origin(item, row.get('source_type') or row.get('list') or 'import')


def build(db_path: Path, output: Path, archives: list[Path]) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    items: dict[str, dict] = {}
    load_database(items, db_path)
    load_archives(items, archives, output)
    for item in items.values():
        stamp = item['captured_at'] or ''
        item['month'] = stamp[:7] if re.fullmatch(r'20\d{2}-\d{2}', stamp[:7]) else '未标月份'
    catalog = sorted(items.values(), key=lambda x: (x['captured_at'], x['id']), reverse=True)
    data = json.dumps(catalog, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    page = TEMPLATE.read_text(encoding='utf-8').replace('__CATALOG__', data).replace('__SCOPE_NOTICE__', '')
    (output / 'index.html').write_text(page, encoding='utf-8')
    (output / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    summary = {
        'total': len(catalog),
        'offline_videos': sum(x['status'] == 'downloaded' for x in catalog),
        'offline_images': sum(x['status'] == 'images' for x in catalog),
        'link_only': sum(x['status'] == 'link' for x in catalog),
        'platforms': dict(Counter(x['platform_label'] for x in catalog)),
        'site': str(output / 'index.html'),
    }
    (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path(DB_PATH))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--archive', type=Path, action='append', default=[], help='可重复指定含 catalog.json 的归档目录')
    args = parser.parse_args()
    print(json.dumps(build(args.db.expanduser(), args.output.expanduser(),
                           [path.expanduser() for path in args.archive]), ensure_ascii=False, indent=2))
