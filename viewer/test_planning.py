import unittest
from unittest.mock import patch
from planning import select_candidates

class PlanningTests(unittest.TestCase):
 def test_cached_pair_before_sampling_and_outside_skipped(self):
  rows=[{'id':str(i),'t_min':str(i)} for i in range(12)]
  def probe(row,ra,dec,cached_only=False):
   self.assertTrue(cached_only)
   i=int(row['id'])
   if i==4:raise ValueError('Target is outside the native detector footprint')
   if i in [0,11]:raise FileNotFoundError()
   return dict(wavelength_um=3.45 if i in [3,8] else i,bandwidth_um=.1,detector='D4',collection='dr1')
  with patch('planning.wavelength_probe',side_effect=probe):selected,report=select_candidates(rows,{'ra':0,'dec':0},6)
  self.assertEqual([r['id'] for r in selected],['3','8'])
  self.assertEqual(report['network_requests'],0)
  self.assertEqual(len(report['excluded']),1)
 def test_uncached_fallback_bounded_sorted(self):
  rows=[{'id':str(i),'t_min':str(i)} for i in range(20)]
  with patch('planning.wavelength_probe',side_effect=FileNotFoundError):selected,report=select_candidates(rows,{'ra':0,'dec':0},6)
  self.assertEqual(len(selected),6);self.assertEqual(selected[0]['id'],'0');self.assertEqual(selected[-1]['id'],'19')
 def test_no_centre_coverage(self):
  with patch('planning.wavelength_probe',side_effect=ValueError('outside')):selected,_=select_candidates([{'id':'x','t_min':'1'}],{'ra':0,'dec':0},6)
  self.assertEqual(selected,[])
