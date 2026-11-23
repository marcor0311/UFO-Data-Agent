"""Exercise actual cleaning, ambiguity preservation and reversible deduplication."""
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts import build_silver as silver
from scripts import silver_quality as quality


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "bronze.db"
        self.target = self.root / "silver/ufo.db"
        self.policy = json.loads(silver.POLICY.read_text())
        self.policy["drop_columns"] = {}
        self.policy["quality"]["country_reference"] = str(silver.ROOT / "config/countries.json")
        with closing(sqlite3.connect(self.source)) as db, db:
            db.executescript("""
                CREATE TABLE source_database (id INTEGER PRIMARY KEY,name TEXT UNIQUE);
                CREATE TABLE location (id INTEGER PRIMARY KEY,city TEXT,state TEXT,country TEXT,
                    country_iso2 TEXT,latitude REAL,longitude REAL);
                CREATE TABLE sighting (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,source_db_id INTEGER REFERENCES source_database(id),
                    source_record_id TEXT,location_id INTEGER REFERENCES location(id),
                    date_event TEXT,date_event_raw TEXT,time_raw TEXT,sighting_datetime TEXT,
                    standardized_shape TEXT,color TEXT,duration_seconds INTEGER,num_witnesses INTEGER,
                    sound TEXT,direction TEXT,quality_score INTEGER,hoax_likelihood REAL,
                    lat REAL,lng REAL,has_media INTEGER,movement_categories TEXT,
                    emotion_7_dominant TEXT,emotion_28_group TEXT,movement_type TEXT,duration_bucket TEXT
                );
                CREATE TABLE duplicate_candidate (id INTEGER PRIMARY KEY,
                    sighting_id_a INTEGER REFERENCES sighting(id),sighting_id_b INTEGER REFERENCES sighting(id),
                    status TEXT DEFAULT 'pending');
                CREATE TABLE sighting_analysis (id INTEGER PRIMARY KEY,
                    sighting_id INTEGER UNIQUE REFERENCES sighting(id),behavior_tags TEXT,
                    emotion_scores TEXT,hoax_flags TEXT,color_list TEXT);
                CREATE TABLE crash_retrieval (id TEXT PRIMARY KEY,date_event TEXT,country TEXT,
                    craft_size_m REAL,latitude REAL,longitude REAL,raw_json TEXT);
                INSERT INTO source_database VALUES (1,'UFOCAT');
                INSERT INTO location VALUES (1,'  San José  ',' ','CA','US',10,-84);
                INSERT INTO location VALUES (2,'Rome',NULL,'Italy',NULL,42,12);
                INSERT INTO location VALUES (3,'Windhoek',NULL,'NA','NA',-22,17);
                INSERT INTO location VALUES (4,'Taipei',NULL,'Taiwan','TW',25,121);
                INSERT INTO location VALUES (5,'N/A','null','USSR','RU',50,30);
                INSERT INTO crash_retrieval VALUES ('estimate','1947-07-01','US','~30 (99 ft, per source)',NULL,NULL,'{}');
                INSERT INTO crash_retrieval VALUES ('component','1947','US','component-only (no intact craft)',NULL,NULL,'{}');
            """)
            fields = [row[1] for row in db.execute("PRAGMA table_info(sighting)")]
            baseline = dict(id=1,source_db_id=1,source_record_id="reused",location_id=1,
                            date_event="2020-01-01T21:00",date_event_raw="2020-01-01",time_raw="2100",
                            sighting_datetime="2020-01-01T21:00",standardized_shape="Disc",color="Orange",
                            duration_seconds=30,num_witnesses=2,sound="none",direction="north",
                            quality_score=60,hoax_likelihood=0,lat=10,lng=-84,has_media=0,
                            movement_categories="[]",emotion_7_dominant="neutral",emotion_28_group="neutral",
                            movement_type="linear",duration_bucket="seconds")
            rows = []
            for key in range(1,8):
                row = {**baseline,"id":key}
                if key == 1:
                    row.update(date_event="1949-02-29",sighting_datetime="1949-02-29",date_event_raw="original date",lat=200,
                               quality_score=101,movement_categories="not JSON",sound=" none ",emotion_7_dominant="invalid")
                elif key == 2:
                    row.update(date_event="2020-05",sighting_datetime="2020-05",date_event_raw="2020-05",lng=None)
                elif key == 5:
                    row["color"]="Blue"
                elif key == 6:
                    row.update(date_event=None,sighting_datetime=None,date_event_raw="original date",lat=None,lng=None)
                elif key == 7:
                    row.update(date_event="0019-01-02T07:30",sighting_datetime="0019-01-02T07:30",date_event_raw="19-01-02")
                if key in (3,4,5):
                    row.update(location_id=2,lat=42,lng=12)
                rows.append(tuple(row[name] for name in fields))
            db.executemany("INSERT INTO sighting VALUES ("+",".join("?" for _ in fields)+")",rows)
            db.executemany("INSERT INTO duplicate_candidate VALUES (?,?,?,'pending')",[(1,3,4),(2,1,2),(3,1,1),(4,3,5)])
            db.execute("INSERT INTO sighting_analysis VALUES (1,1,'[]','{\"joy\":2}','[]','[]')")
        self.manifest = {"dataset":"ufo","expected_metrics":{"total":7},"expected_sources":{"UFOCAT":7},
                         "size_bytes":self.source.stat().st_size,"sha256":silver.digest(self.source)}

    def build(self, target=None, policy=None, replace=False):
        return silver.build(self.source,target or self.target,self.manifest,policy or self.policy,replace=replace)

    def test_cleaning_and_reconciliation(self):
        before = self.source.read_bytes()
        report = self.build()
        self.assertTrue(report["passed"])
        self.assertEqual(before,self.source.read_bytes())
        with closing(sqlite3.connect(self.target)) as db:
            invalid = db.execute("SELECT date_event,date_status,lat,lng,quality_score,movement_categories,sound,has_media FROM sighting WHERE id=1").fetchone()
            self.assertEqual(invalid,(None,"invalid",None,None,None,None,"none",0))
            self.assertEqual(db.execute("SELECT date_event,date_precision,event_year,lat,lng,coordinate_status FROM sighting WHERE id=2").fetchone(),("2020-05","month",2020,None,None,"partial"))
            self.assertEqual(db.execute("SELECT date_event,date_status FROM sighting WHERE id=7").fetchone(),(None,"review"))
            self.assertEqual(db.execute("SELECT sighting_datetime,datetime_precision,timezone_status FROM sighting WHERE id=3").fetchone(),("2020-01-01T21:00","minute","unspecified"))
            self.assertEqual(db.execute("SELECT city,state,country,country_iso2,country_status FROM location WHERE id=1").fetchone(),("San José",None,None,None,"conflict"))
            self.assertEqual(db.execute("SELECT country,country_iso2,country_status FROM location WHERE id=2").fetchone(),("Italy","IT","valid"))
            self.assertEqual(db.execute("SELECT country_iso2,country_status FROM location WHERE id=3").fetchone(),("NA","valid"))
            self.assertEqual(db.execute("SELECT country_iso2,country_status FROM location WHERE id=4").fetchone(),("TW","valid"))
            self.assertEqual(db.execute("SELECT country,country_iso2,country_status FROM location WHERE id=5").fetchone(),(None,None,"unrecognized"))
            self.assertEqual(db.execute("SELECT city,state FROM location WHERE id=5").fetchone(),(None,None))
            self.assertEqual(db.execute("SELECT craft_size_m,craft_size_status FROM crash_retrieval WHERE id='estimate'").fetchone(),(30.0,"approximate"))
            self.assertEqual(db.execute("SELECT craft_size_m,craft_size_status FROM crash_retrieval WHERE id='component'").fetchone(),(None,"unquantified"))
            self.assertIsNone(db.execute("SELECT emotion_scores FROM sighting_analysis").fetchone()[0])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sighting").fetchone()[0],7)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sighting_canonical").fetchone()[0],6)
            self.assertEqual(list(db.execute("SELECT candidate_id,decision FROM duplicate_resolution ORDER BY candidate_id")),[(1,"confirmed_exact"),(2,"needs_review"),(3,"invalid_pair"),(4,"needs_review")])
            self.assertEqual(list(db.execute("SELECT sighting_id,canonical_event_id FROM event_membership WHERE sighting_id IN (3,4,5) ORDER BY sighting_id")),[(3,3),(4,3),(5,5)])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM quality_review").fetchone()[0]>0,True)
            self.assertEqual(list(db.execute("PRAGMA foreign_key_check")),[])
        verification = silver.verify(self.source,self.target,self.manifest,self.policy)
        self.assertTrue(verification["passed"])
        self.assertEqual(verification["changed_fields_verified"],report["quality"]["changed_fields"])

    def test_conflicting_city_geocode_is_quarantined_before_grouping(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("ALTER TABLE location ADD COLUMN geocode_src TEXT")
            db.execute("UPDATE location SET geocode_src='geonames_city_only' WHERE id=1")
            # Rows 3 and 4 copy the conflicting location, row 5 has independent coordinates.
            db.execute("UPDATE sighting SET location_id=1,lat=10,lng=-84 WHERE id IN (3,4)")
            db.execute("UPDATE sighting SET lat=11,lng=-85 WHERE id=5")
        self.manifest.update(size_bytes=self.source.stat().st_size,sha256=silver.digest(self.source))
        report = self.build()
        self.assertTrue(report['passed'])
        with closing(sqlite3.connect(self.target)) as db:
            self.assertEqual(db.execute("SELECT latitude,longitude,coordinate_status FROM location WHERE id=1").fetchone(), (None,None,'review'))
            self.assertEqual(db.execute("SELECT lat,lng,coordinate_status FROM sighting WHERE id=3").fetchone(), (None,None,'review'))
            self.assertEqual(db.execute("SELECT lat,lng,coordinate_status FROM sighting WHERE id=5").fetchone(), (11,-85,'valid'))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM duplicate_group").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sighting_for_map WHERE id IN (3,4)").fetchone()[0],0)
            self.assertEqual(db.execute("SELECT rule_id FROM silver_change WHERE table_name='sighting' AND record_id='3' AND column_name='lat'").fetchone()[0],'coordinate_country_conflict')
        self.assertTrue(silver.verify(self.source,self.target,self.manifest,self.policy)['passed'])

    def test_netherlands_alias_and_uncertain_countries(self):
        countries = quality.Countries(json.loads((silver.ROOT/'config/countries.json').read_text()))
        self.assertEqual(countries.resolve('Netherlands','NL')[1:],('NL','valid'))
        for country,code in [('USSR','RU'),('Korea','KR'),('Kent',None),('OC',None),('AL','XK')]:
            self.assertEqual(countries.resolve(country,code)[2],'unrecognized')
        self.assertEqual(countries.resolve('Netherlands','US')[2],'conflict')

    def test_temporal_recovery_downgrade_intervals_and_analytical_grain(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            cases=[(None,None,'Summer 1952',2),
                   ('1953-07-01','1953-07-01','Summer 1953',3),
                   (None,None,'1995/1996',4),
                   ('1990-01-01','1990-01-01',"1990's",5),
                   (None,None,'10/11/1990',6)]
            db.executemany('UPDATE sighting SET date_event=?,sighting_datetime=?,date_event_raw=? WHERE id=?',cases)
            db.execute('UPDATE sighting SET location_id=NULL,time_raw=NULL WHERE id=6')
        self.manifest.update(size_bytes=self.source.stat().st_size,sha256=silver.digest(self.source))
        report=self.build()
        with closing(sqlite3.connect(self.target)) as db:
            self.assertEqual(db.execute('SELECT date_event,date_precision,date_certainty FROM sighting WHERE id=2').fetchone(),('1952','year','coarsened'))
            self.assertEqual(db.execute('SELECT date_event,sighting_datetime,date_precision FROM sighting WHERE id=3').fetchone(),('1953','1953','year'))
            self.assertEqual(db.execute('SELECT date_event,event_year,date_status,date_certainty FROM sighting WHERE id=4').fetchone(),(None,None,'range','interval'))
            self.assertEqual(db.execute('SELECT evidence_year_min,evidence_year_max FROM sighting_analytical WHERE id=5').fetchone(),(1990,1999))
            self.assertEqual(db.execute('SELECT date_event,usable_for_calendar,usable_for_country FROM sighting_analytical WHERE id=6').fetchone(),(None,0,0))
            self.assertEqual(db.execute('SELECT COUNT(*),COUNT(DISTINCT id) FROM sighting_analytical').fetchone(),(7,7))
            self.assertEqual(db.execute('SELECT time_basis,uses_external_evidence FROM sighting_analytical WHERE id=6').fetchone(),(None,0))
            self.assertEqual(db.execute("SELECT reported_value,coded_value,reported_iso2,coded_iso2 FROM country_evidence WHERE table_name='location' AND record_id='1'").fetchone(),('CA','US','CA','US'))
            self.assertEqual(db.execute("SELECT json_extract(raw_value,'$') FROM silver_rescued_value WHERE table_name='location' AND record_id='1' AND column_name='country'").fetchone()[0],'CA')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sighting_reports_for_time_analysis WHERE id IN (4,5,6)').fetchone()[0],0)
        self.assertTrue(silver.verify(self.source,self.target,self.manifest,self.policy)['passed'])
        self.assertEqual(report['field_profile']['sighting']['rows'],7)

    def test_all_country_conflicts_quarantined_without_geocoder_tag(self):
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            self.assertEqual(db.execute('SELECT latitude,longitude,coordinate_status FROM location WHERE id=1').fetchone(),(None,None,'review'))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sighting_analytical WHERE id IN (3,4) AND usable_for_map=1').fetchone()[0],2)

    def test_ledger_rejects_changed_primary_key_even_with_equal_counts(self):
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            db.execute("ATTACH DATABASE ? AS bronze",(str(self.source),))
            db.execute('UPDATE sighting SET id=30 WHERE id=3')
            layouts={'sighting':[col for col in silver.columns(db,'sighting','bronze')]}
            with self.assertRaisesRegex(ValueError,'Identificadores distintos'):
                quality.verify_change_ledger(db,layouts)

    def test_temporal_replay_detects_unexpected_evidence(self):
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            db.execute('ATTACH DATABASE ? AS bronze',(str(self.source),))
            db.execute("INSERT INTO temporal_evidence VALUES (3,'original date','unresolved',NULL,NULL,NULL,0)")
            checks=quality.validate_quality(db,self.policy['quality'],quality.Countries(json.loads((silver.ROOT/'config/countries.json').read_text())))
            self.assertFalse(checks['analytics_temporal_replay']['passed'])

    def test_qualified_dates_do_not_confirm_duplicate_groups(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE sighting SET date_event_raw='2020-01-01 (approximate)' WHERE id IN (3,4)")
        self.manifest.update(size_bytes=self.source.stat().st_size,sha256=silver.digest(self.source))
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM duplicate_group').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT date_certainty,usable_for_calendar FROM sighting_analytical WHERE id=3').fetchone(),('qualified',0))
            self.assertIsNotNone(db.execute('SELECT date_event FROM sighting WHERE id=3').fetchone()[0])

    def test_geographic_dependencies_rescued_when_coordinates_unusable(self):
        with closing(sqlite3.connect(self.source)) as db,db:
            db.execute('ALTER TABLE sighting ADD COLUMN distance_to_nearest_nuclear_site_km REAL')
            db.execute('ALTER TABLE sighting ADD COLUMN nearest_nuclear_site_name TEXT')
            db.execute("UPDATE sighting SET distance_to_nearest_nuclear_site_km=20.5,nearest_nuclear_site_name='Source site'")
            db.execute('UPDATE sighting SET location_id=1,lat=10,lng=-84 WHERE id=5')
        self.manifest.update(size_bytes=self.source.stat().st_size,sha256=silver.digest(self.source))
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            for key in (1,2,5,6):
                self.assertEqual(db.execute('SELECT distance_to_nearest_nuclear_site_km,nearest_nuclear_site_name,usable_for_nuclear_proximity FROM sighting_analytical WHERE id=?',(key,)).fetchone(),(None,None,0))
            self.assertEqual(db.execute('SELECT distance_to_nearest_nuclear_site_km,nearest_nuclear_site_name,usable_for_nuclear_proximity FROM sighting_analytical WHERE id=3').fetchone(),(20.5,'Source site',1))
            self.assertEqual(db.execute("SELECT json_extract(raw_value,'$') FROM silver_rescued_value WHERE table_name='sighting' AND record_id='5' AND column_name='distance_to_nearest_nuclear_site_km'").fetchone()[0],20.5)
        self.assertTrue(silver.verify(self.source,self.target,self.manifest,self.policy)['passed'])

    def test_deterministic_data_and_membership(self):
        self.build()
        other=self.root/'other.db'
        self.build(other)
        with closing(sqlite3.connect(self.target)) as first,closing(sqlite3.connect(other)) as second:
            for table in ["sighting","location","event_membership","duplicate_resolution","silver_run","silver_change","quality_issue"]:
                count=len(list(first.execute(f'PRAGMA table_info("{table}")')))
                ordering=','.join(str(i) for i in range(1,count+1))
                self.assertEqual(list(first.execute(f'SELECT * FROM "{table}" ORDER BY {ordering}')),list(second.execute(f'SELECT * FROM "{table}" ORDER BY {ordering}')))

    def test_replace_archives_previous_validated_database(self):
        old_policy=copy.deepcopy(self.policy)
        old_policy.pop("quality")
        old_policy["version"]=1
        old=self.build(policy=old_policy)
        old_bytes=self.target.read_bytes()
        self.build(replace=True)
        archive=self.target.parent/'.history'/old['sha256']
        self.assertEqual((archive/'ufo.db').read_bytes(),old_bytes)
        self.assertEqual(json.loads((archive/'ufo.validation.json').read_text())['policy']['version'],1)
        self.assertTrue(silver.verify(self.source,self.target,self.manifest,self.policy)['passed'])

    def test_verification_rejects_modified_artifact(self):
        self.build()
        with closing(sqlite3.connect(self.target)) as db,db:
            db.execute("UPDATE sighting SET color='tampered' WHERE id=3")
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            silver.verify(self.source,self.target,self.manifest,self.policy)

    def test_repeated_replacement_keeps_all_validation_history(self):
        old_policy=copy.deepcopy(self.policy)
        old_policy.pop('quality')
        old_policy['version']=1
        first=self.build(policy=old_policy)
        for _ in range(3):
            self.build(policy=old_policy,replace=True)
        archive=self.target.parent/'.history'/first['sha256']
        self.assertTrue((archive/'ufo.db').exists())
        self.assertGreaterEqual(len(list(archive.glob('*.json'))),3)

    def test_failed_rebuild_preserves_previous_output(self):
        self.build()
        before=self.target.read_bytes()
        report_before=self.target.with_suffix('.validation.json').read_bytes()
        broken=copy.deepcopy(self.policy)
        reference=json.loads(Path(broken['quality']['country_reference']).read_text())
        reference['aliases']['broken']='ZZ'
        bad_reference=self.root/'bad-countries.json'
        bad_reference.write_text(json.dumps(reference))
        broken['quality']['country_reference']=str(bad_reference)
        with self.assertRaisesRegex(ValueError,'Alias de país'):
            self.build(policy=broken,replace=True)
        self.assertEqual(self.target.read_bytes(),before)
        self.assertEqual(self.target.with_suffix('.validation.json').read_bytes(),report_before)

    def test_partial_dates_timezone_and_future(self):
        self.assertEqual(quality.parse_date('2020','2026-11-21')[:3],('2020','year','valid'))
        self.assertEqual(quality.parse_date('2020-02','2026-11-21')[:3],('2020-02','month','valid'))
        self.assertEqual(quality.parse_date('2020-02-29 21:30Z','2026-11-21')[:4],('2020-02-29T21:30+00:00','minute','valid','offset_known'))
        self.assertEqual(quality.parse_date('1949-02-29','2026-11-21')[2],'invalid')
        self.assertEqual(quality.parse_date('2027','2026-11-21')[2],'review')
        self.assertEqual(quality.parse_date('0019-01-02','2026-11-21',False)[2],'valid')

    def test_catalogue_geography_is_compared_with_bronze_before_use(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("INSERT INTO source_database VALUES (2,'UFO-search')")
            # Bronze geocoded "Palestine" in Texas; the catalogue places it in Jerusalem.
            db.execute("""UPDATE sighting SET source_db_id=2,source_record_id='Hatch_UDB_5',date_event_raw='5/21/70',
                date_event=NULL,sighting_datetime=NULL,time_raw=NULL,location_id=2,lat=31.76212,lng=-95.63079 WHERE id=5""")
            # No Bronze pair: the same report's catalogue place may fill it.
            db.execute("""UPDATE sighting SET source_db_id=2,source_record_id='Hatch_UDB_6',date_event_raw='1/840?',
                time_raw=NULL,location_id=NULL WHERE id=6""")
        self.manifest.update(size_bytes=self.source.stat().st_size,sha256=silver.digest(self.source),
                             expected_sources={"UFOCAT":5,"UFO-search":2})
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            self.assertEqual(db.execute('SELECT lat,lng,coordinate_status FROM sighting WHERE id=5').fetchone(),(None,None,'review'))
            self.assertEqual(db.execute('SELECT country_status,country_basis,coordinate_basis,usable_for_map,usable_for_country FROM sighting_analytical WHERE id=5').fetchone(),
                             ('conflict','source_conflict','source_conflict',0,0))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM quality_issue WHERE record_id='5' AND rule_id IN ('source_coordinate_conflict','source_country_conflict')").fetchone()[0],2)
            self.assertEqual(db.execute('SELECT time_raw,time_basis,uses_external_evidence FROM sighting_analytical WHERE id=5').fetchone(),('~18:00','original_catalog',1))
            self.assertEqual(db.execute('SELECT lat,lng,coordinate_status FROM sighting WHERE id=6').fetchone(),(45.750002,4.866667,'valid'))
            self.assertEqual(db.execute('SELECT canonical_country_iso2,country_basis,coordinate_basis,uses_external_evidence FROM sighting_analytical WHERE id=6').fetchone(),
                             ('FR','original_catalog','original_catalog_place',1))
            self.assertEqual(db.execute('SELECT coordinate_check,country_check,coordinates_applied FROM source_geography_evidence ORDER BY sighting_id').fetchall(),
                             [('conflict','conflict',0),('fill','fill',1)])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM sighting_analytical WHERE uses_external_evidence=1').fetchone()[0],2)
        self.assertTrue(silver.verify(self.source,self.target,self.manifest,self.policy)['passed'])

    def test_rescued_values_keep_size_annotations_but_not_blank_text(self):
        self.build()
        with closing(sqlite3.connect(self.target)) as db:
            rescued=dict(((row[0],row[1]),json.loads(row[2])) for row in db.execute(
                "SELECT record_id,column_name,raw_value FROM silver_rescued_value WHERE table_name='crash_retrieval'"))
            self.assertEqual(rescued,{('estimate','craft_size_m'):'~30 (99 ft, per source)',
                                      ('component','craft_size_m'):'component-only (no intact craft)'})


if __name__=='__main__':
    unittest.main()
