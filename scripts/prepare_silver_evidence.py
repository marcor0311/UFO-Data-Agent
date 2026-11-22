"""Reproduce the pinned factual references from the original UFO-search JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def write_reference(path,document,field,entries):
    header=json.dumps(document,ensure_ascii=False,indent=2).rstrip()[:-1].rstrip()
    body=',\n'.join('    '+json.dumps(item,ensure_ascii=False,separators=(',',':')) for item in entries)
    path.write_text(header+',\n  "'+field+'": [\n'+body+'\n  ]\n}\n',encoding='utf-8')


def prepare(timeline):
    current=json.loads((ROOT/'config/silver-source-times.json').read_text(encoding='utf-8'))
    content=timeline.read_bytes()
    if hashlib.sha256(content).hexdigest()!=current['source']['sha256']:
        raise ValueError('El JSON no coincide con el snapshot original fijado')
    rows=json.loads(content.decode('utf-8-sig'))['Majestic Timeline']
    if len(rows)!=current['source']['records'] or len({r['source_id'] for r in rows})!=len(rows):
        raise ValueError('Conteo o identidad original inválidos')
    common={key:current[key] for key in ('version','source_name','source')}
    times=[{'source_record_id':r['source_id'],'date_event_raw':r['date'].strip(),
            'time_raw':r['time'],'single_date':not bool(r.get('alt_date') or r.get('end_date'))}
           for r in rows if r.get('time')]
    places=[]
    for row in rows:
        values=row['key_vals']
        if row['source'] not in ('Hatch','NukeExplosions') or not values.get('LatLong'):
            continue
        lat,lng=map(float,values['LatLong'].replace(',',' ').split())
        places.append({'source_record_id':row['source_id'],'date_event_raw':row['date'].strip(),
                       'latitude':lat,'longitude':lng,'country':values.get('Country') or ''})
    write_reference(ROOT/'config/silver-source-times.json',
        {**common,'scope':'Original factual date and clock fields only; joined by unique source_record_id and exact raw date. No narrative text.'},'times',times)
    write_reference(ROOT/'config/silver-source-geography.json',
        {**common,'scope':'Original catalogue coordinates and country labels, not a verified witness position. NukeCountry is not treated as geographic country. No narrative text.'},'geography',places)
    return len(times),len(places)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeline',type=Path,required=True)
    args=parser.parse_args()
    times,places=prepare(args.timeline)
    print(f'Referencias reproducidas: {times} horas; {places} geografías.')
