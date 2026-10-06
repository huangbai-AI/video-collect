"""连接选题搜索项目：运行站内搜索，核验门槛，人工审核后导入中台。"""
from __future__ import annotations
import argparse,json,subprocess,sys,tempfile
from datetime import datetime,timedelta
from pathlib import Path
from import_links import import_file,configure_output
from build_unified_library import build
from store import DATA_DIR,DB_PATH
KEYWORDS=['AI 视频','AI','AI教程','AI工具','Coding','编程','Vibe Coding','AI 视频教程','AIGC','AI 设计']

def qualify(row,now,min_likes=2000,days=7):
    try: likes=int(row.get('likes'))
    except (TypeError,ValueError): return '点赞数未知'
    if likes<min_likes:return '低于点赞门槛'
    debug=row.get('search_debug') or {}
    if debug.get('login_required'):return '登录或验证未完成'
    stamp=row.get('publish_time') or row.get('published_at')
    if stamp:
        try:
            published=datetime.fromisoformat(str(stamp).replace('Z','+00:00'))
            if published.tzinfo is None: published=published.replace(tzinfo=now.tzinfo)
        except ValueError:return '发布时间无法识别'
        if not now-timedelta(days=days)<=published<=now:return '不在时间范围'
    elif not (row.get('platform')=='xiaohongshu' and debug.get('ui_filter_full_applied') is True):
        return '缺少发布时间或已生效的时间筛选证据'
    return None

def prepare(payload,now=None,min_likes=2000,days=7):
    now=now or datetime.now().astimezone()
    review=[]
    for row in payload.get('items',[]):
        item=dict(row);reason=qualify(item,now,min_likes,days)
        item.update(decision='excluded' if reason else 'pending',review_reason=reason or '',origins=['search'],source_type='search',published_at=item.get('publish_time') or item.get('published_at',''),month=item.get('captured_at',now.isoformat())[:7])
        review.append(item)
    return {'status':'needs_review','rules':{'keywords':KEYWORDS,'days':days,'min_likes':min_likes},'platform_results':payload.get('platform_results',[]),'items':review}

def approved_rows(payload):
    result=[]
    for row in payload.get('items',[]):
        if row.get('decision')!='keep':continue
        if not row.get('review_reason','').strip():raise ValueError('保留条目必须填写筛选理由')
        captured=row.get('captured_at')
        if not captured:raise ValueError('缺少真实抓取时间')
        stamp=datetime.fromisoformat(captured.replace('Z','+00:00'))
        if stamp.tzinfo is None:stamp=stamp.astimezone()
        reason=qualify(row,stamp,payload.get('rules',{}).get('min_likes',2000),payload.get('rules',{}).get('days',7))
        if reason:raise ValueError('保留条目不符合规则：'+reason)
        x=dict(row);x['origins']=['search'];x['published_at']=row.get('publish_time') or row.get('published_at','');result.append(x)
    return result

def main():
    configure_output();p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    r=sub.add_parser('run');r.add_argument('--project',type=Path,required=True,help='现有选题搜索项目目录');r.add_argument('--python',type=Path);r.add_argument('--out',type=Path,required=True)
    r=sub.add_parser('prepare');r.add_argument('file',type=Path);r.add_argument('--out',type=Path,required=True)
    r=sub.add_parser('import');r.add_argument('file',type=Path);r.add_argument('--output',type=Path,default=Path.home()/'video-collect-site')
    a=p.parse_args()
    if a.action=='run':
        project=a.project.expanduser().resolve();backend=project/'backend' if (project/'backend').is_dir() else project
        python=a.python.expanduser().resolve() if a.python else backend/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
        if not python.is_file():p.error('找不到搜索项目的 Python，请用 --python 指定')
        worker=Path(__file__).with_name('keyword_search_worker.py')
        subprocess.run([str(python),str(worker),'--backend',str(backend),'--out',str(a.out.expanduser().resolve())],check=True)
    elif a.action=='prepare':
        result=prepare(json.loads(a.file.read_text(encoding='utf-8')));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('已生成候选审核文件；确认相关性后填写 decision=keep 或 excluded 和 review_reason。')
    else:
        rows=approved_rows(json.loads(a.file.read_text(encoding='utf-8')))
        with tempfile.TemporaryDirectory() as t:
            source=Path(t)/'approved.json';source.write_text(json.dumps(rows,ensure_ascii=False),encoding='utf-8')
            archive=Path(DATA_DIR)/'imports';print(json.dumps(import_file(source,archive),ensure_ascii=False));print(json.dumps(build(Path(DB_PATH),a.output,[archive]),ensure_ascii=False))
if __name__=='__main__':main()
