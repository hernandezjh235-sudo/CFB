from pathlib import Path

p=Path('free_data_v16.py'); s=p.read_text()
# Load the free current-season advanced player and game-roster tables.
needle="""    team_box=grab('team_box','team_box')\n    prev_player_box=grab('player_box','player_box',int(year)-1)\n"""
insert="""    team_box=grab('team_box','team_box')\n    game_rosters=grab('game_rosters','game_rosters')\n    adv_passing=grab('adv_passing','adv_passing')\n    adv_rushing=grab('adv_rushing','adv_rushing')\n    adv_receiving=grab('adv_receiving','adv_receiving')\n    adv_situational=grab('adv_situational','adv_situational')\n    prev_player_box=grab('player_box','player_box',int(year)-1)\n"""
if needle not in s: raise SystemExit('v24 free source marker missing')
s=s.replace(needle,insert,1)

# Helpers to aggregate current opportunity shares/efficiency by player.
marker='''\ndef _merge_player_banks(current:pd.DataFrame, previous:pd.DataFrame)->pd.DataFrame:\n'''
if 'def _advanced_player_features(' not in s:
    fn='''\ndef _advanced_player_features(passing,rushing,receiving,max_week):\n    rows={}\n    def add(name,team,vals):\n        if not name:return\n        k=_norm(name); d=rows.setdefault(k,{'player_key':k,'adv_team':str(team or '')})\n        for key,val in vals.items():\n            try:\n                f=float(val)\n                if np.isfinite(f): d[key]=d.get(key,0.0)+f\n            except Exception: pass\n    def week_filter(df):\n        if df is None or df.empty:return df\n        wc=base._col(df,'week','season_week')\n        if wc:return df[pd.to_numeric(df[wc],errors='coerce').fillna(99)<=int(max_week)].copy()\n        return df.copy()\n    p=week_filter(passing)\n    if p is not None and not p.empty:\n        nc=base._col(p,'passer_player_name'); tc=base._col(p,'pos_team'); gc=base._col(p,'game_id')\n        for _,r in p.iterrows():\n            add(r.get(nc),r.get(tc),{'adv_pass_att':r.get('Att',0),'adv_pass_comp':r.get('Comp',0),'adv_pass_yds':r.get('Yds',0),'adv_pass_epa_total':r.get('EPA',0),'adv_pass_sr_num':float(r.get('SR',0))*float(r.get('Att',0) or 0),'adv_cpoe_num':float(r.get('CPOE',0))*float(r.get('Att',0) or 0),'adv_airyds':r.get('AirYds',0)})\n    ru=week_filter(rushing)\n    if ru is not None and not ru.empty:\n        nc=base._col(ru,'rusher_player_name'); tc=base._col(ru,'pos_team');\n        team_car=ru.groupby(tc)['Car'].sum().to_dict() if tc and 'Car' in ru.columns else {}\n        for _,r in ru.iterrows():\n            team=str(r.get(tc) or ''); car=float(r.get('Car',0) or 0); den=float(team_car.get(team,0) or 0)\n            add(r.get(nc),team,{'adv_rush_car':car,'adv_rush_yds':r.get('Yds',0),'adv_rush_epa_total':r.get('EPA',0),'adv_rush_sr_num':float(r.get('SR',0))*car,'adv_carry_share_num':(car/den if den>0 else 0)})\n    rec=week_filter(receiving)\n    if rec is not None and not rec.empty:\n        nc=base._col(rec,'receiver_player_name'); tc=base._col(rec,'pos_team');\n        team_tar=rec.groupby(tc)['Tar'].sum().to_dict() if tc and 'Tar' in rec.columns else {}\n        for _,r in rec.iterrows():\n            team=str(r.get(tc) or ''); tar=float(r.get('Tar',0) or 0); den=float(team_tar.get(team,0) or 0)\n            add(r.get(nc),team,{'adv_targets':tar,'adv_rec':r.get('Rec',0),'adv_rec_yds':r.get('Yds',0),'adv_rec_epa_total':r.get('EPA',0),'adv_rec_sr_num':float(r.get('SR',0))*tar,'adv_target_share_num':(tar/den if den>0 else 0),'adv_rec_airyds':r.get('AirYds',0)})\n    out=[]\n    for d in rows.values():\n        pa=d.get('adv_pass_att',0); rc=d.get('adv_rush_car',0); tg=d.get('adv_targets',0)\n        if pa>0:\n            d['adv_ypa']=d.get('adv_pass_yds',0)/pa; d['adv_pass_epa']=d.get('adv_pass_epa_total',0)/pa; d['adv_pass_sr']=d.get('adv_pass_sr_num',0)/pa; d['adv_cpoe']=d.get('adv_cpoe_num',0)/pa; d['adv_adot']=d.get('adv_airyds',0)/pa\n        if rc>0:\n            d['adv_ypc']=d.get('adv_rush_yds',0)/rc; d['adv_rush_epa']=d.get('adv_rush_epa_total',0)/rc; d['adv_rush_sr']=d.get('adv_rush_sr_num',0)/rc\n        if tg>0:\n            d['adv_catch_rate']=d.get('adv_rec',0)/tg; d['adv_ypt']=d.get('adv_rec_yds',0)/tg; d['adv_rec_epa']=d.get('adv_rec_epa_total',0)/tg; d['adv_rec_sr']=d.get('adv_rec_sr_num',0)/tg; d['adv_rec_adot']=d.get('adv_rec_airyds',0)/tg\n        # carry/target share sums are per game-like aggregate proxies; bound later in model.\n        d['adv_carry_share']=d.get('adv_carry_share_num',0)\n        d['adv_target_share']=d.get('adv_target_share_num',0)\n        out.append(d)\n    return pd.DataFrame(out)\n\n'''
    s=s.replace(marker,fn+marker,1)

# Merge advanced features after current+prior player bank is created.
needle="""    players=_merge_player_banks(current_players,prior_players)\n    ctx=base._team_context(schedule,adv,pidx,resolved_week)\n"""
insert="""    players=_merge_player_banks(current_players,prior_players)\n    adv_players=_advanced_player_features(adv_passing,adv_rushing,adv_receiving,resolved_week)\n    if players is not None and not players.empty:\n        players['player_key']=players['player'].astype(str).map(_norm)\n        if adv_players is not None and not adv_players.empty:\n            players=players.merge(adv_players,on='player_key',how='left')\n        players.drop(columns=['player_key'],inplace=True,errors='ignore')\n    ctx=base._team_context(schedule,adv,pidx,resolved_week)\n"""
if needle not in s: raise SystemExit('v24 advanced player merge marker missing')
s=s.replace(needle,insert,1)

# Augment roster-map from game_rosters, which is available even when a season roster release lags.
needle="""    roster_map={}\n    roster_rows=[]\n    if roster is not None and not roster.empty:\n"""
insert="""    roster_map={}\n    roster_rows=[]\n    if game_rosters is not None and not game_rosters.empty:\n        gnc=base._col(game_rosters,'athlete_display_name','full_name','player_name')\n        gtc=base._col(game_rosters,'team_display_name','team_short_display_name','team_location')\n        gac=base._col(game_rosters,'active','is_active'); gdc=base._col(game_rosters,'did_not_play')\n        if gnc and gtc:\n            for _,row in game_rosters.iterrows():\n                name=str(row.get(gnc) or '').strip(); team=str(row.get(gtc) or '').strip()\n                if not name or not team:continue\n                if gac and str(row.get(gac)).lower() in {'false','0'}:continue\n                roster_map[_norm(name)]=team\n                roster_rows.append((name,team))\n    if roster is not None and not roster.empty:\n"""
if needle not in s: raise SystemExit('v24 game roster marker missing')
s=s.replace(needle,insert,1)

# Surface all verified free layers in Data Health.
needle="""    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],\n            'player_stats':[],'advanced':[],'errors':errors,'free_health':health,\n"""
insert="""    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],\n            'player_stats':[],'advanced':[],\n            'advanced_player_health':{'passing':len(adv_passing),'rushing':len(adv_rushing),'receiving':len(adv_receiving),'situational':len(adv_situational)},\n            'current_roster_count':len(roster_map),'errors':errors,'free_health':health,\n"""
if needle not in s: raise SystemExit('v24 bundle marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)

# ---- runtime: current roster identity must beat historical school identity ----
p=Path('cfb_runtime_v20.py'); s=p.read_text()
needle="""    player=player or {}; raw=str(row.get('team') or ''); pr=str(player.get('team') or '')\n    away=str(game.get('away') or game.get('away_team') or ''); home=str(game.get('home') or game.get('home_team') or '')\n"""
insert="""    player=player or {}; raw=str(row.get('team') or ''); pr=str(player.get('team') or ''); current=str(player.get('current_team') or '')\n    away=str(game.get('away') or game.get('away_team') or ''); home=str(game.get('home') or game.get('home_team') or '')\n"""
if needle not in s: raise SystemExit('v24 runtime player marker missing')
s=s.replace(needle,insert,1)
needle="""    n=_norm(raw)\n    if n and n==_norm(aa):return away\n"""
insert="""    cn=_norm(current)\n    for full,abbr in ((away,aa),(home,ha)):\n        fn=_norm(full); an=_norm(abbr)\n        if cn and (cn==fn or cn==an or (len(cn)>=4 and (cn in fn or fn in cn))):return full\n    n=_norm(raw)\n    if n and n==_norm(aa):return away\n"""
if needle not in s: raise SystemExit('v24 runtime current team marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)

# ---- app: causal player opportunity formulas using current advanced shares ----
p=Path('app.py'); s=p.read_text()
s=s.replace('CFB Prop Engine v2.3 — NFL-STYLE FINAL + CURRENT ROSTER OPPORTUNITY','CFB Prop Engine v2.4 — NFL-STYLE COMPLETE OPPORTUNITY + ADVANCED DATA')
# Add advanced fields after the simple per-game stats are calculated.
needle="""    pass_td=sf(player.get(\"pass_td\"))/gp; ints=sf(player.get(\"pass_int\"))/gp\n    sample_source=str(player.get(\"sample_source\") or \"current\").lower()\n"""
insert="""    pass_td=sf(player.get(\"pass_td\"))/gp; ints=sf(player.get(\"pass_int\"))/gp\n    adv_att=sf(player.get('adv_pass_att')); adv_ypa=sf(player.get('adv_ypa')); adv_cpoe=sf(player.get('adv_cpoe')); adv_pass_epa=sf(player.get('adv_pass_epa'))\n    adv_car=sf(player.get('adv_rush_car')); adv_ypc=sf(player.get('adv_ypc')); adv_rush_epa=sf(player.get('adv_rush_epa')); carry_share=clamp(sf(player.get('adv_carry_share')),0,.92)\n    adv_tar=sf(player.get('adv_targets')); adv_catch=sf(player.get('adv_catch_rate')); adv_ypt=sf(player.get('adv_ypt')); adv_rec_epa=sf(player.get('adv_rec_epa')); target_share=clamp(sf(player.get('adv_target_share')),0,.58)\n    sample_source=str(player.get(\"sample_source\") or \"current\").lower()\n"""
if needle not in s: raise SystemExit('v24 app adv field marker missing')
s=s.replace(needle,insert,1)

# Replace core market blocks with opportunity-first blends when verified current advanced usage exists.
old='''    if market_label=="Passing Yards":\n        base=pass_y; proj=base*pass_script*pace_adj*snap_adj*pass_match; sd=max(34,0.18*proj)\n'''
new='''    if market_label=="Passing Yards":\n        if adv_att>0 and adv_ypa>0 and team_att>0:\n            qb_share=clamp(adv_att/max(team_att,1),.55,1.05)\n            exp_att=team_att*qb_share*pass_script*pace_adj*snap_adj\n            team_ypa=team_pass/max(team_att,1) if team_att>0 else 7.0\n            ypa=.58*adv_ypa+.42*team_ypa\n            eff=clamp(1+adv_cpoe*.20+adv_pass_epa*.07,.92,1.09)\n            proj=exp_att*ypa*eff*pass_match\n            notes.append("attempt share × YPA advanced opportunity")\n        else:\n            base=pass_y; proj=base*pass_script*pace_adj*snap_adj*pass_match\n        sd=max(34,0.20*proj)\n'''
if old not in s: raise SystemExit('v24 passing marker missing')
s=s.replace(old,new,1)
old='''    elif market_label=="Rushing Yards":\n        proj=rush_y*rush_script*pace_adj*snap_adj*rush_match; sd=max(18,.32*proj)\n'''
new='''    elif market_label=="Rushing Yards":\n        team_rush_att=sf(team_ctx.get('team_rush_att_pg'))\n        if carry_share>0 and adv_ypc>0 and team_rush_att>0:\n            exp_car=team_rush_att*carry_share*rush_script*pace_adj*snap_adj\n            eff=clamp(1+adv_rush_epa*.08,.92,1.08)\n            proj=exp_car*adv_ypc*eff*rush_match\n            notes.append("carry share × YPC advanced opportunity")\n        else: proj=rush_y*rush_script*pace_adj*snap_adj*rush_match\n        sd=max(18,.34*proj)\n'''
if old not in s: raise SystemExit('v24 rushing marker missing')
s=s.replace(old,new,1)
old='''    elif market_label=="Receiving Yards":\n        # Receiver opportunity follows team pass volume/game script; yds/reception carries explosive matchup.\n        proj=rec_y*pass_script*pace_adj*snap_adj*pass_match; sd=max(16,.34*proj)\n'''
new='''    elif market_label=="Receiving Yards":\n        if target_share>0 and adv_ypt>0 and team_att>0:\n            exp_targets=team_att*target_share*pass_script*pace_adj*snap_adj\n            eff=clamp(1+adv_rec_epa*.06,.92,1.08)\n            proj=exp_targets*adv_ypt*eff*pass_match\n            notes.append("target share × YPT advanced opportunity")\n        else: proj=rec_y*pass_script*pace_adj*snap_adj*pass_match\n        sd=max(16,.36*proj)\n'''
if old not in s: raise SystemExit('v24 receiving marker missing')
s=s.replace(old,new,1)
old='''    elif market_label=="Receptions":\n        proj=recs*pass_script*pace_adj*snap_adj*clamp(.98+.02*pass_match,.90,1.08); sd=max(1.3,.31*proj)\n'''
new='''    elif market_label=="Receptions":\n        if target_share>0 and adv_catch>0 and team_att>0:\n            exp_targets=team_att*target_share*pass_script*pace_adj*snap_adj\n            proj=exp_targets*clamp(adv_catch,.35,.88)*clamp(.98+.02*pass_match,.90,1.08)\n            notes.append("target share × catch rate advanced opportunity")\n        else: proj=recs*pass_script*pace_adj*snap_adj*clamp(.98+.02*pass_match,.90,1.08)\n        sd=max(1.3,.33*proj)\n'''
if old not in s: raise SystemExit('v24 receptions marker missing')
s=s.replace(old,new,1)

# Reliability: current roster + advanced opportunity can upgrade confidence, transfers stay capped.
needle="""            src=str(pr.get(\"sample_source\") or \"fallback\").lower(); gp=sf(pr.get(\"games\"),0)\n            if src==\"current\": pcap=.72 if gp<=1 else (.80 if gp<=3 else .88)\n            elif src==\"prior\": pcap=.76 if gp>=8 else .70\n            else: pcap=.66\n            p=min(max(p,1-pcap),pcap)\n"""
insert="""            src=str(pr.get(\"sample_source\") or \"fallback\").lower(); gp=sf(pr.get(\"games\"),0)\n            roster_confirmed=bool(pr.get('current_team')) or src=='current'\n            transferred=bool(pr.get('current_team') and pr.get('team') and norm_name(pr.get('current_team'))!=norm_name(pr.get('team')))\n            has_adv=any(sf(pr.get(k))>0 for k in ['adv_pass_att','adv_rush_car','adv_targets'])\n            if src==\"current\": pcap=.74 if gp<=1 else (.82 if gp<=3 else .88)\n            elif src==\"prior\": pcap=.72 if roster_confirmed else .64\n            elif src==\"roster\": pcap=.62\n            else: pcap=.62\n            if has_adv and roster_confirmed: pcap=min(.84,pcap+.03)\n            if transferred: pcap=min(pcap,.68)\n            if not roster_confirmed: pcap=min(pcap,.64)\n            p=min(max(p,1-pcap),pcap)\n"""
if needle not in s: raise SystemExit('v24 reliability marker missing')
s=s.replace(needle,insert,1)

# Add source notes/status gating for unresolved roster-only players.
needle="""            status=\"PLAYABLE\" if p>=.60 and proj>0 else \"LEAN\" if p>=.56 and proj>0 else \"TRACK\"\n            q={**r,\"_game\":row_game,\"team\":team,\"opp\":opp,\"side\":side,\"projection\":proj,\"sd\":sd,\"probability\":p,\"edge\":edge,\"status\":status,\"notes\":\" · \".join(notes)}\n"""
insert="""            status=\"PLAYABLE\" if p>=.60 and proj>0 else \"LEAN\" if p>=.56 and proj>0 else \"TRACK\"\n            if src in {'roster','fallback'} and not has_adv: status='TRACK'\n            if transferred: notes.append('transfer/current-role uncertainty')\n            if roster_confirmed: notes.append('current roster confirmed')\n            if has_adv: notes.append('2026 advanced usage available')\n            q={**r,\"_game\":row_game,\"team\":team,\"opp\":opp,\"side\":side,\"projection\":proj,\"sd\":sd,\"probability\":p,\"edge\":edge,\"status\":status,\"notes\":\" · \".join(dict.fromkeys(notes))}\n"""
if needle not in s: raise SystemExit('v24 status marker missing')
s=s.replace(needle,insert,1)
p.write_text(s)
print('v2.4 advanced opportunity patch applied')
