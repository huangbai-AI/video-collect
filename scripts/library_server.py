"""Local library + explicitly started Feishu candidate sync. No credentials in pages."""
import argparse, functools, json, os, re, subprocess, threading, time, uuid
from collections import defaultdict
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

CATEGORIES=['AIGC 教程','AI Coding','AI办公（泛 AI 效率 工具）','AI 设计','AI内容','其他灵感']

def classify(x):
    s=(x.get('title','')+' '+x.get('description','')).lower()
    if any(v in s for v in ['微信记录','办公','workbuddy','知识库']): return CATEGORIES[2]
    if any(v in s for v in ['网站','作品集','claude code','three.js','复刻','编程','coding']): return CATEGORIES[1]
    if any(v in s for v in ['广告','arcads','生成 ai','ai 视频']): return CATEGORIES[0]
    return CATEGORIES[3]

def post_key(url):
    u=urlparse(url);h=u.hostname or '';p=u.path.rstrip('/')
    if 'instagram.com' in h: return 'instagram:'+p.split('/')[-1]
    if h.endswith('x.com') or h.endswith('twitter.com'): return 'x:'+p.split('/')[-1]
    if 'xiaohongshu.com' in h: return 'xiaohongshu:'+p.split('/')[-1]
    if 'tiktok.com' in h: return 'tiktok:'+p.split('/')[-1]
    return h+p

class SyncEngine:
    def __init__(self, root, config):
        self.root=Path(root).resolve();self.config=Path(config);self.dir=self.root/'feishu-sync';self.dir.mkdir(exist_ok=True)
        self.jobs={};self.lock=threading.Lock()
    def settings(self): return json.loads(self.config.read_text()) if self.config.exists() else {}
    def catalog(self):
        return {x['id']:x for x in json.loads((self.root/'catalog.json').read_text())}
    def history(self):
        p=self.dir/'history.json';return json.loads(p.read_text()) if p.exists() else {}
    def status(self):
        month=datetime.now().strftime('%Y-%m');target=self.settings().get('targets',{}).get(month)
        return {'month':month,'target':target,'configured':bool(target),'categories':CATEGORIES,
                'synced':[key.split('|',1)[1] for key in self.history() if key.startswith(month+'|')],
                'jobs':list(self.jobs.values())[-8:]}
    def cli(self,*args):
        p=subprocess.run(['lark-cli','docs',*args,'--as','user'],capture_output=True,text=True,timeout=180,cwd=self.root)
        try: value=json.loads(p.stdout or p.stderr)
        except ValueError: raise RuntimeError('飞书未返回有效结果，请检查登录或网络')
        if p.returncode or not value.get('ok'): raise RuntimeError(str(value.get('error','飞书操作失败'))[:500])
        return value
    def fetch(self,target): return self.cli('+fetch','--doc',target,'--detail','full')['data']['document']
    def start(self, requested):
        with self.lock:
            if any(j['state']=='running' for j in self.jobs.values()): raise ValueError('已有同步正在进行，请等它完成')
            current=self.status();target=current['target']
            if not target: raise ValueError('尚未配置当月飞书选题文档')
            if not isinstance(requested,list) or not 1<=len(requested)<=50: raise ValueError('每次请选择1到50条')
            catalog=self.catalog();rows=[];seen=set()
            for r in requested:
                if not isinstance(r,dict) or r.get('id') not in catalog: raise ValueError('候选不在资料库中')
                x=dict(catalog[r['id']]);
                if x['id'] in seen: continue
                seen.add(x['id']);x['category']=r.get('category') or classify(x)
                if x['category'] not in CATEGORIES: raise ValueError('选题分类不正确')
                x['content']=str(r.get('content') or x['title'])[:500];rows.append(x)
            ident=uuid.uuid4().hex;job={'id':ident,'state':'running','month':current['month'],'target':target,'total':len(rows),'done':0,'results':[]}
            self.jobs[ident]=job;threading.Thread(target=self.run,args=(job,rows),daemon=True).start();return job
    def save_job(self,job):
        p=self.dir/(job['id']+'.json');p.write_text(json.dumps(job,ensure_ascii=False,indent=2))
    def image(self,x):
        p=self.dir/'screenshots'/(re.sub(r'[^\w-]','_',x['id'])+'.png')
        if p.exists(): return p
        source=x.get('poster')
        if source and not urlparse(source).scheme:
            p=(self.root/source).resolve()
            if p.is_relative_to(self.root.parent) and p.is_file(): return p
        return None
    def record(self,job,x,kind):
        history=self.history();history[job['month']+'|'+x['id']]={'target':job['target'],'title':x['title'],'at':datetime.now().isoformat(),'result':kind}
        p=self.dir/'history.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(history,ensure_ascii=False,indent=2));tmp.replace(p)
        job['results'].append({'id':x['id'],'title':x['title'],'state':kind,'screenshot':bool(self.image(x))});job['done']+=1;self.save_job(job)
    def run(self,job,rows):
        try:
            document=self.fetch(job['target']);root=ET.fromstring('<root>'+document['content']+'</root>')
            title=''.join(root.find('title').itertext());digits=re.sub(r'\s','',title)
            if job['month'] not in digits: raise RuntimeError('目标文档月份与当前月份不一致，已停止')
            known={post_key(a.get('href','')) for a in root.iter('a') if a.get('href')}
            groups=defaultdict(list)
            for x in rows:
                if post_key(x['url']) in known: self.record(job,x,'already');continue
                known.add(post_key(x['url']));groups[x['category']].append(x)
            for category,selected in groups.items():
                document=self.fetch(job['target']);root=ET.fromstring('<root>'+document['content']+'</root>')
                section=None;anchor=None
                for child in root:
                    if child.tag.startswith('h') and child.tag[1:].isdigit(): section=''.join(child.itertext()).strip()
                    if section==category and child.tag=='table': anchor=child.get('id')
                if not anchor: raise RuntimeError('没有找到分类表格：'+category)
                body=[]
                for x in selected:
                    p=self.image(x);reference=('<img path='+quoteattr('@'+str(p))+' width="240"/>') if p else '<p>截图待补（原帖链接已同步）</p>'
                    body.append('<tr><td><p>'+escape(x['content'])+'</p></td><td>'+reference+'</td><td><p><a href='+quoteattr(x['url'])+'>'+escape(x['title'])+'</a></p></td></tr>')
                xml='<table><colgroup><col width="264"/><col width="403"/><col width="340"/></colgroup><thead><tr><th><p>内容</p></th><th><p>参考</p></th><th><p>备注</p></th></tr></thead><tbody>'+''.join(body)+'</tbody></table>'
                draft=self.dir/(job['id']+'-'+str(len(job['results']))+'.xml');draft.write_text(xml)
                write_error=None
                try: self.cli('+update','--doc',job['target'],'--command','block_insert_after','--block-id',anchor,'--content','@'+str(draft),'--revision-id',str(document['revision_id']))
                except Exception as e: write_error=e
                after=self.fetch(job['target']);afterroot=ET.fromstring('<root>'+after['content']+'</root>')
                found={post_key(a.get('href','')) for a in afterroot.iter('a') if a.get('href')}
                (self.dir/(job['id']+'-verified.json')).write_text(json.dumps(after,ensure_ascii=False))
                for x in selected:
                    if post_key(x['url']) not in found: raise RuntimeError(str(write_error or '写入后未找到原帖链接'))
                    self.record(job,x,'synced')
                if write_error: raise RuntimeError('部分内容已确认写入，请核对同步记录后重试剩余内容')
            job['state']='done'
        except Exception as e: job['state']='error';job['error']=str(e)[:600]
        self.save_job(job)

class Handler(SimpleHTTPRequestHandler):
    engine=None
    def valid_host(self): return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def reply(self,value,code=200):
        data=json.dumps(value,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if not self.valid_host(): self.reply({'error':'仅供本机使用'},403);return
        if self.path=='/api/feishu-sync':
            try:self.reply(self.engine.status())
            except Exception:self.reply({'error':'无法读取同步配置'},500)
            return
        if self.path.startswith('/api/feishu-sync/'):
            job=self.engine.jobs.get(self.path.rsplit('/',1)[-1]);self.reply(job or {'error':'任务不存在'},200 if job else 404);return
        # Private journal/config never served as website files.
        decoded=unquote(urlparse(self.path).path)
        resolved=Path(self.translate_path(self.path)).resolve()
        if resolved.is_relative_to(self.engine.dir) and not resolved.is_relative_to(self.engine.dir/'screenshots'): self.reply({'error':'不可访问'},403);return
        super().do_GET()
    def do_POST(self):
        origin=self.headers.get('Origin');expected=f'http://{self.headers.get("Host")}'
        if not self.valid_host() or origin!=expected or self.headers.get('Content-Type','').split(';')[0]!='application/json':self.reply({'error':'仅允许资料页主动同步'},403);return
        if self.path!='/api/feishu-sync':self.reply({'error':'不存在'},404);return
        try:
            n=int(self.headers.get('Content-Length','0'))
            if not 0<n<65536:raise ValueError('请求过大')
            payload=json.loads(self.rfile.read(n));self.reply(self.engine.start(payload.get('items')),202)
        except (ValueError,TypeError,json.JSONDecodeError) as e:self.reply({'error':str(e)},400)
        except Exception:self.reply({'error':'同步服务暂时不可用'},500)

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--serve-root');p.add_argument('--config',required=True);p.add_argument('--port',type=int,default=8799);a=p.parse_args()
    Handler.engine=SyncEngine(a.root,a.config)
    server=ThreadingHTTPServer(('127.0.0.1',a.port),functools.partial(Handler,directory=a.serve_root or a.root));server.serve_forever()
if __name__=='__main__':main()
