import json, traceback
import pandas as pd
from free_data_v15 import load_free_stack, _parquet, _col
from underdog_cfb_v15 import fetch_underdog_cfb_props

out={}
try:
    raw=_parquet('schedules',2026,'cfb_schedule')
    wc=_col(raw,'week','season_week')
    out['schedule_schema']={'columns':list(map(str,raw.columns)),'week_column':wc,'week_values':sorted(pd.to_numeric(raw[wc],errors='coerce').dropna().astype(int).unique().tolist()) if wc else [],'head':raw.head(3).astype(str).to_dict('records')}
except Exception as e:
    out['schedule_schema_error']=repr(e)
try:
    b,ctx,players,market=load_free_stack(2026,2)
    out['free']={'games':len(b.get('games',[])),'players':len(players),'teams':len(ctx),'markets':len(market),'health':b.get('free_health',{}),'errors':b.get('errors',{})}
except Exception as e:
    out['free_error']=repr(e); out['free_trace']=traceback.format_exc()[-2000:]
try:
    rows,debug=fetch_underdog_cfb_props(True)
    out['underdog']={'rows':len(rows),'debug':debug,'sample':rows[:5]}
except Exception as e:
    out['underdog_error']=repr(e); out['underdog_trace']=traceback.format_exc()[-2000:]
open('live_smoke_v15.json','w').write(json.dumps(out,indent=2,default=str))
print(json.dumps(out,indent=2,default=str))
