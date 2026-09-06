import json, traceback
from collections import Counter
from free_data_v16 import load_free_stack
from underdog_cfb_v15 import fetch_underdog_cfb_props

out={}
try:
    b,ctx,players,market=load_free_stack(2026,2)
    out['free']={'requested_week':b.get('requested_week'),'resolved_week':b.get('resolved_week'),'available_weeks':b.get('available_weeks'),
                 'games':len(b.get('games',[])),'players':len(players),'teams':len(ctx),'markets':len(market),'health':b.get('free_health',{}),'errors':b.get('errors',{}),
                 'game_sample':b.get('games',[])[:5]}
except Exception as e:
    out['free_error']=repr(e); out['free_trace']=traceback.format_exc()[-2000:]
try:
    rows,debug=fetch_underdog_cfb_props(True)
    counts=Counter(str(r.get('prop')) for r in rows)
    games=Counter(str(r.get('matchup')) for r in rows)
    out['underdog']={'rows':len(rows),'prop_counts':dict(counts.most_common()),'game_counts':dict(games.most_common(12)),'debug':debug,'sample':rows[:8]}
except Exception as e:
    out['underdog_error']=repr(e); out['underdog_trace']=traceback.format_exc()[-2000:]
open('live_smoke_v15.json','w').write(json.dumps(out,indent=2,default=str))
print(json.dumps(out,indent=2,default=str))
