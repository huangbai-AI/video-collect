"""Archive every image and the text of one Xiaohongshu image note."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def ensure_yt_dlp() -> None:
    try:
        import yt_dlp  # noqa: F401
    except ModuleNotFoundError:
        executable = shutil.which('yt-dlp')
        if not executable:
            raise RuntimeError('yt-dlp is required')
        first_line = Path(executable).read_text(encoding='utf-8').splitlines()[0]
        if not first_line.startswith('#!'):
            raise RuntimeError('cannot find the yt-dlp Python environment')
        interpreter = first_line[2:].strip().split()[0]
        if os.path.abspath(interpreter) == os.path.abspath(sys.executable):
            raise RuntimeError('yt-dlp module is unavailable in its own environment')
        os.execv(interpreter, [interpreter, __file__, *sys.argv[1:]])


def image_kind(data: bytes) -> str | None:
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    if data[4:12] in (b'ftypavif', b'ftypavis'):
        return 'avif'
    return None


def fetch_image(urls: list[str], target: Path, proxy: str) -> Path:
    for url in urls:
        parsed = urlparse(url)
        if parsed.hostname is None or not parsed.hostname.endswith('.xhscdn.com'):
            continue
        if parsed.scheme not in {'http', 'https'}:
            continue
        tmp = target.with_suffix('.part')
        command = ['curl', '-fsSL', '--retry', '2', '--max-time', '35',
                   '--proto', '=https', '--proto-redir', '=https',
                   '-A', 'Mozilla/5.0', '-e', 'https://www.xiaohongshu.com/',
                   '-o', str(tmp)]
        if proxy:
            command += ['--proxy', proxy]
        command.append(url.replace('http://', 'https://', 1))
        result = subprocess.run(command, capture_output=True, text=True, timeout=100)
        if result.returncode == 0 and tmp.exists() and tmp.stat().st_size > 1000:
            with tmp.open('rb') as handle:
                kind = image_kind(handle.read(16))
            if kind:
                actual = target.with_suffix('.' + kind)
                tmp.replace(actual)
                return actual
        tmp.unlink(missing_ok=True)
    raise RuntimeError('image download failed')


def archive(url: str, out: Path, proxy: str) -> dict:
    ensure_yt_dlp()
    from yt_dlp import YoutubeDL
    from yt_dlp.extractor.xiaohongshu import XiaoHongShuIE

    out.mkdir(parents=True, exist_ok=True)
    manifest = out / 'note.json'
    if manifest.exists():
        old = json.loads(manifest.read_text(encoding='utf-8'))
        if old.get('images') and all((out / item['file']).is_file() for item in old['images']):
            return {'id': old['id'], 'count': len(old['images']), 'out': str(out), 'reused': True}

    with YoutubeDL({'proxy': proxy or None, 'quiet': True, 'no_warnings': True}) as ydl:
        info = XiaoHongShuIE(ydl)._real_extract(url)
    if info.get('formats'):
        raise RuntimeError('this note has video formats; use the video downloader')
    thumbnails = info.get('thumbnails') or []
    groups: dict[str, list[str]] = {}
    for image in thumbnails:
        media_url = image.get('url')
        if not media_url:
            continue
        asset = urlparse(media_url).path.rsplit('/', 1)[-1].split('!', 1)[0]
        if asset:
            groups.setdefault(asset, []).append(media_url)
    if not groups:
        raise RuntimeError('no images found in note')

    images = []
    for number, urls in enumerate(groups.values(), 1):
        base = out / f'{number:02d}'
        existing = next((p for suffix in ('jpg', 'png', 'webp', 'avif')
                         if (p := base.with_suffix('.' + suffix)).is_file()), None)
        path = existing or fetch_image(urls, base, proxy)
        images.append({'file': path.name, 'bytes': path.stat().st_size})
    data = {
        'id': info['id'], 'source': url, 'title': info.get('title') or '',
        'description': info.get('description') or '', 'tags': info.get('tags') or [],
        'images': images,
    }
    tmp = manifest.with_suffix('.json.part')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(manifest)
    return {'id': data['id'], 'count': len(images), 'out': str(out), 'reused': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--proxy', default='')
    args = parser.parse_args()
    print(json.dumps(archive(args.url, args.out, args.proxy), ensure_ascii=False))


if __name__ == '__main__':
    main()
