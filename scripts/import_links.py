"""导入 CSV / JSON 标题与链接，保留月份、来源和收录人。只写本地归档。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

PLATFORMS = {
    'instagram.com': 'instagram', 'xiaohongshu.com': 'xiaohongshu',
    'xhslink.com': 'xiaohongshu', 'douyin.com': 'douyin',
    'x.com': 'x', 'twitter.com': 'x', 'tiktok.com': 'tiktok',
    'bilibili.com': 'bilibili', 'b23.tv': 'bilibili',
    'youtube.com': 'youtube', 'youtu.be': 'youtube',
    'feishu.cn': 'feishu', 'larksuite.com': 'feishu', 'weixin.qq.com': 'wechat',
}
ALIASES = {'小红书': 'xiaohongshu', 'xhs': 'xiaohongshu', '抖音': 'douyin',
           '飞书': 'feishu', 'B站': 'bilibili', 'B 站': 'bilibili',
           '视频号': 'wechat', '网页': 'web', 'X': 'x', 'Instagram': 'instagram',
           'YouTube': 'youtube', 'TikTok': 'tiktok'}
ORIGINS = {'收藏': 'favorite', '收藏夹': 'favorite', 'fav': 'favorite',
           'saved': 'favorite', 'favorite_collection': 'favorite',
           '点赞': 'like', 'liked': 'like', '搜索': 'search',
           '飞书选题库': 'knowledge', '知识库': 'knowledge', '导入': 'import'}


def platform_of(url: str) -> str:
    host = (urlsplit(url).hostname or '').lower()
    return next((p for d, p in PLATFORMS.items() if host == d or host.endswith('.' + d)), 'web')


def safe_url(url: str) -> str:
    if not isinstance(url, str) or any(ord(c) < 32 for c in url):
        raise ValueError('链接含有非法字符')
    parts = urlsplit(url.strip())
    if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('链接必须为不含账号密码的 http / https 地址')
    return url.strip()


def identity(platform: str, url: str) -> str:
    patterns = {'instagram': r'/(?:p|reel)/([^/?#]+)', 'x': r'/status/(\d+)',
                'douyin': r'/(?:video|note)/(\d+)', 'bilibili': r'/video/([^/?#]+)',
                'xiaohongshu': r'/(?:explore|discovery/item)/([^/?#]+)',
                'tiktok': r'/video/(\d+)'}
    match = re.search(patterns.get(platform, r'(?!)'), urlsplit(url).path)
    if match:
        return match.group(1)
    parts = urlsplit(url)
    # Generic pages and Feishu record links may differ only by query or fragment.
    canonical = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), parts.query, parts.fragment))
    return hashlib.sha256(canonical.encode()).hexdigest()[:24]


def first(row, *keys, default=''):
    return next((row[k] for k in keys if row.get(k) not in (None, '')), default)


def string_list(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [s.strip() for s in str(value or '').split(',') if s.strip()]


def normalize(row: dict, contributor='', now=None) -> dict:
    url = safe_url(first(row, 'url', '链接', '原帖链接', '参考链接', 'source'))
    platform = first(row, 'platform', '平台', default=platform_of(url))
    platform = ALIASES.get(platform, str(platform).lower())
    if platform not in set(PLATFORMS.values()) | {'web'}:
        platform = platform_of(url)
    captured = str(first(row, 'captured_at', 'first_seen', '抓取时间', '入库时间',
                         default=now or datetime.now().astimezone().isoformat(timespec='seconds')))
    raw_month = str(first(row, 'month', '月份'))
    month = '未标月份'
    if raw_month and raw_month != month:
        match = re.fullmatch(r'(20\d{2})[-/年](\d{1,2})月?', raw_month.strip())
        if not match or not 1 <= int(match[2]) <= 12:
            raise ValueError('月份应为 YYYY-MM，例如 2026-09')
        month = f'{match[1]}-{int(match[2]):02d}'
    elif not raw_month and re.match(r'20\d{2}-(0[1-9]|1[0-2])', captured):
        month = captured[:7]
    origins = string_list(first(row, 'origins', 'source_type', '获取来源', '来源', 'list', 'lists', default='import'))
    origins = list(dict.fromkeys(ORIGINS.get(o, o) if ORIGINS.get(o, o) in {'like', 'favorite', 'search', 'knowledge', 'import'} else 'import' for o in origins))
    people = string_list(first(row, 'contributors', 'contributor', '收录人'))
    if contributor and contributor not in people:
        people.append(contributor)
    return {
        'vid': identity(platform, url), 'platform': platform, 'url': url,
        'title': str(first(row, 'title_zh', 'title', '标题', '内容', default=url))[:1000],
        'author': str(first(row, 'author', '作者', '原帖作者'))[:200],
        'month': month, 'captured_at': captured, 'origins': origins,
        'contributors': people, 'kind': str(first(row, 'kind', '类型', default='选题'))[:40],
        'likes': first(row, 'likes', '点赞数', default=None),
        'published_at': str(first(row, 'published_at', '发布时间')),
        'description': str(first(row, 'description', 'caption', '文案'))[:20000],
        'keyword': str(first(row, 'keyword', '关键词'))[:1000],
    }


def read_rows(path: Path) -> list:
    with path.open(encoding='utf-8-sig', newline='') as f:
        if path.suffix.lower() == '.csv':
            rows = list(csv.DictReader(f))
        else:
            rows = json.load(f)
            if isinstance(rows, dict):
                rows = rows.get('items')
    if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
        raise ValueError('文件应为 JSON 条目数组、{items:[...]} 或带表头的 CSV')
    return rows


def import_file(source: Path, archive: Path, contributor='') -> dict:
    # Validate the entire batch before touching any existing archive.
    incoming = []
    for index, row in enumerate(read_rows(source), 1):
        try:
            incoming.append(normalize(row, contributor))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f'第 {index} 条无法导入：{exc}') from exc
    target = archive / 'catalog.json'
    archive.mkdir(parents=True, exist_ok=True)
    lock = archive / '.import.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('另一个导入正在运行；请稍后重试') from None
    os.close(fd)
    tmp = None
    try:
        old = json.loads(target.read_text(encoding='utf-8')) if target.exists() else []
        records = {(r['platform'], r['vid']): r for r in old}
        added = 0
        for row in incoming:
            key = row['platform'], row['vid']
            if key not in records:
                records[key] = row
                added += 1
            else:
                existing = records[key]
                # First topic month/title are retained; provenance is cumulative.
                for field in ('origins', 'contributors'):
                    existing[field] = list(dict.fromkeys(existing.get(field, []) + row[field]))
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=archive, delete=False) as f:
            tmp = Path(f.name)
            json.dump(list(records.values()), f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, target)
        return {'received': len(incoming), 'added': added, 'existing': len(incoming)-added, 'total': len(records)}
    finally:
        if tmp and tmp.exists():
            tmp.unlink()
        lock.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--contributor', default='')
    args = parser.parse_args()
    try:
        print(json.dumps(import_file(args.file.expanduser(), args.out.expanduser(), args.contributor), ensure_ascii=False))
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
