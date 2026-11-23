"""Package approved sketchbook populations, without touching or training on the source DB."""
from pathlib import Path
import json,sqlite3,hashlib
root=Path(__file__).parent
source=json.loads((root/'sketchbook-v2/data.json').read_text())
cards=[x for x in json.loads((root/'sketchbook-v2/propuestas-implementacion.json').read_text()) if x['id'] not in ['M14','M15','M16','M17']]
# Preserve the complete real populations, compactly; IDs remain DB IDs here.
rows={r['dbId']:r for k in ['ca','historic','ml'] for r in source[k]}
con=sqlite3.connect((root/'ufo_public.db').resolve().as_uri()+'?mode=ro',uri=True);con.execute('PRAGMA query_only=ON')
cols=[x[1]for x in con.execute('PRAGMA table_info(duplicate_candidate)')]
pairs=[]
if cols:
 query='SELECT * FROM duplicate_candidate'
 for values in con.execute(query):
  row=dict(zip(cols,values))
  # Store only pairs fully within this compact prototype population.
  ids=[v for k,v in row.items() if ('sighting' in k or 'record' in k) and isinstance(v,int) and v in rows]
  if len(set(ids))>=2:pairs.append({'ids':ids[:2],'raw':row})
con.close()
payload={'cards':cards,'rows':[{'dbId':i,'raw':r['raw'],'region':r['region']}for i,r in sorted(rows.items())], 'cohorts':{k:[r['dbId']for r in source[k]]for k in ['ca','historic','ml']},'grid':source['grid'],'pairs':pairs[:400], 'source':'sketchbook-v2/data.json','sourceSha256':hashlib.sha256((root/'sketchbook-v2/data.json').read_bytes()).hexdigest()}
(root/'assets/analitica/sketchbook-v2.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')))
print(json.dumps({'views':len(cards),'records':len(rows),'pairs':len(payload['pairs']),'cohorts':{k:len(v)for k,v in payload['cohorts'].items()}}))
