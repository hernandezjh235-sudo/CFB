from pathlib import Path

# ---- Fix Underdog stat canonicalization + expose alternate-line metadata ----
p=Path('underdog_cfb_v15.py')
s=p.read_text()
old="""def _canon(label):
    text=re.sub(r'\\s+',' ',str(label or '').strip().lower())
    for canon,als in PROP_ALIASES.items():
        if any(a in text for a in als):return canon
    return None
"""
new="""def _canon(label):
    # Exact market matching only. Specialty yes/no markets such as
    # 'Game High Pass Yards' or '1+ Pass TDs in Each Half' must NOT be fed
    # into the ordinary Passing Yards/Passing TD formulas. The old substring
    # matcher also turned Fantasy Points into Interceptions ('points' contains
    # 'ints') and combo stats into component stats.
    def norm_phrase(x):
        return re.sub(r'[^a-z0-9]+',' ',str(x or '').lower()).strip()
    nt=norm_phrase(label)
    for canon,als in PROP_ALIASES.items():
        for alias in [canon]+list(als):
            if nt==norm_phrase(alias):return canon
    return None
"""
if old not in s:
    raise SystemExit('canon block not found')
s=s.replace(old,new)
oldrow="""    return {'player':name,'team':team,'prop':prop,'line':float(line),'side':'AUTO','source':'Underdog','source_url':source_url,'away':away,'home':home,'matchup':matchup,'event_id':str(event_id or game.get('id') or ''),'underdog_id':str(line_obj.get('id') or ''),'line_status':line_obj.get('status') or '','scheduled_at':game.get('scheduled_at') or game.get('starts_at') or game.get('start_time')}
"""
newrow="""    ou=line_obj.get('over_under') if isinstance(line_obj.get('over_under'),dict) else {}
    return {'player':name,'team':team,'prop':prop,'line':float(line),'side':'AUTO','source':'Underdog','source_url':source_url,'away':away,'home':home,'matchup':matchup,'event_id':str(event_id or game.get('id') or ''),'underdog_id':str(line_obj.get('id') or ''),'line_status':line_obj.get('status') or '','scheduled_at':game.get('scheduled_at') or game.get('starts_at') or game.get('start_time'),'line_type':str(line_obj.get('line_type') or ''),'non_discounted_line':_num(line_obj.get('non_discounted_stat_value')),'has_alternates':bool(ou.get('has_alternates'))}
"""
if oldrow in s:
    s=s.replace(oldrow,newrow)
p.write_text(s)

# ---- Fix misleading Data Readiness zero table and label v2.9 ----
p=Path('app.py')
s=p.read_text()
s=s.replace('APP_VERSION = "CFB Prop Engine v2.8 — LIVE EVENT LOCK + ROLE INTEGRITY + GRADE AUDIT"','APP_VERSION = "CFB Prop Engine v2.9 — PROP PARSER CLEAN + TRUE DATA READINESS"')
s=s.replace('APP_VERSION = "CFB Prop Engine v2.6 — COACH-AWARE BLOWOUT + COMPLETE OPPORTUNITY"','APP_VERSION = "CFB Prop Engine v2.9 — PROP PARSER CLEAN + TRUE DATA READINESS"')
old="""    checks=[]
    for k in [\"games\",\"teams\",\"sp\",\"core\",\"srs\",\"elo\",\"rankings\",\"talent\",\"player_stats\",\"advanced\"]:
        v=bundle.get(k,[]); checks.append({\"Layer\":k,\"Rows\":len(v) if isinstance(v,list) else 0,\"Ready\":bool(v),\"Role\":{
            \"games\":\"schedule/results/game counts\",\"teams\":\"FBS identity/logos/colors/conference\",\"sp\":\"offense/defense/pass/rush/explosive/havoc/pace\",\"core\":\"opponent-relative team efficiency\",\"srs\":\"schedule-adjusted power\",\"elo\":\"team strength\",\"rankings\":\"AP/CFP context\",\"talent\":\"roster talent gap/blowout context\",\"player_stats\":\"QB/RB/WR season production/usage\",\"advanced\":\"advanced efficiency context\"}[k]})
    st.dataframe(pd.DataFrame(checks),width=\"stretch\",hide_index=True)
"""
new="""    checks=[]
    if str(data_mode).startswith('FREE'):
        fh=bundle.get('free_health',{}) or {}
        # Show the real no-key datasets actually feeding the model. The legacy
        # CFBD-shaped bundle intentionally keeps several placeholder lists empty,
        # which previously made healthy free data look like Rows=0.
        free_layers=[
            ('schedule/results',fh.get('schedules',len(bundle.get('games',[]))),'game schedule/results'),
            ('team context',len(ctx),'team identity + derived matchup context'),
            ('player production',len(players) if players is not None else 0,'QB/RB/WR current + prior + roster bank'),
            ('advanced passing',fh.get('adv_passing',0),'QB usage/efficiency'),
            ('advanced rushing',fh.get('adv_rushing',0),'carry share/efficiency'),
            ('advanced receiving',fh.get('adv_receiving',0),'targets/air yards/efficiency'),
            ('situational',fh.get('adv_situational',0),'down/distance/red-zone context'),
            ('team box',fh.get('team_box',0),'plays/turnovers/possession/efficiency'),
            ('game rosters',fh.get('game_rosters',0),'starter/current-game role'),
            ('current rosters',fh.get('rosters',0),'current-team identity'),
            ('power index',fh.get('power_index',0),'team strength/rating context'),
            ('betting',fh.get('betting',0),'spread + total context'),
            ('drives',fh.get('v25_drives',fh.get('drives',0)),'drive/pace/scoring opportunity'),
        ]
        for name,rows,role in free_layers:
            checks.append({'Layer':name,'Rows':int(rows or 0),'Ready':bool(rows),'Role':role})
    else:
        for k in [\"games\",\"teams\",\"sp\",\"core\",\"srs\",\"elo\",\"rankings\",\"talent\",\"player_stats\",\"advanced\"]:
            v=bundle.get(k,[]); checks.append({\"Layer\":k,\"Rows\":len(v) if isinstance(v,list) else 0,\"Ready\":bool(v),\"Role\":{
                \"games\":\"schedule/results/game counts\",\"teams\":\"FBS identity/logos/colors/conference\",\"sp\":\"offense/defense/pass/rush/explosive/havoc/pace\",\"core\":\"opponent-relative team efficiency\",\"srs\":\"schedule-adjusted power\",\"elo\":\"team strength\",\"rankings\":\"AP/CFP context\",\"talent\":\"roster talent gap/blowout context\",\"player_stats\":\"QB/RB/WR season production/usage\",\"advanced\":\"advanced efficiency context\"}[k]})
    st.dataframe(pd.DataFrame(checks),width=\"stretch\",hide_index=True)
"""
if old not in s:
    raise SystemExit('data readiness block not found')
s=s.replace(old,new)
s=s.replace('[\"player\",\"team\",\"matchup\",\"prop\",\"line\",\"line_status\",\"scheduled_at\"]','[\"player\",\"team\",\"matchup\",\"prop\",\"line\",\"line_type\",\"non_discounted_line\",\"line_status\",\"scheduled_at\"]')
p.write_text(s)
print('v2.9 parser/data-readiness fixes applied')
