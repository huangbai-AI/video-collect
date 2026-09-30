import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from import_links import import_file, normalize, identity
from build_unified_library import build, media_path


class ImportTest(unittest.TestCase):
    def test_demo_on_non_utf8_console(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(repo / 'scripts/library.py'),
                                     'demo', '--output', temp, '--no-open'],
                                    env={**os.environ, 'PYTHONIOENCODING': 'ascii'},
                                    capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8'))
            self.assertIn('网页', result.stdout.decode('utf-8'))

    def test_chinese_csv_and_repeat_preserve_month_and_merge_contributors(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'topics.csv'
            source.write_text('标题,链接,月份,来源\n选题,https://www.instagram.com/reel/demo/,2026-08,收藏\n', encoding='utf-8-sig')
            self.assertEqual(import_file(source, root / 'archive', '甲')['added'], 1)
            self.assertEqual(import_file(source, root / 'archive', '乙')['added'], 0)
            build(root / 'missing.db', root / 'site', [root / 'archive'])
            item = json.loads((root / 'site/catalog.json').read_text(encoding='utf-8'))[0]
            self.assertEqual(item['month'], '2026-08')
            self.assertEqual(item['contributors'], ['甲', '乙'])
            self.assertEqual(item['origins'], ['favorite'])
            self.assertEqual(item['status'], 'link')

    def test_invalid_batch_does_not_partially_import(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'records.json'
            source.write_text(json.dumps([{'title': 'valid', 'url': 'https://example.com/a'}]))
            import_file(source, root / 'archive')
            original = (root / 'archive/catalog.json').read_bytes()
            source.write_text(json.dumps([{'url': 'https://example.com/b'}, {'url': 'javascript:alert(1)'}]))
            with self.assertRaises(ValueError):
                import_file(source, root / 'archive')
            self.assertEqual(original, (root / 'archive/catalog.json').read_bytes())

    def test_distinct_pages_and_feishu_records_do_not_collide(self):
        self.assertNotEqual(identity('web', 'https://one.example/a'), identity('web', 'https://two.example/a'))
        self.assertNotEqual(identity('feishu', 'https://demo.feishu.cn/base/a?record=1'), identity('feishu', 'https://demo.feishu.cn/base/a?record=2'))
        self.assertEqual(identity('instagram', 'https://instagram.com/p/example/?share=one'), identity('instagram', 'https://instagram.com/reel/example/'))

    def test_url_and_month_validation(self):
        for url in ['javascript:alert(1)', 'file:///private/file', 'https://user:pass@example.com', 'https://example.com/\nx']:
            with self.assertRaises(ValueError):
                normalize({'url': url})
        with self.assertRaises(ValueError):
            normalize({'url': 'https://example.com', 'month': '2026-13'})
        self.assertEqual(normalize({'url': 'https://example.com', 'month': '2026年9月'})['month'], '2026-09')

    def test_script_escaping_and_media_path_confinement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'archive'
            archive.mkdir()
            (root / 'outside.mp4').write_bytes(b'fixture')
            self.assertIsNone(media_path(archive, '../outside.mp4', root / 'site'))
            (archive / 'catalog.json').write_text(json.dumps([{'url': 'https://example.com/a', 'title': '</script><script>alert(1)</script>', 'month': '2026-08', 'origins': ['knowledge']}]))
            build(root / 'absent.db', root / 'site', [archive])
            page = (root / 'site/index.html').read_text(encoding='utf-8')
            self.assertNotIn('</script><script>alert(1)</script>', page)
            item = json.loads((root / 'site/catalog.json').read_text(encoding='utf-8'))[0]
            self.assertEqual(item['origins'], ['knowledge'])


if __name__ == '__main__':
    unittest.main()
