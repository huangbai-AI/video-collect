"""Run the existing topic search adapters once, without outgoing messages."""
import asyncio,json,sys,logging,sqlite3,os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
for stream in (sys.stdout,sys.stderr):
 if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
parser=argparse.ArgumentParser()
parser.add_argument('--backend',type=Path,required=True)
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
PROJECT=args.backend.expanduser().resolve()
sys.path.insert(0,str(PROJECT));os.chdir(PROJECT)
from config import settings
from scrapers.registry import create_scrapers
out=args.out.expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
logging.basicConfig(level=logging.WARNING)
settings.scrape_retry_attempts=1
settings.xhs_login_recover_wait_seconds=0
settings.feishu_webhook_url='';settings.feishu_app_id='';settings.feishu_app_secret='';settings.feishu_chat_id=''
settings.xhs_parallel_tabs=1
scrapers=create_scrapers()
async def stop_on_risk(self,page,keyword,stage,flags):
 self.last_search_debug.update(login_required=True,risk_stage=stage,risk_flags=flags,source='stopped_after_risk')
 return False
from types import MethodType
scrapers['xiaohongshu']._handle_login_required=MethodType(stop_on_risk,scrapers['xiaohongshu'])
c=sqlite3.connect('file:data/topic_assistant.db?mode=ro',uri=True);c.row_factory=sqlite3.Row
keywords=[dict(r) for r in c.execute('select id,keyword,platforms,min_likes from keywords where enabled=1 order by id')];c.close()
if not keywords: raise SystemExit('没有启用的关键词，请先在搜索项目中配置')
result={'started_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'keywords':keywords,'platform_results':[],'items':[],'status':'running','notifications':False}
def save():
 tmp=out/'search_results.tmp';tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2));tmp.replace(out/'search_results.json')
async def main():
 save()
 xhs=scrapers['xiaohongshu'];names=[r['keyword'] for r in keywords if 'xiaohongshu' in json.loads(r['platforms'])]
 try:await asyncio.wait_for(xhs.prefetch(names,20),timeout=600)
 except Exception as e:
  result['platform_results'].append({'platform':'xiaohongshu','stage':'prefetch','status':'failed','error':type(e).__name__+': '+str(e)[:300]})
  # Do not reopen the profile after a failed prefetch.
  names=[]
 for platform in ['xiaohongshu','bilibili']:
  stopped=False
  for kw in keywords:
   if platform not in json.loads(kw['platforms']):continue
   if stopped or platform=='xiaohongshu' and not names:
    result['platform_results'].append({'platform':platform,'keyword':kw['keyword'],'status':'skipped_after_failure'});save();continue
   print('开始',platform,kw['keyword'],flush=True)
   try:
    batch=await asyncio.wait_for(scrapers[platform].search_and_wrap(kw['keyword'],20),timeout=120)
    debug=dict(getattr(scrapers[platform],'last_search_debug',{}))
    safe_debug={k:v for k,v in debug.items() if not any(s in k.lower() for s in ['cookie','token','secret','html','screenshot'])}
    risk=bool(debug.get('login_required'))
    if risk:stopped=True
    valid=[x for x in batch.items if x.likes>=kw['min_likes']]
    result['platform_results'].append({'platform':platform,'keyword':kw['keyword'],'status':'blocked' if risk else 'ok' if batch.items else 'empty_or_failed','found':len(batch.items),'above_threshold':len(valid),'debug':safe_debug})
    for x in valid:
     d=x.model_dump();d['captured_at']=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d %H:%M:%S');d['minimum_likes']=kw['min_likes'];d['search_debug']=safe_debug;result['items'].append(d)
    print('结果',platform,kw['keyword'],len(batch.items),'达标',len(valid),'风险',risk,flush=True)
   except Exception as e:
    result['platform_results'].append({'platform':platform,'keyword':kw['keyword'],'status':'failed','error':type(e).__name__+': '+str(e)[:300]});print('失败',platform,kw['keyword'],type(e).__name__,flush=True)
    if platform=='xiaohongshu':stopped=True
   save()
   if platform=='bilibili':await asyncio.sleep(3)
 result['status']='finished' if all(x.get('status')=='ok' for x in result['platform_results']) else 'partial';result['finished_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();save()
 print('已完成，候选',len(result['items']),flush=True)
asyncio.run(main())
