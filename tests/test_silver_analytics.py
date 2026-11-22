"""Temporal evidence must not introduce a day, century or representative year."""
import unittest
from scripts.silver_analytics import interpret_raw_date,temporal_decision
from scripts.silver_quality import parse_date


class TemporalGrammarTests(unittest.TestCase):
    def test_supported_calendar_precision(self):
        cases={'Summer 1952':'1952','Late 8/1947':'1947-08','April 1952':'1952-04',
               '1950-06- E':'1950-06','1950--':'1950','14 October 1952':'1952-10-14',
               'October 14, 1952':'1952-10-14','2/29/2000':'2000-02-29',
               'summer evening in 1946':'1946','Summer 1945 NIGHT':'1945',
               '1995 Late Summer':'1995','Late November 1933':'1933-11',
               'October 1997, Evening':'1997-10','1977 (Colares events)':'1977',
               'one night (1976)':'1976'}
        for raw,expected in cases.items():
            with self.subTest(raw=raw):self.assertEqual(interpret_raw_date(raw)['candidate'],expected)

    def test_ambiguous_impossible_or_incomplete_not_inferred(self):
        for raw in ['19--','196E--','8/3/989','1/2/70','10/11/1990','1949-02-29',
                    'July 8, 11.15PM','1995/1994','0000','1990-13-','1991s','0214','reported in 2022','1977 (approximately)','1977 (reported in 1999)']:
            with self.subTest(raw=raw):self.assertIsNone(interpret_raw_date(raw)['candidate'])
        for raw in ['Winter 1952','1943 (approximate)','In the summer of 1952, about 2:00 p.m.']:
            self.assertEqual(interpret_raw_date(raw)['kind'],'qualified')

    def test_fractional_precision_and_offset_validation(self):
        value='2020-01-01T12:34:56.1+05:30'
        self.assertEqual(parse_date(value,'2026-11-21')[:4],(value,'fractional_second','valid','offset_known'))
        for value in ['2020-01-01T12:34+01:99','2020-01-01T12:34+24:00']:
            self.assertEqual(parse_date(value,'2026-11-21')[2],'invalid')

    def test_intervals_do_not_become_point_dates(self):
        for raw,lower,upper in [('1995/1996',1995,1996),('1968 - 1969',1968,1969),("1950's",1950,1959),("mid-1990s",1990,1999)]:
            result=interpret_raw_date(raw)
            self.assertEqual((result['candidate'],result['year_min'],result['year_max']),(None,lower,upper))

    def test_known_clock_preserved_and_conflicting_raw_quarantined(self):
        original={'date_event':'1952-01-01T21:00','sighting_datetime':'1952-01-01T21:00','date_event_raw':'1952-01-01'}
        result=temporal_decision(original,parse_date,'2026-11-21')
        self.assertEqual(result[1],{})
        original['date_event_raw']='1953'
        result=temporal_decision(original,parse_date,'2026-11-21')
        self.assertEqual(result[0]['kind'],'conflict')
        self.assertEqual(result[1],{'date_event':None,'sighting_datetime':None})


if __name__=='__main__':unittest.main()
