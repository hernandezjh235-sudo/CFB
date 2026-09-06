from pathlib import Path

# --- free_data_v16.py: canonicalize numeric team IDs on player rows ---
p=Path('free_data_v16.py'); s=p.read_text()
needle="""    cur_team=_team_baselines(team_box,resolved_week)\n"""
insert="""    # Player-box team fields can be ESPN numeric IDs. Convert them to the same\n    # canonical school names used by the game/context layer so logos, opponents,\n    # and matchup metrics resolve correctly in the player board.\n    if players is not None and not players.empty and 'team' in players.columns:\n        id_to_name={}\n        for key,d in list(ctx.items()):\n            if not isinstance(d,dict):continue\n            eid=str(d.get('espn_id') or '').strip()\n            cname=str(d.get('canonical_name') or key or '').strip()\n            if eid and eid.lower()!='nan' and cname:\n                id_to_name[eid]=cname\n        def _canon_player_team(v):\n            raw=str(v or '').strip()\n            if raw in id_to_name:return id_to_name[raw]\n            d=ctx.get(raw,{}) or {}\n            return str(d.get('canonical_name') or raw)\n        players['team']=players['team'].map(_canon_player_team)\n\n    cur_team=_team_baselines(team_box,resolved_week)\n"""
if needle not in s: raise SystemExit('free_data insertion marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)

# --- app.py: opportunity reliability + no fake 100% confidence ---
p=Path('app.py'); s=p.read_text()
needle="""    pass_td=sf(player.get(\"pass_td\"))/gp; ints=sf(player.get(\"pass_int\"))/gp\n    # NFL-app style opening-week fallback: use independent team production baselines\n"""
insert="""    pass_td=sf(player.get(\"pass_td\"))/gp; ints=sf(player.get(\"pass_int\"))/gp\n    sample_source=str(player.get(\"sample_source\") or \"current\").lower()\n    # Opening-week opportunity correction: an active QB/skill prop indicates the\n    # player has a meaningful current role, while an old tiny backup sample may not.\n    # We do NOT use the sportsbook line value to set the projection; we only shrink\n    # stale/small personal samples toward independent team production.\n    team_pass=sf(team_ctx.get(\"team_pass_yds_pg\")); team_att=sf(team_ctx.get(\"team_pass_att_pg\")); team_comp=sf(team_ctx.get(\"team_pass_comp_pg\"))\n    if sample_source==\"prior\" and market_label in {\"Passing Yards\",\"Pass Attempts\",\"Completions\",\"Passing TDs\",\"Pass + Rush Yards\"}:\n        rel=clamp(gp/(gp+7.0),.18,.72)\n        if team_pass>0 and (pass_y<=0 or pass_y < team_pass*.62):\n            pass_y=rel*pass_y + (1-rel)*(team_pass*.90); notes.append(\"role reset: prior backup sample shrunk to team QB baseline\")\n        if team_att>0 and (pass_att<=0 or pass_att < team_att*.62): pass_att=rel*pass_att + (1-rel)*(team_att*.90)\n        if team_comp>0 and (comp<=0 or comp < team_comp*.62): comp=rel*comp + (1-rel)*(team_comp*.90)\n    # NFL-app style opening-week fallback: use independent team production baselines\n"""
if needle not in s: raise SystemExit('app opportunity marker missing')
s=s.replace(needle,insert,1)

needle="""            p=prop_probability(proj,r.get(\"line\"),sd,side)\n            edge=proj-sf(r.get(\"line\")); edge = edge if side==\"Over\" else -edge\n            status=\"PLAYABLE\" if p>=.60 and proj>0 else \"LEAN\" if p>=.56 and proj>0 else \"TRACK\"\n"""
insert="""            p=prop_probability(proj,r.get(\"line\"),sd,side)\n            # Reliability calibration. Early CFB samples and prior-season role changes\n            # should never print fake 98-100% certainty. Keep direction/edge intact\n            # while widening uncertainty until current-season opportunity is proven.\n            src=str(pr.get(\"sample_source\") or \"fallback\").lower(); gp=sf(pr.get(\"games\"),0)\n            if src==\"current\": pcap=.72 if gp<=1 else (.80 if gp<=3 else .88)\n            elif src==\"prior\": pcap=.76 if gp>=8 else .70\n            else: pcap=.66\n            p=min(max(p,1-pcap),pcap)\n            edge=proj-sf(r.get(\"line\")); edge = edge if side==\"Over\" else -edge\n            status=\"PLAYABLE\" if p>=.60 and proj>0 else \"LEAN\" if p>=.56 and proj>0 else \"TRACK\"\n"""
if needle not in s: raise SystemExit('app probability marker missing')
s=s.replace(needle,insert,1)
s=s.replace('CFB Prop Engine v2.0 — NFL-STYLE AUTO SLATE + PLAYER BASELINES','CFB Prop Engine v2.1 — NFL-STYLE FINAL BOARD + OPPORTUNITY CALIBRATION')
p.write_text(s)

# --- cfb_nfl_ui_v18.py: team logos + green OVER / red UNDER ---
p=Path('cfb_nfl_ui_v18.py'); s=p.read_text()
cssneedle=""".cfb18-cell{text-align:center}.cfb18-cell b{display:block;font-size:12px}.cfb18-cell span{font-size:7px;color:#7e92a5;text-transform:uppercase;font-weight:900}\n"""
cssinsert=""".cfb18-cell{text-align:center}.cfb18-cell b{display:block;font-size:12px}.cfb18-cell span{font-size:7px;color:#7e92a5;text-transform:uppercase;font-weight:900}.cfb18-side-over{color:#55e991!important}.cfb18-side-under{color:#ff6f7d!important}.cfb18-logo-wrap{width:36px;height:36px;display:flex;align-items:center;justify-content:center}.cfb18-logo-fallback{width:30px;height:30px;border-radius:50%;background:#142131;border:1px solid #2a3d50;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:900;color:#9cb0c3}\n"""
if cssneedle not in s: raise SystemExit('ui css marker missing')
s=s.replace(cssneedle,cssinsert,1)

# player cards: color full side label
old="""<div class=\"cfb18-val\">{html.escape(side.upper())} {_fmt(r.get('line'))}</div>"""
new="""<div class=\"cfb18-val {'cfb18-side-over' if side.lower()=='over' else 'cfb18-side-under'}\">{html.escape(side.upper())} {_fmt(r.get('line'))}</div>"""
s=s.replace(old,new)

# fast rows: robust logo fallback + full colored OVER/UNDER label
old="""        lg=f\"<img src='{html.escape(logo,quote=True)}' alt='{html.escape(team)} logo' loading='lazy' onerror=\\\"this.style.display='none'\\\">\" if logo else '<div></div>'\n        bits.append(f'''<div class=\"cfb18-row\" style=\"--team:{color}\">{lg}<div><div class=\"cfb18-rowname\">#{i} {html.escape(str(r.get('player') or ''))}</div><div class=\"cfb18-rowsub\">{html.escape(team)} VS {html.escape(opp)}</div></div><div class=\"cfb18-cell\"><span>Prop</span><b>{html.escape(str(r.get('prop') or ''))}</b></div><div class=\"cfb18-cell\"><span>Line</span><b>{html.escape(str(r.get('side') or ''))[:1].upper()} {_fmt(r.get('line'))}</b></div><div class=\"cfb18-cell\"><span>Proj</span><b>{_fmt(r.get('projection'))}</b></div><div class=\"cfb18-cell hide-mobile\"><span>Edge</span><b>{_num(r.get('edge')):+.1f}</b></div><div class=\"cfb18-cell hide-mobile\"><span>Likely</span><b>{_pct(r.get('probability')):.0f}%</b></div></div>''')\n"""
new="""        abbr=_abbr(ctx,team); side=str(r.get('side') or 'Over'); side_cls='cfb18-side-over' if side.lower()=='over' else 'cfb18-side-under'\n        lg=(f\"<div class='cfb18-logo-wrap'><img src='{html.escape(logo,quote=True)}' alt='{html.escape(team)} logo' loading='lazy' onerror=\\\"this.style.display='none'\\\"></div>\" if logo else f\"<div class='cfb18-logo-wrap'><div class='cfb18-logo-fallback'>{html.escape(abbr[:4])}</div></div>\")\n        bits.append(f'''<div class=\"cfb18-row\" style=\"--team:{color}\">{lg}<div><div class=\"cfb18-rowname\">#{i} {html.escape(str(r.get('player') or ''))}</div><div class=\"cfb18-rowsub\">{html.escape(team)} VS {html.escape(opp)}</div></div><div class=\"cfb18-cell\"><span>Prop</span><b>{html.escape(str(r.get('prop') or ''))}</b></div><div class=\"cfb18-cell\"><span>Line</span><b class=\"{side_cls}\">{html.escape(side.upper())} {_fmt(r.get('line'))}</b></div><div class=\"cfb18-cell\"><span>Proj</span><b>{_fmt(r.get('projection'))}</b></div><div class=\"cfb18-cell hide-mobile\"><span>Edge</span><b>{_num(r.get('edge')):+.1f}</b></div><div class=\"cfb18-cell hide-mobile\"><span>Likely</span><b>{_pct(r.get('probability')):.0f}%</b></div></div>''')\n"""
if old not in s: raise SystemExit('fast row marker missing')
s=s.replace(old,new,1)
p.write_text(s)
print('v2.1 patch applied')
