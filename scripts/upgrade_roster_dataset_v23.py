from pathlib import Path

p=Path('free_data_v16.py'); s=p.read_text()
# imports needed for release-asset roster fallback
s=s.replace('import math\nimport numpy as np', 'import math\nfrom io import BytesIO\nimport requests\nimport numpy as np',1)
# load current season roster dataset directly from SportsDataverse release assets.
needle="""    prev_schedule=grab('schedules','cfb_schedule',int(year)-1)\n\n    resolved_week=int(week)\n"""
insert="""    prev_schedule=grab('schedules','cfb_schedule',int(year)-1)\n    try:\n        roster_url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_rosters/cfb_rosters_{int(year)}.parquet'\n        rr=requests.get(roster_url,timeout=(5,30),headers={'User-Agent':'Mozilla/5.0'})\n        rr.raise_for_status(); roster=pd.read_parquet(BytesIO(rr.content)); health['rosters']=len(roster)\n    except Exception as e:\n        roster=pd.DataFrame(); health['rosters']=0; errors['rosters']=str(e)\n\n    resolved_week=int(week)\n"""
if needle not in s: raise SystemExit('roster load marker missing')
s=s.replace(needle,insert,1)

needle="""        players['team']=players['team'].map(_canon_player_team)\n\n    cur_team=_team_baselines(team_box,resolved_week)\n"""
insert="""        players['team']=players['team'].map(_canon_player_team)\n\n    # Current-season roster is the source of truth for TODAY'S school. Prior-season\n    # box stats remain useful production evidence, but transfers inherit the new team's\n    # logo, opponent matchup and opportunity baseline.\n    roster_map={}\n    roster_rows=[]\n    if roster is not None and not roster.empty:\n        nc=base._col(roster,'athlete_display_name','player_name','athlete_name','player','athlete_full_name','full_name')\n        tc=base._col(roster,'team_display_name','team_short_display_name','team_location','school','team')\n        if nc and tc:\n            for _,row in roster.iterrows():\n                name=str(row.get(nc) or '').strip(); team=str(row.get(tc) or '').strip()\n                if not name or not team or name.lower()=='nan' or team.lower()=='nan':continue\n                if team.replace('.0','').isdigit():\n                    d=next((v for v in ctx.values() if isinstance(v,dict) and str(v.get('espn_id') or '') in {team,team.replace('.0','')}),{})\n                    team=str(d.get('canonical_name') or d.get('display_name') or team)\n                roster_map[_norm(name)]=team\n                roster_rows.append((name,team))\n    if players is None or players.empty:\n        players=pd.DataFrame(columns=['player','team','current_team','games','pass_yds','pass_att','pass_comp','pass_td','pass_int','rush_yds','rush_att','rush_td','rec_yds','receptions','rec_td','sample_source'])\n    if 'current_team' not in players.columns: players['current_team']=''\n    players['current_team']=players['player'].astype(str).map(lambda x: roster_map.get(_norm(x),'') if _norm(x) in roster_map else '')\n    existing=set(players['player'].astype(str).map(_norm))\n    add=[]\n    for name,team in roster_rows:\n        if _norm(name) in existing:continue\n        add.append({'player':name,'team':team,'current_team':team,'games':0,'pass_yds':0.0,'pass_att':0.0,'pass_comp':0.0,'pass_td':0.0,'pass_int':0.0,'rush_yds':0.0,'rush_att':0.0,'rush_td':0.0,'rec_yds':0.0,'receptions':0.0,'rec_td':0.0,'sample_source':'roster'})\n    if add: players=pd.concat([players,pd.DataFrame(add)],ignore_index=True,sort=False)\n\n    cur_team=_team_baselines(team_box,resolved_week)\n"""
if needle not in s: raise SystemExit('roster map marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)

p=Path('app.py'); s=p.read_text()
needle="""            # Resolve Underdog abbreviations to the full school used by the model/game board.\n            team=canonical_prop_team(r,row_game,pr)\n"""
insert="""            # Current-season roster identity overrides the historical sample school.\n            current_team=str(pr.get('current_team') or '')\n            team=''\n            if current_team:\n                for t in [row_game['away'],row_game['home']]:\n                    a,b=norm_name(current_team),norm_name(t)\n                    if a==b or (len(a)>=4 and (a in b or b in a)):\n                        team=t; break\n            if not team: team=canonical_prop_team(r,row_game,pr)\n"""
if needle not in s: raise SystemExit('app team override marker missing')
s=s.replace(needle,insert,1)

needle="""    if sample_source==\"prior\" and market_label in {\"Passing Yards\",\"Pass Attempts\",\"Completions\",\"Passing TDs\",\"Pass + Rush Yards\"}:\n        rel=clamp(gp/(gp+7.0),.18,.72)\n"""
insert="""    sample_team=str(player.get('team') or '')\n    current_team=str(player.get('current_team') or '')\n    transferred=bool(sample_source=='prior' and current_team and sample_team and norm_name(current_team)!=norm_name(sample_team))\n    if transferred and market_label in {\"Passing Yards\",\"Pass Attempts\",\"Completions\",\"Passing TDs\",\"Pass + Rush Yards\"}:\n        if team_pass>0: pass_y=team_pass*.90\n        if team_att>0: pass_att=team_att*.90\n        if team_comp>0: comp=team_comp*.90\n        if sf(team_ctx.get('team_pass_td_pg'))>0: pass_td=sf(team_ctx.get('team_pass_td_pg'))*.88\n        notes.append('transfer/current-role reset to new-team opportunity')\n    if sample_source==\"prior\" and not transferred and market_label in {\"Passing Yards\",\"Pass Attempts\",\"Completions\",\"Passing TDs\",\"Pass + Rush Yards\"}:\n        rel=clamp(gp/(gp+7.0),.18,.72)\n"""
if needle not in s: raise SystemExit('transfer marker missing')
s=s.replace(needle,insert,1)
s=s.replace('CFB Prop Engine v2.1 — NFL-STYLE FINAL BOARD + OPPORTUNITY CALIBRATION','CFB Prop Engine v2.3 — NFL-STYLE FINAL + CURRENT ROSTER OPPORTUNITY')
p.write_text(s)
print('v2.3 roster release patch applied')
