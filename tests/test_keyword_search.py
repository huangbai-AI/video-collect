import sys,unittest
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from keyword_search import qualify,prepare,approved_rows
NOW=datetime(2026,10,6,12,tzinfo=timezone(timedelta(hours=8)))
class SearchReviewTest(unittest.TestCase):
 def row(self,**kw):
  return dict(platform='bilibili',title='AI 做网站',url='https://bilibili.com/video/BVexample',likes=2500,published_at='2026-10-05T10:00:00+08:00',captured_at=NOW.isoformat(),**kw)
 def test_threshold_dates_and_evidence(self):
  x=self.row();self.assertIsNone(qualify(x,NOW))
  for patch in [{'likes':None},{'likes':1999},{'published_at':'2026-09-01'},{'published_at':'2026-10-07'},{'published_at':'bad'},{'published_at':''}]:
   self.assertIsNotNone(qualify({**x,**patch},NOW))
  x.update(platform='xiaohongshu',published_at='',search_debug={'ui_filter_full_applied':True})
  self.assertIsNone(qualify(x,NOW));x['search_debug']['login_required']=True;self.assertIsNotNone(qualify(x,NOW))
 def test_prepare_preserves_date_and_requires_review(self):
  p=prepare({'items':[self.row()]},NOW)
  self.assertEqual(p['items'][0]['published_at'],self.row()['published_at']);self.assertEqual(approved_rows(p),[])
  x=p['items'][0];x['decision']='keep'
  with self.assertRaises(ValueError):approved_rows(p)
  x['review_reason']='标题明确是AI建站案例；未观看视频'
  self.assertEqual(len(approved_rows(p)),1)
  x['likes']=100
  with self.assertRaises(ValueError):approved_rows(p)
 def test_import_uses_capture_time_not_later_review_time(self):
  p=prepare({'items':[self.row()]},NOW);p['items'][0].update(decision='keep',review_reason='具体制作案例')
  self.assertEqual(approved_rows(p)[0]['origins'],['search'])
if __name__=='__main__':unittest.main()
