from __future__ import annotations

import math
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
    prev_player_box=grab('player_box','player_box',int(year)-1)
    prev_team_box=grab('team_box','team_box',int(year)-1)
    prev_schedule=grab('schedules','cfb_schedule',int(year)-1)

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
            'player_stats':[],'advanced':[],'errors':errors,'free_health':health,
            'requested_week':int(week),'resolved_week':resolved_week,'available_weeks':available}
    print('CFB_FREE_V20','requested',week,'resolved',resolved_week,'available',available,
          'games',len(games),'players',len(players),'current_players',len(current_players),'prior_players',len(prior_players),
          'ctx',len(ctx),'markets',len(market),'health',health,'errors',errors,flush=True)
    return bundle,ctx,players,market
