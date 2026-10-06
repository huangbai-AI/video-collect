"""通过独立的小号浏览器试抓抖音站内搜索；不下载媒体、不发送通知。"""
from __future__ import annotations
import argparse,json,subprocess,time,re
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from store import DATA_DIR
from import_links import configure_output
from keyword_search import KEYWORDS
SESSION='video-collect-douyin-small'

def parse_card(card,keyword,stamp,debug):
 lines=card['text'].splitlines()
 pos=next((i for i,s in enumerate(lines) if re.fullmatch(r'(?:\d{1,2}:)?\d{1,2}:\d{2}',s)),None)
 if pos is None or len(lines)<=pos+3:return None
 label=lines[pos+1]
 try:likes=int(Decimal(label.removesuffix('万'))*(10000 if label.endswith('万') else 1))
 except Exception:return None
 author=next((i for i,s in enumerate(lines[pos+2:],pos+2) if s.startswith('@')),None)
 if author is None:return None
 title=' '.join(lines[pos+2:author]);url=card['url']
 if not re.fullmatch(r'https://www\.douyin\.com/video/\d+',url) or not title:return None
 return dict(platform='douyin',url=url,title=title,description=title,author=lines[author].lstrip('@'),likes=likes,likes_label=label,likes_approximate=label.endswith('万'),publish_time='',published_label=lines[-1],captured_at=stamp,keyword=keyword,search_debug=debug)

def collect(cli,out,keywords,delay=12):
 out.mkdir(parents=True,exist_ok=True)
 result=dict(started_at=datetime.now().astimezone().isoformat(),status='running',items=[],platform_results=[])
 code=Path(__file__).with_name('collectors').joinpath('douyin_search.playwright.js').read_text(encoding='utf-8')
 def save():
  tmp=out/'search_results.tmp';tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(out/'search_results.json')
 for keyword in keywords:
  print('搜索',keyword,flush=True)
  try:
   proc=subprocess.run([cli,'--session',SESSION,'run-code',code.replace('__KEYWORD__',json.dumps(keyword))],capture_output=True,text=True,encoding='utf-8',timeout=90)
   if proc.returncode or '### Result\n' not in proc.stdout:raise RuntimeError('浏览器未完成搜索；先运行 login 并在独立窗口登录小号')
   data=json.JSONDecoder().raw_decode(proc.stdout.split('### Result\n',1)[1])[0]
   if data.get('blocked') or data.get('filter_failed'):
    result['platform_results'].append(dict(platform='douyin',keyword=keyword,status='blocked' if data.get('blocked') else 'filter_failed'));break
   debug=dict(ui_filter_full_applied=True,sort_evidence=data['sort'],week_evidence=data['week'])
   stamp=datetime.now().astimezone().isoformat(timespec='seconds')
   rows=[x for card in data['items'] if (x:=parse_card(card,keyword,stamp,debug))]
   result['items']+=rows;result['platform_results'].append(dict(platform='douyin',keyword=keyword,status='ok',found=len(rows),above_threshold=sum(x['likes']>=2000 for x in rows)))
   save();print('返回',len(rows),flush=True);time.sleep(max(12,delay))
  except Exception as exc:
   result['platform_results'].append(dict(platform='douyin',keyword=keyword,status='failed',error=str(exc)[:180]));break
 result['status']='finished' if len(result['platform_results'])==len(keywords) and all(x['status']=='ok' for x in result['platform_results']) else 'partial'
 result['finished_at']=datetime.now().astimezone().isoformat();save();return result

def main():
 configure_output();p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['login','run']);p.add_argument('--cli',default='playwright-cli');p.add_argument('--profile',type=Path,default=Path(DATA_DIR)/'browser-profiles/douyin-small');p.add_argument('--out',type=Path);p.add_argument('--keyword',action='append');a=p.parse_args()
 if a.action=='login':
  subprocess.run([a.cli,'--session',SESSION,'open','https://www.douyin.com/','--browser','chrome','--headed','--profile',str(a.profile.expanduser().resolve())],check=True)
  print('请在独立窗口扫码登录小号并自行完成验证；完成后运行 run。不要使用大号。')
 else:
  if not a.out:p.error('run 需要 --out 指定私有轮次目录')
  result=collect(a.cli,a.out.expanduser().resolve(),a.keyword or KEYWORDS);print('本轮状态：',result['status'])
if __name__=='__main__':main()
