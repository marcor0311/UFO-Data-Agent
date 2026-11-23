"""Reproducible compact analytical cohorts; never writes the source SQLite DB."""
from pathlib import Path
import sqlite3, json, re, datetime, calendar, hashlib
ROOT=Path(__file__).resolve().parent
DB=ROOT/'ufo_public.db'
SQL_COLUMNS='''s.id, s.source_db_id, s.source_record_id, s.date_event, s.date_event_raw,
s.date_reported, s.date_posted, s.shape, s.standardized_shape, s.duration_seconds,
s.num_witnesses, s.source_ref, s.lat, s.lng, s.has_photo, s.has_video,
l.city, l.state AS region, l.country, l.latitude AS location_lat,
l.longitude AS location_lon, l.geocode_src, d.name AS database_name, d.url AS database_url'''
BASE='SELECT '+SQL_COLUMNS+' FROM sighting s LEFT JOIN location l ON l.id=s.location_id LEFT JOIN source_database d ON d.id=s.source_db_id '
DATE_RE=re.compile(r'^(\d{4})(?:-(\d{2})(?:-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?)?)?$')
def date_info(v):
 m=DATE_RE.fullmatch((v or '').strip())
 if not m:return None
 y,mo,day,h,mi,se,tz=m.groups(); y=int(y);mo=int(mo) if mo else None;day=int(day) if day else None
 if not 1900<=y<=2026 or mo is not None and not 1<=mo<=12:return None
 if day is not None and not 1<=day<=calendar.monthrange(y,mo)[1]:return None
 if h is not None and (int(h)>23 or int(mi)>59 or se is not None and int(se)>59):return None
 if tz and tz!='Z' and (int(tz[1:3])>14 or int(tz[4:])>59):return None
 return {'year':y,'precision':'day' if day else 'month' if mo else 'year','date':f'{y:04}-{mo:02}-{day:02}' if day else None}
def profile(rows):
 ds=[r['duration_seconds']/60 for r in rows if isinstance(r['duration_seconds'],(int,float)) and r['duration_seconds']>=0]
 dates=[date_info(r['date_event']) for r in rows]
 located=lambda r: isinstance(r['lat'] if r['lat'] is not None else r['location_lat'],(int,float)) and isinstance(r['lng'] if r['lng'] is not None else r['location_lon'],(int,float)) and -90<=(r['lat'] if r['lat'] is not None else r['location_lat'])<=90 and -180<=(r['lng'] if r['lng'] is not None else r['location_lon'])<=180
 return {'records':len(rows),'distinct_ids':len({r['id'] for r in rows}),'valid_date':sum(x is not None for x in dates),'day_precision':sum(x is not None and x['precision']=='day' for x in dates),'valid_duration':len(ds),'duration_gt_60_min':sum(v>60 for v in ds),'duration_max_min':max(ds,default=None),'valid_coordinates':sum(located(r) for r in rows),'shape_present':sum(bool(r['standardized_shape']) for r in rows),'witnesses_present':sum(r['num_witnesses'] is not None for r in rows),'country_missing':sum(not r['country'] for r in rows),'sources':{s:sum(r['database_name']==s for r in rows) for s in sorted({r['database_name'] for r in rows})}}
def main():
 c=sqlite3.connect(DB.as_uri()+'?mode=ro',uri=True);c.execute('PRAGMA query_only=ON');c.row_factory=sqlite3.Row
 assert c.execute('PRAGMA query_only').fetchone()[0]==1
 country="(l.country IS NULL OR trim(l.country)='' OR lower(l.country) IN ('us','usa','united states','united states of america'))"
 specs={'general':("lower(l.state) IN ('ca','california','nv','nevada') AND ((s.date_event >= '1990' AND s.date_event < '2000') OR (s.date_event >= '2020' AND s.date_event < '2024')) AND "+country, {'start':1990,'end':2023,'region':'California y Nevada','intervals':[[1990,1999],[2020,2023]],'bounds':[-126,31,-113,43]})}
 for key,start,end,region,states,bounds in [('roswell',1944,1950,'Nuevo México y entorno',"'nm','new mexico','nuevo mexico'",[-109,31,-103,37]),('socorro',1961,1967,'Nuevo México y entorno',"'nm','new mexico','nuevo mexico'",[-109,31,-103,37]),('nimitz',2001,2007,'California y entorno',"'ca','california'",[-125,31,-114,42])]:
  west,south,east,north=bounds
  where=f"s.date_event >= '{start}' AND s.date_event < '{end+1}' AND {country} AND (lower(l.state) IN ({states}) OR (coalesce(s.lat,l.latitude) BETWEEN {south} AND {north} AND coalesce(s.lng,l.longitude) BETWEEN {west} AND {east}))"
  specs[key]=(where,{'start':start,'end':end,'region':region,'bounds':bounds})
 out={'generated':'2026-10-20','database':'ufo_public.db','database_bytes':DB.stat().st_size,'grain':'sighting.id; reports, not unique physical events','coordinates':'sighting.lat/lng; location fallback only if null. Precision not verified.','regional_rule':'State label or explicit context bounds; known non-US countries excluded. Unknown countries retained and counted.','snapshot':'complete query results, compact field projection, no sampling','cohorts':{}}
 for key,(where,meta) in specs.items():
  sql=BASE+'WHERE '+where+' ORDER BY s.date_event,s.id'
  rows=[dict(r) for r in c.execute(sql)]
  cols=list(rows[0]) if rows else []
  out['cohorts'][key]={**meta,'query':sql,'profile':profile(rows),'columns':cols,'rows':[[r[k] for k in cols] for r in rows]}
  print(key,json.dumps(out['cohorts'][key]['profile'],ensure_ascii=False))
 c.close();target=ROOT/'assets/analitica';target.mkdir(exist_ok=True)
 (target/'cohortes.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
 (target/'perfil.json').write_text(json.dumps({k:v for k,v in out.items() if k!='cohorts'}|{'cohorts':{k:{a:b for a,b in v.items() if a not in ('columns','rows')} for k,v in out['cohorts'].items()}},indent=2,ensure_ascii=False)+'\n')
if __name__=='__main__':main()
