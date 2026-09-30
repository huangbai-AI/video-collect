import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_unified_library as site
import store


class LibraryTest(unittest.TestCase):
    def test_merges_collected_link_with_verified_local_media(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / 'data' / 'videos.db'
            conn = store.connect(str(db))
            platform, list_name, items = store.validate({
                'platform': 'instagram', 'list': 'liked',
                'items': [{'vid': 'example', 'url': 'https://www.instagram.com/p/example/',
                           'title': '示例帖子'}],
            })
            store.ingest(conn, platform, list_name, items)
            conn.close()

            archive = root / 'archive'
            archive.mkdir()
            (archive / 'video.mp4').write_bytes(b'fixture')
            (archive / 'catalog.json').write_text(json.dumps([{
                'platform': 'instagram', 'vid': 'example',
                'url': 'https://www.instagram.com/p/example/',
                'video': 'video.mp4', 'author': 'creator',
            }]), encoding='utf-8')
            output = root / 'site'
            result = site.build(db, output, [archive])
            entry = json.loads((output / 'catalog.json').read_text(encoding='utf-8'))[0]

            self.assertEqual(result['total'], 1)
            self.assertEqual(result['offline_videos'], 1)
            self.assertEqual(entry['status'], 'downloaded')
            self.assertEqual(entry['origins'], ['like', 'search'])
            self.assertEqual((output / entry['video']).resolve(), (archive / 'video.mp4').resolve())
            self.assertIn('示例帖子', (output / 'index.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
