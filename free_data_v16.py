from __future__ import annotations

import math
from io import BytesIO
import requests
import numpy as np
import pandas as pd
import free_data_v15 as base

_norm=base._norm
_num=base._num


def _team_baselines(df:pd.DataFrame, max_week:int|None=None):
    out={}
    if df is None or df.empty:return out
    use=df.copy(); wc=base._col(use,'week','season_week')
    if wc and max_week is not None:
        use=use[pd.to_numeric(use[wc],errors='coerce').fillna(99)<=int(max_week)]
    tc=base._col(use,'team','team_display_name','team_name','school')
    if not tc:return out
    gc=base._col(use,'game_id','id','event_id')
    aliases={
        'team_pass_yds_pg':('passing_yards','pass_yards','pass_yds'),
        'team_pass_att_pg':('passing_attempts','pass_attempts','pass_att'),
        'team_pass_comp_pg':('passing_completions','completions','pass_completions'),
        'team_pass_td_pg':('passing_touchdowns','passing_tds','pass_tds'),
        'team_rush_yds_pg':('rushing_yards','rush_yards','rush_yds'),
        'team_rush_att_pg':('rushing_attempts','rushing_carries','carries','rush_attempts'),
        'team_rush_td_pg':('rushing_touchdowns','rushing_tds','rush_tds'),
    }
    cols={k:base._col(use,*als) for k,als in aliases.items()}
    for team,sub in use.groupby(tc):
        d={}
        for k,c in cols.items():
            if c:
                s=pd.to_numeric(sub[c],errors='coerce')
                # team_box is game-level; mean is the correct per-game baseline.
                if s.notna().any():d[k]=float(s.mean())
        d['team_box_games']=int(sub[gc].astype(str).nunique()) if gc else int(len(sub))
        out[str(team)]=d
    return out


def _advanced_player_features(passing,rushing,receiving,max_week):
    rows={}
    def add(name,team,vals):
        if not name:return
        k=_norm(name); d=rows.setdefault(k,{'player_key':k,'adv_team':str(team or '')})
        for key,val in vals.items():
            try:
                f=float(val)
                if np.isfinite(f): d[key]=d.get(key,0.0)+f
            except Exception: pass
    def week_filter(df):
        if df is None or df.empty:return df
        wc=base._col(df,'week','season_week')
        if wc:return df[pd.to_numeric(df[wc],errors='coerce').fillna(99)<=int(max_week)].copy()
        return df.copy()
    p=week_filter(passing)
    if p is not None and not p.empty:
        nc=base._col(p,'passer_player_name'); tc=base._col(p,'pos_team'); gc=base._col(p,'game_id')
        for _,r in p.iterrows():
            add(r.get(nc),r.get(tc),{'adv_pass_att':r.get('Att',0),'adv_pass_comp':r.get('Comp',0),'adv_pass_yds':r.get('Yds',0),'adv_pass_epa_total':r.get('EPA',0),'adv_pass_sr_num':float(r.get('SR',0))*float(r.get('Att',0) or 0),'adv_cpoe_num':float(r.get('CPOE',0))*float(r.get('Att',0) or 0),'adv_airyds':r.get('AirYds',0)})
    ru=week_filter(rushing)
    if ru is not None and not ru.empty:
        nc=base._col(ru,'rusher_player_name'); tc=base._col(ru,'pos_team');
        team_car=ru.groupby(tc)['Car'].sum().to_dict() if tc and 'Car' in ru.columns else {}
        for _,r in ru.iterrows():
            team=str(r.get(tc) or ''); car=float(r.get('Car',0) or 0); den=float(team_car.get(team,0) or 0)
            add(r.get(nc),team,{'adv_rush_car':car,'adv_rush_yds':r.get('Yds',0),'adv_rush_epa_total':r.get('EPA',0),'adv_rush_sr_num':float(r.get('SR',0))*car,'adv_carry_share_num':(car/den if den>0 else 0)})
    rec=week_filter(receiving)
    if rec is not None and not rec.empty:
        nc=base._col(rec,'receiver_player_name'); tc=base._col(rec,'pos_team');
        team_tar=rec.groupby(tc)['Tar'].sum().to_dict() if tc and 'Tar' in rec.columns else {}
        for _,r in rec.iterrows():
            team=str(r.get(tc) or ''); tar=float(r.get('Tar',0) or 0); den=float(team_tar.get(team,0) or 0)
            add(r.get(nc),team,{'adv_targets':tar,'adv_rec':r.get('Rec',0),'adv_rec_yds':r.get('Yds',0),'adv_rec_epa_total':r.get('EPA',0),'adv_rec_sr_num':float(r.get('SR',0))*tar,'adv_target_share_num':(tar/den if den>0 else 0),'adv_rec_airyds':r.get('AirYds',0)})
    out=[]
    for d in rows.values():
        pa=d.get('adv_pass_att',0); rc=d.get('adv_rush_car',0); tg=d.get('adv_targets',0)
        if pa>0:
            d['adv_ypa']=d.get('adv_pass_yds',0)/pa; d['adv_pass_epa']=d.get('adv_pass_epa_total',0)/pa; d['adv_pass_sr']=d.get('adv_pass_sr_num',0)/pa; d['adv_cpoe']=d.get('adv_cpoe_num',0)/pa; d['adv_adot']=d.get('adv_airyds',0)/pa
        if rc>0:
            d['adv_ypc']=d.get('adv_rush_yds',0)/rc; d['adv_rush_epa']=d.get('adv_rush_epa_total',0)/rc; d['adv_rush_sr']=d.get('adv_rush_sr_num',0)/rc
        if tg>0:
            d['adv_catch_rate']=d.get('adv_rec',0)/tg; d['adv_ypt']=d.get('adv_rec_yds',0)/tg; d['adv_rec_epa']=d.get('adv_rec_epa_total',0)/tg; d['adv_rec_sr']=d.get('adv_rec_sr_num',0)/tg; d['adv_rec_adot']=d.get('adv_rec_airyds',0)/tg
        # carry/target share sums are per game-like aggregate proxies; bound later in model.
        d['adv_carry_share']=d.get('adv_carry_share_num',0)
        d['adv_target_share']=d.get('adv_target_share_num',0)
        out.append(d)
    return pd.DataFrame(out)


def _merge_player_banks(current:pd.DataFrame, previous:pd.DataFrame)->pd.DataFrame:
    cur=current.copy() if current is not None else pd.DataFrame()
    prev=previous.copy() if previous is not None else pd.DataFrame()
    if not cur.empty:cur['sample_source']='current'
    if prev.empty:return cur
    prev['sample_source']='prior'
    if cur.empty:return prev
    existing=set(cur['player'].astype(str).map(_norm)) if 'player' in cur.columns else set()
    prev=prev[~prev['player'].astype(str).map(_norm).isin(existing)]
    return pd.concat([cur,prev],ignore_index=True,sort=False)


def load_free_stack(year:int, week:int):
    errors={}; health={}
    def grab(ds,stem=None,grab_year=None):
        yy=int(year if grab_year is None else grab_year)
        key=ds if yy==int(year) else f'{ds}_{yy}'
        try:
            x=base._parquet(ds,yy,stem or ds); health[key]=len(x); return x
        except Exception as e:
            errors[key]=str(e); health[key]=0; return pd.DataFrame()

    schedule=grab('schedules','cfb_schedule')
    player_box=grab('player_box','player_box')
    adv=grab('adv_team','adv_team')
    pidx=grab('power_index','power_index')
    betting=grab('betting','betting')
    team_box=grab('team_box','team_box')
    game_rosters=grab('game_rosters','game_rosters')
    adv_passing=grab('adv_passing','adv_passing')
    adv_rushing=grab('adv_rushing','adv_rushing')
    adv_receiving=grab('adv_receiving','adv_receiving')
    adv_situational=grab('adv_situational','adv_situational')
    prev_player_box=grab('player_box','player_box',int(year)-1)
    prev_team_box=grab('team_box','team_box',int(year)-1)
    prev_schedule=grab('schedules','cfb_schedule',int(year)-1)
    try:
        roster_url=f'https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_cfb_rosters/cfb_rosters_{int(year)}.parquet'
        rr=requests.get(roster_url,timeout=(5,30),headers={'User-Agent':'Mozilla/5.0'})
        rr.raise_for_status(); roster=pd.read_parquet(BytesIO(rr.content)); health['rosters']=len(roster)
    except Exception as e:
        roster=pd.DataFrame(); health['rosters']=0; errors['rosters']=str(e)

    resolved_week=int(week)
    wc=base._col(schedule,'week','season_week') if schedule is not None else None
    available=[]
    if wc and not schedule.empty:
        available=sorted(pd.to_numeric(schedule[wc],errors='coerce').dropna().astype(int).unique().tolist())
        if available and resolved_week not in available:
            resolved_week=max(available)

    games=base._schedule_rows(schedule,resolved_week)
    if not games:
        games=base._espn_schedule(year,resolved_week)
        health['espn_schedule']=len(games)

    if games and schedule is not None and not schedule.empty:
        gidc=base._col(schedule,'game_id','id','event_id','espn_id')
        hac=base._col(schedule,'home_abbreviation','home_abbr','home_team_abbreviation')
        aac=base._col(schedule,'away_abbreviation','away_abbr','away_team_abbreviation')
        heid=base._col(schedule,'home_team_id','home_id','home_espn_id')
        aeid=base._col(schedule,'away_team_id','away_id','away_espn_id')
        if gidc:
            lookup={str(r.get(gidc)):r for _,r in schedule.iterrows()}
            for g in games:
                rr=lookup.get(str(g.get('id')))
                if rr is not None:
                    g['home_abbreviation']=str(rr.get(hac) or '') if hac else ''
                    g['away_abbreviation']=str(rr.get(aac) or '') if aac else ''
                    g['home_espn_id']=str(rr.get(heid) or '') if heid else ''
                    g['away_espn_id']=str(rr.get(aeid) or '') if aeid else ''
                    if g['home_espn_id']:g['home_logo']=f"https://a.espncdn.com/i/teamlogos/ncaa/500/{g['home_espn_id']}.png"
                    if g['away_espn_id']:g['away_logo']=f"https://a.espncdn.com/i/teamlogos/ncaa/500/{g['away_espn_id']}.png"

    current_players=base._players(player_box,resolved_week)
    prior_players=base._players(prev_player_box,99)
    players=_merge_player_banks(current_players,prior_players)
    adv_players=_advanced_player_features(adv_passing,adv_rushing,adv_receiving,resolved_week)
    if players is not None and not players.empty:
        players['player_key']=players['player'].astype(str).map(_norm)
        if adv_players is not None and not adv_players.empty:
            players=players.merge(adv_players,on='player_key',how='left')
        players.drop(columns=['player_key'],inplace=True,errors='ignore')
    ctx=base._team_context(schedule,adv,pidx,resolved_week)

    # Build NFL-style canonical team aliases from current + prior schedules. The
    # previous season is useful before the next-day schedule file catches up, and
    # gives stable ESPN IDs for logos without any paid API.
    alias_schedules=[x for x in [schedule,prev_schedule] if x is not None and not x.empty]
    for sched in alias_schedules:
        hname=base._col(sched,'home_team','home_display_name','home_team_name','home_name')
        aname=base._col(sched,'away_team','away_display_name','away_team_name','away_name')
        habbr=base._col(sched,'home_abbreviation','home_abbr','home_team_abbreviation')
        aabbr=base._col(sched,'away_abbreviation','away_abbr','away_team_abbreviation')
        hid=base._col(sched,'home_team_id','home_id','home_espn_id')
        aid=base._col(sched,'away_team_id','away_id','away_espn_id')
        for _,rr in sched.iterrows():
            for nc,ac,ic in [(hname,habbr,hid),(aname,aabbr,aid)]:
                name=str(rr.get(nc) or '').strip() if nc else ''
                abbr=str(rr.get(ac) or '').strip() if ac else ''
                eid=str(rr.get(ic) or '').strip() if ic else ''
                if not name:continue
                d=ctx.setdefault(name,{'sp':0,'srs':0,'core':0,'elo':1500,'talent':0,'off_rating':0,'def_rating':0,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0})
                d['canonical_name']=name
                if abbr:d['abbreviation']=abbr
                if eid and eid.lower()!='nan':
                    d['espn_id']=eid
                    d['logo']=d.get('logo') or f'https://a.espncdn.com/i/teamlogos/ncaa/500/{eid}.png'
                if abbr:
                    alias=dict(d);alias['canonical_name']=name;ctx[abbr]=alias

    # Player-box team fields can be ESPN numeric IDs. Convert them to the same
    # canonical school names used by the game/context layer so logos, opponents,
    # and matchup metrics resolve correctly in the player board.
    if players is not None and not players.empty and 'team' in players.columns:
        id_to_name={}
        for key,d in list(ctx.items()):
            if not isinstance(d,dict):continue
            eid=str(d.get('espn_id') or '').strip()
            cname=str(d.get('canonical_name') or key or '').strip()
            if eid and eid.lower()!='nan' and cname:
                id_to_name[eid]=cname
        def _canon_player_team(v):
            raw=str(v or '').strip()
            if raw in id_to_name:return id_to_name[raw]
            d=ctx.get(raw,{}) or {}
            return str(d.get('canonical_name') or raw)
        players['team']=players['team'].map(_canon_player_team)

    # Current-season roster is the source of truth for TODAY'S school. Prior-season
    # box stats remain useful production evidence, but transfers inherit the new team's
    # logo, opponent matchup and opportunity baseline.
    roster_map={}
    roster_rows=[]
    if game_rosters is not None and not game_rosters.empty:
        gnc=base._col(game_rosters,'athlete_display_name','full_name','player_name')
        gtc=base._col(game_rosters,'team_display_name','team_short_display_name','team_location')
        gac=base._col(game_rosters,'active','is_active'); gdc=base._col(game_rosters,'did_not_play')
        if gnc and gtc:
            for _,row in game_rosters.iterrows():
                name=str(row.get(gnc) or '').strip(); team=str(row.get(gtc) or '').strip()
                if not name or not team:continue
                if gac and str(row.get(gac)).lower() in {'false','0'}:continue
                roster_map[_norm(name)]=team
                roster_rows.append((name,team))
    if roster is not None and not roster.empty:
        nc=base._col(roster,'athlete_display_name','player_name','athlete_name','player','athlete_full_name','full_name')
        tc=base._col(roster,'team_display_name','team_short_display_name','team_location','school','team')
        if nc and tc:
            for _,row in roster.iterrows():
                name=str(row.get(nc) or '').strip(); team=str(row.get(tc) or '').strip()
                if not name or not team or name.lower()=='nan' or team.lower()=='nan':continue
                if team.replace('.0','').isdigit():
                    d=next((v for v in ctx.values() if isinstance(v,dict) and str(v.get('espn_id') or '') in {team,team.replace('.0','')}),{})
                    team=str(d.get('canonical_name') or d.get('display_name') or team)
                roster_map[_norm(name)]=team
                roster_rows.append((name,team))
    if players is None or players.empty:
        players=pd.DataFrame(columns=['player','team','current_team','games','pass_yds','pass_att','pass_comp','pass_td','pass_int','rush_yds','rush_att','rush_td','rec_yds','receptions','rec_td','sample_source'])
    if 'current_team' not in players.columns: players['current_team']=''
    players['current_team']=players['player'].astype(str).map(lambda x: roster_map.get(_norm(x),'') if _norm(x) in roster_map else '')
    existing=set(players['player'].astype(str).map(_norm))
    add=[]
    for name,team in roster_rows:
        if _norm(name) in existing:continue
        add.append({'player':name,'team':team,'current_team':team,'games':0,'pass_yds':0.0,'pass_att':0.0,'pass_comp':0.0,'pass_td':0.0,'pass_int':0.0,'rush_yds':0.0,'rush_att':0.0,'rush_td':0.0,'rec_yds':0.0,'receptions':0.0,'rec_td':0.0,'sample_source':'roster'})
    if add: players=pd.concat([players,pd.DataFrame(add)],ignore_index=True,sort=False)

    cur_team=_team_baselines(team_box,resolved_week)
    prev_team=_team_baselines(prev_team_box,None)
    all_teams=set(ctx)|set(cur_team)|set(prev_team)
    for team in all_teams:
        d=ctx.setdefault(team,{'sp':0,'srs':0,'core':0,'elo':1500,'talent':0,'off_rating':0,'def_rating':0,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0})
        cur=cur_team.get(team,{})
        prev=prev_team.get(team,{})
        # Current-season game data wins; prior season fills opening-week holes.
        src=cur if cur.get('team_box_games',0)>0 else prev
        for k,v in src.items():d[k]=v
        d['team_baseline_source']='current' if src is cur and src else ('prior' if src else 'none')

    ap=base.ncaa_ap_rankings()
    for t,r in ap.items():
        for key in list(ctx):
            if base._norm(key)==base._norm(t):ctx[key]['ap_rank']=r

    market={}
    if betting is not None and not betting.empty:
        away=base._text(betting,'away_team','away_display_name')
        home=base._text(betting,'home_team','home_display_name')
        spread=base._series(betting,'spread','home_spread','spread_line',default=np.nan)
        total=base._series(betting,'over_under','total','total_line',default=np.nan)
        bw=base._series(betting,'week',default=resolved_week)
        for i in betting.index:
            if int(base._num(bw.loc[i],resolved_week))!=int(resolved_week):continue
            if not away.loc[i] or not home.loc[i]:continue
            market[(base._norm(away.loc[i]),base._norm(home.loc[i]))]={
                'away':away.loc[i],'home':home.loc[i],
                'market_home_spread':None if pd.isna(spread.loc[i]) else float(spread.loc[i]),
                'market_total':None if pd.isna(total.loc[i]) else float(total.loc[i])}

    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],
            'player_stats':[],'advanced':[],
            'advanced_player_health':{'passing':len(adv_passing),'rushing':len(adv_rushing),'receiving':len(adv_receiving),'situational':len(adv_situational)},
            'current_roster_count':len(roster_map),'errors':errors,'free_health':health,
            'requested_week':int(week),'resolved_week':resolved_week,'available_weeks':available}
    print('CFB_FREE_V20','requested',week,'resolved',resolved_week,'available',available,
          'games',len(games),'players',len(players),'current_players',len(current_players),'prior_players',len(prior_players),
          'ctx',len(ctx),'markets',len(market),'health',health,'errors',errors,flush=True)
    return bundle,ctx,players,market
