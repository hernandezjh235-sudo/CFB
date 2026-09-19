from pathlib import Path
import re

p=Path("cfb_runtime_v20.py")
s=p.read_text()
old="def games_from_props(rows:List[dict],ctx:Dict[str,dict])->List[dict]:"
if old not in s:
    raise SystemExit("games_from_props marker missing")
# Add a second-pass ESPN reconciler without changing provider data.
marker="\ndef _branding_from_games"
fn=r'''
def reconcile_prop_games(rows:List[dict],ctx:Dict[str,dict])->List[dict]:
    raw=games_from_props(rows,ctx)
    out=[]
    for g in raw:
        dt=local_game_dt(g)
        espn=espn_games_for_date(dt.strftime('%Y%m%d')) if dt else []
        ga=_norm(g.get('away_team')); gh=_norm(g.get('home_team'))
        best=None
        for e in espn:
            ea=_norm(e.get('away_team')); eh=_norm(e.get('home_team'))
            aa=_norm(e.get('away_abbreviation')); ha=_norm(e.get('home_abbreviation'))
            am=(ga==ea or ga==aa or (len(ga)>=5 and (ga in ea or ea in ga)))
            hm=(gh==eh or gh==ha or (len(gh)>=5 and (gh in eh or eh in gh)))
            if am and hm:
                best=e; break
        if best:
            q=dict(g); q.update(best); q['prop_event_id']=g.get('id'); q['source']='PropLine + ESPN reconciled'; out.append(q)
        else:
            out.append(g)
    return out

'''
if "def reconcile_prop_games" not in s:
    s=s.replace(marker,"\n"+fn+marker.lstrip("\n"),1)
p.write_text(s)

p=Path("app.py"); s=p.read_text()
s=s.replace("games_from_props)", "games_from_props, reconcile_prop_games)")
s=s.replace('CFB Prop Engine v3.7 — SEASON ANCHOR + LOGO RESTORE','CFB Prop Engine v3.8 — EVENT LOCK + PROJECTION VERIFY')
s=s.replace("games_from_props(prop_rows,ctx)","reconcile_prop_games(prop_rows,ctx)")
needle='q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj'
repl='q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection_source":str(model_pr.get("sample_source") or "unknown").upper(),"sample_games":int(sf(model_pr.get("games"),0)),"projection":proj'
s=s.replace(needle,repl)
p.write_text(s)

p=Path("cfb_nfl_ui_v18.py"); s=p.read_text()
old="logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _isaway else str(game.get('home_logo') or '') if _ishome else '') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{_eid}.png' if _eid else '')"
new="logo=(str(game.get('away_logo') or '') if _isaway else str(game.get('home_logo') or '') if _ishome else '') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{_eid}.png' if _eid else '') or _logo(ctx,team)"
s=s.replace(old,new)
p.write_text(s)

for f in ["cfb_runtime_v20.py","app.py","cfb_nfl_ui_v18.py"]:
    compile(Path(f).read_text(),f,"exec")
print("v3.8 ready")

# trigger workflow
