import importlib.util,json,tempfile,unittest
from pathlib import Path
from datetime import datetime
spec=importlib.util.spec_from_file_location('library_server',Path(__file__).parents[1]/'scripts/library_server.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class SyncTest(unittest.TestCase):
 def test_verified_write_and_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);month=datetime.now().strftime('%Y-%m');target='https://example.feishu.cn/docx/demo'
   (p/'config.json').write_text(json.dumps({'targets':{month:target}}));(p/'catalog.json').write_text(json.dumps([{'id':'x:123','title':'Three.js 网站案例','url':'https://x.com/demo/status/123'}]))
   engine=s.SyncEngine(p,p/'config.json');content=f'<title>{month} 月</title><h1>AI Coding</h1><table id="anchor"><tbody><tr><td><p>原有选题</p></td></tr></tbody></table>';writes=[]
   def cli(*args):
    nonlocal content
    if args[0]=='+update':
     writes.append(args);content+=Path(args[args.index('--content')+1][1:]).read_text()
    return {'ok':True,'data':{'document':{'content':content,'revision_id':1}}}
   engine.cli=cli
   row={'id':'x:123','title':'Three.js 网站案例','url':'https://x.com/demo/status/123','category':'AI Coding','content':'开发教程：Three.js 视频制作'}
   job={'id':'test','state':'running','month':month,'target':target,'total':1,'done':0,'results':[]};engine.run(job,[row]);self.assertEqual(job['state'],'done');self.assertEqual(len(writes),1);self.assertIn('原有选题',content);self.assertEqual(engine.status()['synced'],['x:123'])
   job2={**job,'id':'again','done':0,'results':[]};engine.run(job2,[row]);self.assertEqual(len(writes),1);self.assertEqual(job2['results'][0]['state'],'already')
   self.assertRaises(ValueError,engine.start,[{'id':'untrusted'}])
 def test_identity(self):
  self.assertEqual(s.post_key('https://www.instagram.com/p/demo/?tracking=1'),s.post_key('https://www.instagram.com/reel/demo/'))
if __name__=='__main__':unittest.main()
