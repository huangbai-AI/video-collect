import sys,unittest
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from douyin_keyword_search import parse_card
from keyword_search import qualify
class DouyinSearchTest(unittest.TestCase):
 def test_card_and_filter_evidence(self):
  debug={'ui_filter_full_applied':True,'sort_evidence':'最多点赞 KlEyP1lp HjptjtzN','week_evidence':'一周内 KlEyP1lp HjptjtzN'}
  row=parse_card({'url':'https://www.douyin.com/video/1234567890','text':'合集\n01:28:02\n3.8万\nAI视频制作教程\n@示例作者\n1天前'},'AI教程','2026-10-06T12:00:00+08:00',debug)
  self.assertEqual(row['likes'],38000);self.assertEqual(row['author'],'示例作者');self.assertEqual(row['published_label'],'1天前');self.assertEqual(row['publish_time'],'')
  self.assertIsNone(qualify(row,datetime.now(timezone.utc)))
  row['search_debug']={**debug,'week_evidence':'一周内 KlEyP1lp'}
  self.assertIsNotNone(qualify(row,datetime.now(timezone.utc)))
 def test_no_video_or_unknown_likes_not_imported(self):
  self.assertIsNone(parse_card({'url':'https://www.douyin.com/video/123','text':'00:10\n未知\nAI\n@示例\n今天'},'AI','',{}))
  self.assertIsNone(parse_card({'url':'https://www.douyin.com/user/123','text':'00:10\n2500\nAI\n@示例\n今天'},'AI','',{}))
if __name__=='__main__':unittest.main()
