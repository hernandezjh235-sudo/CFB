from pathlib import Path

app=Path('app.py')
s=app.read_text()

s=s.replace("from cfb_runtime_v20 import (annotate_games, ensure_branding, filter_games_by_scope, filter_props_by_scope,\n    local_now, scope_target_date, logo_coverage, day_games, canonical_prop_team, prop_rows_date_label, games_from_props)\n",
"from cfb_runtime_v20 import (annotate_games, ensure_branding, filter_games_by_scope, filter_props_by_scope,\n    local_now, scope_target_date, logo_coverage, day_games, canonical_prop_team, prop_rows_date_label, games_from_props)\nfrom cfb_opportunity_v25 import enrich_opportunity, automatic_weather\n")
s=s.replace('APP_VERSION = "CFB Prop Engine v2.4 — NFL-STYLE COMPLETE OPPORTUNITY + ADVANCED DATA"','APP_VERSION = "CFB Prop Engine v2.5 — DRIVE + HOOK + EXPLOSIVE + PRESSURE + AUTO WEATHER"')

anchor='''    else:\n        bundle,ctx,players,market_map=load_free_stack(int(year),int(week))\n        data_mode="FREE SportsDataverse/NCAA"\nctx=hydrate_team_branding(ctx)\n'''
replace='''    else:\n        bundle,ctx,players,market_map=load_free_stack(int(year),int(week))\n        data_mode="FREE SportsDataverse/NCAA"\n    # v2.5: enrich both free and optional-CFBD modes with the same no-key CFB\n    # drive/opportunity context. This layer never uses the sportsbook line to set a projection.\n    ctx,players,opportunity_health=enrich_opportunity(int(year),int(bundle.get("resolved_week",week) if isinstance(bundle,dict) else week),ctx,players)\n    if isinstance(bundle,dict):\n        bundle.setdefault("free_health",{}).update({f"v25_{k}":v for k,v in opportunity_health.items()})\nctx=hydrate_team_branding(ctx)\n'''
if anchor not in s: raise SystemExit('load anchor not found')
s=s.replace(anchor,replace,1)

old='''    # Total uses offense-v-defense + pace + explosiveness. Baseline 55 is close to modern FBS scoring environment and is recalibrated by grading.\n    h_off=sf(h.get("off_rating")); a_off=sf(a.get("off_rating")); h_def=sf(h.get("def_rating")); a_def=sf(a.get("def_rating"))\n    pace=(sf(h.get("pace"))+sf(a.get("pace")))/2\n    expl=(sf(h.get("off_expl"))+sf(a.get("off_expl"))-sf(h.get("def_expl"))-sf(a.get("def_expl")))/4\n    total=55.0 + .28*(h_off+a_off) - .20*(h_def+a_def) + .10*pace + .08*expl\n    total=clamp(total,34,86)\n'''
new='''    # v2.5 total: offense/defense remains the stable prior, while actual possessions,\n    # drive success, third-down sustain, turnovers and explosives determine opportunity.\n    h_off=sf(h.get("off_rating")); a_off=sf(a.get("off_rating")); h_def=sf(h.get("def_rating")); a_def=sf(a.get("def_rating"))\n    pace=(sf(h.get("pace"))+sf(a.get("pace")))/2\n    expl=(sf(h.get("off_expl"))+sf(a.get("off_expl"))-sf(h.get("def_expl"))-sf(a.get("def_expl")))/4\n    drive_pg=np.mean([x for x in [sf(h.get('drives_pg')),sf(a.get('drives_pg'))] if x>0]) if any(sf(x.get('drives_pg'))>0 for x in [h,a]) else 11.5\n    score_rate=np.mean([x for x in [sf(h.get('score_drive_rate')),sf(a.get('score_drive_rate'))] if x>0]) if any(sf(x.get('score_drive_rate'))>0 for x in [h,a]) else .34\n    td_rate=np.mean([x for x in [sf(h.get('td_drive_rate')),sf(a.get('td_drive_rate'))] if x>0]) if any(sf(x.get('td_drive_rate'))>0 for x in [h,a]) else .24\n    sustain=np.mean([sf(h.get('third_down_rate')),sf(a.get('third_down_rate')),sf(h.get('third_down_success_rate')),sf(a.get('third_down_success_rate'))])\n    turnovers=sf(h.get('turnovers_pg'))+sf(a.get('turnovers_pg'))\n    ypp=np.mean([x for x in [sf(h.get('yards_per_play')),sf(a.get('yards_per_play'))] if x>0]) if any(sf(x.get('yards_per_play'))>0 for x in [h,a]) else 5.7\n    drive_signal=clamp((drive_pg-11.5)*1.0 + (score_rate-.34)*24 + (td_rate-.24)*18 + (sustain-.40)*8 - max(turnovers-2.2,0)*.8 + (ypp-5.7)*1.2,-8,9)\n    total=55.0 + .25*(h_off+a_off) - .18*(h_def+a_def) + .08*pace + .07*expl + drive_signal\n    total=clamp(total,34,86)\n'''
if old not in s: raise SystemExit('project total block not found')
s=s.replace(old,new,1)

# Add CFB-specific opportunity adjustments immediately after snap_adj logic.
needle='''    if is_fav and blow>.55:\n        snap_adj=1.0-(blow-.55)*.24\n        notes.append("blowout playing-time tax")\n    elif not is_fav and blow>.60:\n        notes.append("underdog catch-up volume")\n'''
insert='''    if is_fav and blow>.55:\n        snap_adj=1.0-(blow-.55)*.24\n        notes.append("blowout playing-time tax")\n    elif not is_fav and blow>.60:\n        notes.append("underdog catch-up volume")\n    # CFB starters get pulled much earlier than NFL starters. Use actual QB1 share and\n    # current roster starter status to make the hook tax role-aware.\n    qb1_share=clamp(sf(team_ctx.get('qb1_attempt_share')),0,1)\n    starter_current=bool(player.get('starter_current'))\n    if is_fav and blow>.52 and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Receiving Yards","Receptions","Pass + Rush Yards"}:\n        hook=(blow-.52)*(.32 if qb1_share<.86 else .24)\n        snap_adj*=clamp(1-hook,.76,1.0); notes.append("CFB starter hook/share adjustment")\n    if starter_current: notes.append("current starter confirmed")\n'''
if needle not in s: raise SystemExit('snap block not found')
s=s.replace(needle,insert,1)

# Add contextual variables after advanced player variables.
needle2="""    adv_tar=sf(player.get('adv_targets')); adv_catch=sf(player.get('adv_catch_rate')); adv_ypt=sf(player.get('adv_ypt')); adv_rec_epa=sf(player.get('adv_rec_epa')); target_share=clamp(sf(player.get('adv_target_share')),0,.58)\n"""
insert2=needle2+"""    air_share=clamp(sf(player.get('air_yard_share')),0,.80); qb_rush_share=clamp(sf(player.get('qb_rush_share')),0,.65); sack_rate=clamp(sf(player.get('sack_rate')),0,.30)\n    drives=sf(team_ctx.get('drives_pg'),11.5); plays_drive=sf(team_ctx.get('plays_per_drive'),5.7); score_drive=sf(team_ctx.get('score_drive_rate'),.34); rz=sf(team_ctx.get('red_zone_success_rate'),.55)\n    early_pass=sf(team_ctx.get('early_down_pass_rate')); early_rush=sf(team_ctx.get('early_down_rush_rate')); start_field=sf(team_ctx.get('avg_start_yard_line'),50)\n    volume_drive=clamp(1+(drives-11.5)*.018+(plays_drive-5.7)*.015,.90,1.12)\n    scoring_env=clamp(1+(score_drive-.34)*.18+(rz-.55)*.10+(start_field-50)*.002,.90,1.12)\n"""
s=s.replace(needle2,insert2,1)

# Passing advanced projection: add pressure, drive volume, early-down pass tendency.
oldp='''            eff=clamp(1+adv_cpoe*.20+adv_pass_epa*.07,.92,1.09)\n            proj=exp_att*ypa*eff*pass_match\n            notes.append("attempt share × YPA advanced opportunity")\n'''
newp='''            pressure_tax=clamp(1-sack_rate*.30-max(sf(opp_ctx.get('havoc')),0)*.004,.88,1.03)\n            pass_tendency=clamp(1+(early_pass-.50)*.10,.94,1.06) if early_pass>0 else 1.0\n            eff=clamp(1+adv_cpoe*.20+adv_pass_epa*.07,.92,1.09)\n            proj=exp_att*ypa*eff*pass_match*pressure_tax*volume_drive*pass_tendency\n            notes.append("attempt share × YPA + drive/pressure opportunity")\n'''
if oldp not in s: raise SystemExit('pass block not found')
s=s.replace(oldp,newp,1)

oldr='''            eff=clamp(1+adv_rush_epa*.08,.92,1.08)\n            proj=exp_car*adv_ypc*eff*rush_match\n            notes.append("carry share × YPC advanced opportunity")\n'''
newr='''            rush_tendency=clamp(1+(early_rush-.50)*.10,.94,1.07) if early_rush>0 else 1.0\n            eff=clamp(1+adv_rush_epa*.08,.92,1.08)\n            proj=exp_car*adv_ypc*eff*rush_match*volume_drive*rush_tendency\n            # Dual-threat QBs require a separate scramble/designed-run opportunity bump.\n            if adv_att>0 and qb_rush_share>0: proj*=clamp(1+qb_rush_share*.10,1.0,1.06); notes.append("QB rushing role separated from RB workload")\n            notes.append("carry share × YPC + drive opportunity")\n'''
if oldr not in s: raise SystemExit('rush block not found')
s=s.replace(oldr,newr,1)

oldrec='''            eff=clamp(1+adv_rec_epa*.06,.92,1.08)\n            proj=exp_targets*adv_ypt*eff*pass_match\n            notes.append("target share × YPT advanced opportunity")\n'''
newrec='''            air_eff=clamp(1+(air_share-.25)*.10,.95,1.06) if air_share>0 else 1.0\n            pressure_tax=clamp(1-sack_rate*.12,.95,1.0)\n            eff=clamp(1+adv_rec_epa*.06,.92,1.08)\n            proj=exp_targets*adv_ypt*eff*pass_match*air_eff*pressure_tax*volume_drive\n            notes.append("target share × YPT + air-yard/drive opportunity")\n'''
if oldrec not in s: raise SystemExit('receiving block not found')
s=s.replace(oldrec,newrec,1)

# TD markets get explicit scoring/red-zone opportunity context.
s=s.replace('proj=max(.02,(sf(player.get("rush_td"))+sf(player.get("rec_td")))/gp*(game.get("model_total",55)/55)*snap_adj); sd=max(.65,math.sqrt(proj))',
'proj=max(.02,(sf(player.get("rush_td"))+sf(player.get("rec_td")))/gp*(game.get("model_total",55)/55)*snap_adj*scoring_env); sd=max(.65,math.sqrt(proj))')
s=s.replace('proj=max(.02,(sf(player.get("pass_td"))+sf(player.get("rush_td"))+sf(player.get("rec_td")))/gp*(game.get("model_total",55)/55)*snap_adj); sd=max(.7,math.sqrt(proj))',
'proj=max(.02,(sf(player.get("pass_td"))+sf(player.get("rush_td"))+sf(player.get("rec_td")))/gp*(game.get("model_total",55)/55)*snap_adj*scoring_env); sd=max(.7,math.sqrt(proj))')

# Auto-weather fallback in each constructed game: manual file wins; otherwise Open-Meteo from ESPN venue city/state.
s=s.replace('''    pg["weather"]={"wind_mph":wind,"precip_prob":precip,"temp_f":temp}\n    pg["game_id"]=g.get("id"); pg["start_date"]=g.get("start_date") or g.get("startDate")\n''','''    auto_w=automatic_weather(g) if not (wind or precip or (manual_gc.get("temp_f") not in (None,""))) else {}\n    pg["weather"]={"wind_mph":sf(auto_w.get("wind_mph"),wind),"precip_prob":sf(auto_w.get("precip_prob"),precip),"temp_f":sf(auto_w.get("temp_f"),temp),"source":auto_w.get("source") or ("manual" if manual_gc else "")}\n    pg["game_id"]=g.get("id"); pg["start_date"]=g.get("start_date") or g.get("startDate")\n''',1)

# Data tab architecture message.
s=s.replace('SportsDataverse/NCAA (free stats) + Underdog live CFB player lines → matchup/game environment → player opportunity → projection → Higher/Lower probability + edge → save/grade',
'SportsDataverse/NCAA + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog live lines → CFB opportunity/hook/pressure/explosive engine → projection → Higher/Lower probability + edge → save/grade')

app.write_text(s)

rt=Path('cfb_runtime_v20.py')
r=rt.read_text()
old="""            hn=ht.get('displayName') or ht.get('shortDisplayName'); an=at.get('displayName') or at.get('shortDisplayName')\n            if not hn or not an:continue\n            out.append({'id':ev.get('id'),'week':None,'home_team':hn,'away_team':an,'home_points':_score(home),'away_points':_score(away),'start_date':ev.get('date') or comp.get('date'),'neutral_site':bool(comp.get('neutralSite')),'home_abbreviation':ht.get('abbreviation') or '','away_abbreviation':at.get('abbreviation') or '','home_espn_id':str(ht.get('id') or ''),'away_espn_id':str(at.get('id') or ''),'home_logo':_team_info(ht).get('logo'),'away_logo':_team_info(at).get('logo'),'status':((ev.get('status') or {}).get('type') or {}).get('name') or ''})\n"""
new="""            hn=ht.get('displayName') or ht.get('shortDisplayName'); an=at.get('displayName') or at.get('shortDisplayName')\n            if not hn or not an:continue\n            venue=comp.get('venue') or {}; address=venue.get('address') or {}\n            out.append({'id':ev.get('id'),'week':None,'home_team':hn,'away_team':an,'home_points':_score(home),'away_points':_score(away),'start_date':ev.get('date') or comp.get('date'),'neutral_site':bool(comp.get('neutralSite')),'home_abbreviation':ht.get('abbreviation') or '','away_abbreviation':at.get('abbreviation') or '','home_espn_id':str(ht.get('id') or ''),'away_espn_id':str(at.get('id') or ''),'home_logo':_team_info(ht).get('logo'),'away_logo':_team_info(at).get('logo'),'venue_city':address.get('city') or '','venue_state':address.get('state') or '','venue_name':venue.get('fullName') or '','status':((ev.get('status') or {}).get('type') or {}).get('name') or ''})\n"""
if old not in r: raise SystemExit('runtime venue anchor not found')
rt.write_text(r.replace(old,new,1))
print('v2.5 complete CFB opportunity patch applied')
