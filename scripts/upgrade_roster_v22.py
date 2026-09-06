from pathlib import Path

p=Path('cfb_runtime_v20.py'); s=p.read_text()
if 'def current_roster_team(' not in s:
    marker='''\ndef canonical_prop_team(row:dict,game:dict,player:dict=None)->str:\n'''
    fn='''\n@lru_cache(maxsize=256)\ndef espn_team_roster(espn_id:str)->Dict[str,str]:\n    out={}\n    eid=str(espn_id or '').strip()\n    if not eid:return out\n    try:\n        url=f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{eid}/roster'\n        # ESPN site-v2 CFB endpoints can reject spoofed browser user agents.\n        # Use the same light headers cfbfastR uses.\n        headers={'Accept':'application/json, text/plain, */*','Origin':'https://www.espn.com','Referer':'https://www.espn.com/'}\n        r=requests.get(url,timeout=(4,12),headers=headers)\n        r.raise_for_status(); j=r.json()\n        def walk(x):\n            if isinstance(x,dict):\n                a=x.get('athlete') if isinstance(x.get('athlete'),dict) else x\n                name=a.get('displayName') or a.get('fullName') or a.get('shortName')\n                if name and (a.get('id') or a.get('position') or a.get('jersey')):\n                    out[_norm(name)]=str(name)\n                for v in x.values():walk(v)\n            elif isinstance(x,list):\n                for v in x:walk(v)\n        walk(j)\n    except Exception:pass\n    return out\n\ndef current_roster_team(player_name:str,game:dict)->str:\n    n=_norm(player_name)\n    for side in ('away','home'):\n        team=str(game.get(side) or game.get(f'{side}_team') or '')\n        eid=str(game.get(f'{side}_espn_id') or '')\n        if n and n in espn_team_roster(eid):return team\n    return ''\n\n'''
    if marker not in s: raise SystemExit('runtime roster marker missing')
    s=s.replace(marker,fn+marker,1)
p.write_text(s)

p=Path('app.py'); s=p.read_text()
s=s.replace('prop_rows_date_label, games_from_props)', 'prop_rows_date_label, games_from_props, current_roster_team)')
needle='''            # Resolve Underdog abbreviations to the full school used by the model/game board.\n            team=canonical_prop_team(r,row_game,pr)\n'''
insert='''            # Resolve CURRENT roster identity before prior-season school identity.\n            roster_team=current_roster_team(r.get("player",""),row_game)\n            team=roster_team or canonical_prop_team(r,row_game,pr)\n'''
if needle not in s: raise SystemExit('app roster marker missing')
s=s.replace(needle,insert,1)

needle='''    if sample_source=="prior" and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Pass + Rush Yards"}:\n        rel=clamp(gp/(gp+7.0),.18,.72)\n'''
insert='''    transferred=bool(player.get("team") and team_name and norm_name(player.get("team"))!=norm_name(team_name))\n    if sample_source=="prior" and transferred and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Pass + Rush Yards"}:\n        if team_pass>0: pass_y=team_pass*.90\n        if team_att>0: pass_att=team_att*.90\n        if team_comp>0: comp=team_comp*.90\n        if sf(team_ctx.get("team_pass_td_pg"))>0: pass_td=sf(team_ctx.get("team_pass_td_pg"))*.88\n        notes.append("transfer/current-role reset to new-team QB opportunity")\n    if sample_source=="prior" and not transferred and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Pass + Rush Yards"}:\n        rel=clamp(gp/(gp+7.0),.18,.72)\n'''
if needle not in s: raise SystemExit('app transfer opportunity marker missing')
s=s.replace(needle,insert,1)
s=s.replace('CFB Prop Engine v2.1 — NFL-STYLE FINAL BOARD + OPPORTUNITY CALIBRATION','CFB Prop Engine v2.2 — NFL-STYLE FINAL + CURRENT ROSTER OPPORTUNITY')
p.write_text(s)
print('v2.2 roster-aware patch applied')
