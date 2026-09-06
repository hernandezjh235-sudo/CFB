from pathlib import Path

p=Path('free_data_v16.py'); s=p.read_text()
needle="""    team_box=grab('team_box','team_box')\n    prev_player_box=grab('player_box','player_box',int(year)-1)\n"""
insert="""    team_box=grab('team_box','team_box')\n    rosters=grab('rosters','rosters')\n    game_rosters=grab('game_rosters','game_rosters')\n    injuries=grab('injuries','injuries')\n    adv_passing=grab('adv_passing','adv_passing')\n    adv_rushing=grab('adv_rushing','adv_rushing')\n    adv_receiving=grab('adv_receiving','adv_receiving')\n    adv_situational=grab('adv_situational','adv_situational')\n    prev_player_box=grab('player_box','player_box',int(year)-1)\n"""
if needle not in s: raise SystemExit('free source marker missing')
s=s.replace(needle,insert,1)
if 'def _clean_team_id(' not in s:
    marker='''\ndef _merge_player_banks(current:pd.DataFrame, previous:pd.DataFrame)->pd.DataFrame:\n'''
    fn='''\ndef _clean_team_id(v):\n    raw=str(v or '').strip()\n    if raw.lower() in {'','nan','none'}: return ''\n    try:\n        f=float(raw)\n        if f.is_integer(): return str(int(f))\n    except Exception: pass\n    return raw\n\ndef _roster_map(*dfs):\n    out={}\n    for df in dfs:\n        if df is None or df.empty: continue\n        pc=base._col(df,'athlete_display_name','player_name','athlete_name','display_name','full_name','player','name')\n        tc=base._col(df,'team_display_name','team_name','school','team','team_abbreviation')\n        if not pc or not tc: continue\n        for _,r in df.iterrows():\n            p=str(r.get(pc) or '').strip(); t=str(r.get(tc) or '').strip()\n            if p and t and p.lower()!='nan' and t.lower()!='nan': out[_norm(p)]=t\n    return out\n\ndef _auto_injury_rows(df):\n    if df is None or df.empty:return []\n    pc=base._col(df,'athlete_display_name','player_name','athlete_name','display_name','player','name')\n    sc=base._col(df,'status','injury_status','designation','type')\n    tc=base._col(df,'team_display_name','team_name','school','team')\n    if not pc:return []\n    out=[]\n    for _,r in df.iterrows():\n        p=str(r.get(pc) or '').strip()\n        if not p or p.lower()=='nan':continue\n        out.append({'player':p,'team':str(r.get(tc) or '') if tc else '', 'status':str(r.get(sc) or '') if sc else '', 'expected_snap_pct':100, 'source':'SportsDataverse injuries'})\n    return out\n\n'''
    s=s.replace(marker,fn+marker,1)
s=s.replace("eid=str(rr.get(ic) or '').strip() if ic else ''", "eid=_clean_team_id(rr.get(ic)) if ic else ''")
s=s.replace("eid=str(d.get('espn_id') or '').strip()", "eid=_clean_team_id(d.get('espn_id'))")
needle="""    if players is not None and not players.empty and 'team' in players.columns:\n        id_to_name={}\n"""
insert="""    current_roster=_roster_map(rosters,game_rosters)\n    if players is not None and not players.empty:\n        players['current_team']=players['player'].astype(str).map(lambda x: current_roster.get(_norm(x),'') if current_roster else '')\n    if players is not None and not players.empty and 'team' in players.columns:\n        id_to_name={}\n"""
if needle not in s: raise SystemExit('roster map insertion marker missing')
s=s.replace(needle,insert,1)
needle="""    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],\n            'player_stats':[],'advanced':[],'errors':errors,'free_health':health,\n            'requested_week':int(week),'resolved_week':resolved_week,'available_weeks':available}\n"""
insert="""    auto_injuries=_auto_injury_rows(injuries)\n    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],\n            'player_stats':[],'advanced':[], 'auto_injuries':auto_injuries,\n            'current_roster_count':len(current_roster),\n            'advanced_player_health':{'passing':len(adv_passing),'rushing':len(adv_rushing),'receiving':len(adv_receiving),'situational':len(adv_situational)},\n            'errors':errors,'free_health':health,\n            'requested_week':int(week),'resolved_week':resolved_week,'available_weeks':available}\n"""
if needle not in s: raise SystemExit('bundle marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)

p=Path('cfb_runtime_v20.py'); s=p.read_text()
needle="""    player=player or {}; raw=str(row.get('team') or ''); pr=str(player.get('team') or '')\n    away=str(game.get('away') or game.get('away_team') or ''); home=str(game.get('home') or game.get('home_team') or '')\n"""
insert="""    player=player or {}; raw=str(row.get('team') or ''); pr=str(player.get('team') or ''); current=str(player.get('current_team') or '')\n    away=str(game.get('away') or game.get('away_team') or ''); home=str(game.get('home') or game.get('home_team') or '')\n"""
if needle not in s: raise SystemExit('runtime canonical marker missing')
s=s.replace(needle,insert,1)
needle="""    n=_norm(raw)\n    if n and n==_norm(aa):return away\n"""
insert="""    cn=_norm(current)\n    for full,abbr in ((away,aa),(home,ha)):\n        fn=_norm(full); an=_norm(abbr)\n        if cn and (cn==fn or cn==an or cn in fn or fn in cn): return full\n    n=_norm(raw)\n    if n and n==_norm(aa):return away\n"""
if needle not in s: raise SystemExit('runtime current-team marker missing')
s=s.replace(needle,insert,1)
needle="""    pn=_norm(pr)\n    for full in (away,home):\n        if pn and pn==_norm(full):return full\n    return raw or pr\n"""
insert="""    pn=_norm(pr)\n    for full in (away,home):\n        if pn and pn==_norm(full):return full\n    return raw if raw else (current if current else '')\n"""
if needle not in s: raise SystemExit('runtime stale-team marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)

p=Path('app.py'); s=p.read_text()
s=s.replace('CFB Prop Engine v2.1 — NFL-STYLE FINAL BOARD + OPPORTUNITY CALIBRATION','CFB Prop Engine v2.3 — NFL-STYLE COMPLETE DATA + OPPORTUNITY AUDIT')
needle='''injuries_df=load_optional_csv("injuries.csv")\ndepth_df=load_optional_csv("depth_chart.csv")\n'''
insert='''injuries_df=load_optional_csv("injuries.csv")\nauto_injuries_df=pd.DataFrame(bundle.get("auto_injuries",[])) if isinstance(bundle,dict) else pd.DataFrame()\nif not auto_injuries_df.empty:\n    injuries_df=pd.concat([auto_injuries_df,injuries_df],ignore_index=True,sort=False) if not injuries_df.empty else auto_injuries_df\ndepth_df=load_optional_csv("depth_chart.csv")\n'''
if needle not in s: raise SystemExit('app injury merge marker missing')
s=s.replace(needle,insert,1)
needle='''            team=canonical_prop_team(r,row_game,pr)\n            opp=row_game["home"] if team==row_game["away"] else row_game["away"]\n'''
insert='''            team=canonical_prop_team(r,row_game,pr)\n            if not team:\n                cand=str(pr.get("current_team") or pr.get("team") or "")\n                for full in (row_game.get("away",""),row_game.get("home","")):\n                    if cand and norm_name(cand)==norm_name(full): team=full; break\n            opp=row_game["home"] if team==row_game["away"] else row_game["away"]\n'''
if needle not in s: raise SystemExit('app team inference marker missing')
s=s.replace(needle,insert,1)
needle='''            src=str(pr.get("sample_source") or "fallback").lower(); gp=sf(pr.get("games"),0)\n            if src=="current": pcap=.72 if gp<=1 else (.80 if gp<=3 else .88)\n            elif src=="prior": pcap=.76 if gp>=8 else .70\n            else: pcap=.66\n            p=min(max(p,1-pcap),pcap)\n'''
insert='''            src=str(pr.get("sample_source") or "fallback").lower(); gp=sf(pr.get("games"),0)\n            current_team=str(pr.get("current_team") or "")\n            transferred=bool(current_team and pr.get("team") and norm_name(current_team)!=norm_name(pr.get("team")))\n            roster_confirmed=bool(current_team) or src=="current"\n            if src=="current": pcap=.72 if gp<=1 else (.80 if gp<=3 else .88)\n            elif src=="prior": pcap=.72 if (roster_confirmed and gp>=8) else .66\n            else: pcap=.62\n            if transferred: pcap=min(pcap,.66)\n            if not team or norm_name(team) not in {norm_name(row_game.get("away")),norm_name(row_game.get("home"))}: pcap=min(pcap,.58)\n            p=min(max(p,1-pcap),pcap)\n'''
if needle not in s: raise SystemExit('app reliability marker missing')
s=s.replace(needle,insert,1)
needle='''            status="PLAYABLE" if p>=.60 and proj>0 else "LEAN" if p>=.56 and proj>0 else "TRACK"\n            q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(notes)}\n'''
insert='''            status="PLAYABLE" if p>=.60 and proj>0 else "LEAN" if p>=.56 and proj>0 else "TRACK"\n            if not roster_confirmed and src=="prior": status="TRACK"\n            if transferred: notes.append("current-team transfer/role uncertainty")\n            if current_team: notes.append("current roster team confirmed")\n            q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(dict.fromkeys(notes))}\n'''
if needle not in s: raise SystemExit('app status marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)
print('v2.3 complete-data opportunity patch applied')
