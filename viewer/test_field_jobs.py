import unittest,tempfile,time,threading,json
from pathlib import Path
from concurrent.futures import Future
from unittest.mock import patch
import field_jobs,store
from test_spatial import row
from archive import query_url

class InlineExecutor:
 def submit(self,fn,*args):
  future=Future()
  try:future.set_result(fn(*args))
  except Exception as e:future.set_exception(e)
  return future

class DurableFieldJobTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=patch.object(store,'DB',self.root/'catalogue.sqlite');self.db.start();self.cache=patch.object(field_jobs,'CACHE',self.root);self.cache.start();self.products=self.root/'products';self.products.mkdir();self.registry={};field_jobs._active.clear()
  self.rows=[row(str(i),'CIRCLE ICRS 0 0 1',detector=1,mjd=60000+i) for i in range(4)];store.put_query(query_url(0,0,5,'spherex_dr1'),{'rows':self.rows,'truncated':False});self.calls=[]
 def tearDown(self):self.cache.stop();self.db.stop();self.tmp.cleanup()
 def payload(self,n=4):return {'ra':0,'dec':0,'fov_arcmin':5,'observation_ids':[r['id'] for r in self.rows[:n]]}
 def image(self,job,rows,params,dest,match=False):
  self.calls.append(rows[0]['id']);dest.mkdir(exist_ok=True);m={'parameters':params,'frames':[{'id':rows[0]['id']}]};(dest/'manifest.json').write_text(json.dumps(m));job.update(state='complete',manifest=m)
 def assembly(self,job,ids,params,dest):
  dest.mkdir(exist_ok=True);(dest/'manifest.json').write_text(json.dumps({'parameters':params,'frames':[]}));job.update(state='complete')
 def wait(self,key):
  for _ in range(300):
   state=field_jobs.status(key)
   if not field_jobs._active.get(key):return state
   time.sleep(.01)
  self.fail('Field job did not finish')
 def test_all_records_are_attempted_and_status_persists(self):
  data=field_jobs.start(self.payload(),InlineExecutor(),self.products,self.registry,self.image,self.assembly);state=self.wait(data['id'])
  self.assertEqual(state['state'],'complete');self.assertEqual(state['counts']['prepared'],4);self.assertEqual(len(self.calls),4);self.assertTrue(state['sequence_id'])
 def test_three_failures_pause_without_failing_unattempted_records(self):
  def fail(job,*args):job.update(state='failed',error='upstream unavailable')
  data=field_jobs.start(self.payload(),InlineExecutor(),self.products,self.registry,fail,self.assembly);state=self.wait(data['id'])
  self.assertEqual(state['state'],'paused_after_failures');self.assertEqual(state['counts']['failed'],3);self.assertEqual(state['counts']['pending'],1)
 def test_stop_then_explicit_resume(self):
  entered=threading.Event();release=threading.Event()
  def held(*args):entered.set();release.wait(2);self.image(*args)
  data=field_jobs.start(self.payload(2),InlineExecutor(),self.products,self.registry,held,self.assembly)
  try:
   self.assertTrue(entered.wait(2));field_jobs.stop(data['id'])
  finally:release.set()
  state=self.wait(data['id']);self.assertEqual(state['state'],'stopped');self.assertEqual(state['counts']['prepared'],1)
  data=field_jobs.start(self.payload(2),InlineExecutor(),self.products,self.registry,self.image,self.assembly);state=self.wait(data['id']);self.assertEqual(state['state'],'complete');self.assertEqual(len(self.calls),2)
