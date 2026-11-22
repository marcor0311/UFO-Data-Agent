"""Boundaries for source evidence used by Gold-facing Silver fields."""
import unittest

from scripts import silver_analytics as analytics, silver_evidence as evidence
from scripts.silver_quality import parse_date


class SourceEvidenceTests(unittest.TestCase):
    def test_ufocat_decades_are_source_specific_and_never_point_dates(self):
        for raw in ('196.--','196L--','196M- F-','194M-12-23'):
            result=analytics.interpret_raw_date(raw,'UFOCAT')
            self.assertEqual(result['kind'],'decade')
            self.assertIsNone(result['candidate'])
            self.assertEqual(result['year_max']-result['year_min'],9)
            self.assertNotEqual(analytics.interpret_raw_date(raw)['kind'],'decade')
        original={'date_event':'1965-01-01T01:33','sighting_datetime':'1965-01-01T01:33',
                  'date_event_raw':'1965-01-01','time_raw':'01333'}
        decision=analytics.temporal_decision(original,parse_date,'2026-11-21',True)
        self.assertEqual(decision[1],{'date_event':'1965-01-01','sighting_datetime':'1965-01-01'})

    def test_clock_restored_only_on_exact_day_of_same_record(self):
        original={'date_event':'1952-07-14','sighting_datetime':'1952-07-14',
                  'date_event_raw':'7/14/1952','time_raw':None}
        item={'date_event_raw':'7/14/1952','time_raw':'21:15','single_date':True}
        def recover():
            temporal=analytics.temporal_decision(original,parse_date,'2026-11-21')
            return evidence.time_overrides(original,temporal,item,parse_date,'2026-11-21')
        self.assertEqual(recover(),{'time_raw':'21:15','sighting_datetime':'1952-07-14T21:15'})
        item['time_raw']='~21:15'
        self.assertEqual(recover(),{'time_raw':'~21:15'})
        item['time_raw']='21:15';item['single_date']=False
        self.assertEqual(recover(),{'time_raw':'21:15'})
        item['single_date']=True;original['date_event']='1952-07'
        original['sighting_datetime']='1952-07';original['date_event_raw']='7/1952';item['date_event_raw']='7/1952'
        self.assertEqual(recover(),{'time_raw':'21:15'})
        item['date_event_raw']='8/1952'
        with self.assertRaises(ValueError):recover()

    def test_facility_distance_and_stable_tie(self):
        facilities=[(2,'Second',0,1),(1,'First',0,-1)]
        self.assertEqual(evidence.nearest_facility(0,0,facilities),(111.2,'First'))
        self.assertEqual(evidence.nearest_facility(0,0,[]),(None,None))
        self.assertFalse(evidence.valid_source_coordinates({'latitude':0,'longitude':0,'country':'The Moon'}))
        self.assertFalse(evidence.valid_source_coordinates({'latitude':90.000004,'longitude':0,'country':'USA'}))
        self.assertTrue(evidence.valid_source_coordinates({'latitude':0,'longitude':0,'country':''}))


if __name__=='__main__':unittest.main()
