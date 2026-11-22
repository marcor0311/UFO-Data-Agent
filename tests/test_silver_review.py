"""Candidate triage describes insufficient evidence without adjudicating pairs."""
import sqlite3
import unittest
from scripts.review_silver import candidate_query


class CandidateReviewTests(unittest.TestCase):
    def test_first_blocker_covers_pairs_without_double_counting(self):
        with sqlite3.connect(':memory:') as conn:
            conn.create_function('norm',1,lambda v:v.strip().casefold() if isinstance(v,str) else v)
            conn.create_function('meaningful',1,lambda v:v is not None and str(v).strip().casefold() not in ('','unknown','other','n/a','?','unidentified'))
            conn.executescript('''
                CREATE TABLE sighting(id INTEGER PRIMARY KEY,sighting_datetime TEXT,
                    datetime_precision TEXT,coordinate_status TEXT,lat REAL,lng REAL,
                    standardized_shape TEXT,time_raw TEXT,color TEXT,duration_seconds INTEGER,
                    num_witnesses INTEGER,sound TEXT,direction TEXT,hynek TEXT,vallee TEXT,
                    event_type TEXT,weather TEXT,terrain TEXT);
                CREATE TABLE duplicate_candidate(id INTEGER PRIMARY KEY,sighting_id_a INTEGER,
                    sighting_id_b INTEGER,match_method TEXT);
                CREATE TABLE duplicate_resolution(candidate_id INTEGER PRIMARY KEY,decision TEXT);
            ''')
            baseline=[None,'2020-01-01T12:00','minute','valid',10,-84,'Disc','1200','Red',30,None,None,None,None,None,None,None,None]
            mutations={2:{1:'2020-01-02T12:00'},3:{3:'review',4:None,5:None},
                       4:{8:'Blue'},5:{8:None,9:None},6:{7:None},7:{}}
            conn.execute('INSERT INTO sighting VALUES ('+','.join('?' for _ in baseline)+')',[1]+baseline[1:])
            for key,updates in mutations.items():
                row=baseline.copy();row[0]=key
                for index,value in updates.items():row[index]=value
                conn.execute('INSERT INTO sighting VALUES ('+','.join('?' for _ in row)+')',row)
                conn.execute("INSERT INTO duplicate_candidate VALUES (?,1,?,'test')",(key,key))
                conn.execute("INSERT INTO duplicate_resolution VALUES (?,'needs_review')",(key,))
            result={reason:count for reason,method,count,example in conn.execute(candidate_query())}
            self.assertEqual(result,{'datetime_differs':1,'coordinates_unusable':1,
                'descriptors_differ':1,'descriptors_insufficient':1,'time_raw_insufficient':1,
                'strict_match_unconfirmed':1})
            self.assertEqual(sum(result.values()),6)


if __name__=='__main__':
    unittest.main()
