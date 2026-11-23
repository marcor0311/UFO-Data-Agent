"""Temporal evidence must not introduce a day, century or representative year."""
import unittest
from scripts.silver_analytics import interpret_raw_date,placeholder_profile,supported_date,temporal_decision
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

    def test_free_text_components_must_appear_in_raw_date(self):
        cases={('07/52','1952-07-01'):'1952-07',('Sometime in 1952','1952-01-01'):'1952',
               ('20 Feb','1952-02-20'):None,('night of January 1','1952-01-01'):None,
               ('21-22 July 1952','1952-07-21'):'1952-07',('1/1/1943','1943-01-01'):'1943-01-01',
               ('Sept. 1, 1966','1966-09-01'):'1966-09-01',('090706','2009-07-06'):'2009-07-06',
               ('241400GMT JAN 72','1972-01-24'):'1972-01-24',('June [1952]','1952-06-01'):'1952-06',
               ('OTTOBRE 1944 17 MILANO (MI) AQ 5165','1944-10-01'):'1944-10',
               (' 811-09-03','0811-09-03'):'0811-09-03',('8/1027','1027-08'):'1027-08'}
        for (raw,point),expected in cases.items():
            with self.subTest(raw=raw):self.assertEqual(supported_date(raw,point),expected)

    def test_synthetic_day_removed_and_external_year_not_certified(self):
        original={'date_event':'1952-07-01','sighting_datetime':'1952-07-01','date_event_raw':'07/52'}
        evidence,overrides,forced,certainty,relevant=temporal_decision(original,parse_date,'2026-11-21')
        self.assertEqual((evidence['kind'],overrides,certainty,relevant),
                         ('coarsened',{'date_event':'1952-07','sighting_datetime':'1952-07'},'coarsened',True))
        original.update(date_event='1952-02-20',sighting_datetime='1952-02-20',date_event_raw='20 Feb')
        evidence,overrides,forced,certainty,relevant=temporal_decision(original,parse_date,'2026-11-21')
        self.assertEqual((evidence['kind'],overrides,certainty,relevant),('unsupported',{},'qualified',True))
        for raw,point in [('SAB. 07 GIUGNO 3003 23:00 FIRENZE (FI) BQ 7201','2003-06-07'),('30 NOV 2335','1974-11-30')]:
            original.update(date_event=point,sighting_datetime=point,date_event_raw=raw)
            self.assertEqual(temporal_decision(original,parse_date,'2026-11-21')[3],'qualified')

    def test_approximate_alternative_and_publication_dates_are_qualified(self):
        for raw in ['July or August 1948','about 1986','might have been 1975','~1950','1952, around March or April',
                    '1975 (as listed on website cover page)','6/11/1947 (estimated)','090816–090817',
                    'ESTATE 1979 o 1980 15:00 circa PAVONE MELLA (BS) BQ 7938','AGOSTO 1956 ? IMPRECISATO ISOLE TREMITI (FG) AQ 5746']:
            with self.subTest(raw=raw):self.assertEqual(interpret_raw_date(raw)['kind'],'qualified')
        original={'date_event':'1986-01-01','sighting_datetime':'1986-01-01','date_event_raw':'about 1986'}
        self.assertEqual(temporal_decision(original,parse_date,'2026-11-21')[3],'qualified')

    def test_explicit_month_and_italian_catalogue_layout(self):
        cases={'1938 (September)':'1938-09','LUN. 06 DICEMBRE 1937 17.35 ca. PALERMO (PA) ME 5160':'1937-12-06',
               'SETTEMBRE 1948 IMPRECISATO SARZANA (SP) BQ 2949':'1948-09','ANNO 1971 02.40 CERVARO (FR) AQ 3303 A':'1971',
               'ESTATE 1942 IMPRECISATO TORINO (TO) AQ 5938':'1942','MER. 28 NOVEMBRE 1973 TRA 17 E 18 ROMA (RM) BQ 1376':'1973-11-28',
               'APRILE 1928 (fine) IMPRECISATO ARQUATA SCRIVIA (AL) AQ 3918':'1928-04','1993-05-20 00:00:00':'1993-05-20'}
        for raw,expected in cases.items():
            with self.subTest(raw=raw):self.assertEqual(interpret_raw_date(raw)['candidate'],expected)
        self.assertEqual(interpret_raw_date('INVERNO 1947 POMERIGGIO SASSARI (SS) AQ 4166')['kind'],'qualified')
        original={'date_event':'1947-08-12','sighting_datetime':'1947-08-12','date_event_raw':'LUN. 25 AGOSTO 1947 21.30 MILANO (MI) AQ 5650'}
        self.assertEqual(temporal_decision(original,parse_date,'2026-11-21')[0]['kind'],'conflict')

    def test_review_dates_do_not_keep_a_precision_label(self):
        self.assertEqual(parse_date('0019-07','2026-11-21',True),(None,'unknown','review','unknown',None))
        self.assertEqual(parse_date('2030-08-02','2026-11-21'),(None,'unknown','review','unknown',None))

    def test_placeholder_profile_flags_statistical_excess_only(self):
        rows=[(1,f'2000-{month:02d}-{day:02d}') for month in range(1,13) for day in range(1,29)]
        rows+=[(1,'2000-03-01')]*12+[(1,'2000-01-01')]*20+[(2,'2000-01-01')]
        policy={'temporal_placeholders':{'candidates':{'day':['01','15'],'month_day':['01-01']},'ratio_threshold':1.25}}
        profile={row[:3]:row[3:] for row in placeholder_profile(rows,policy)}
        self.assertEqual(profile[(1,'day','01')],(44,12.0,3.6667,1))
        self.assertEqual(profile[(1,'day','15')][3],0)
        self.assertEqual(profile[(1,'month_day','01-01')][3],1)
        self.assertEqual(profile[(2,'day','01')][2:],(None,0))


if __name__=='__main__':unittest.main()
