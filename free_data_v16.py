from __future__ import annotations

import math
import numpy as np
import pandas as pd
import free_data_v15 as base

# Re-export helpers used elsewhere if needed.
_norm=base._norm
_num=base._num


def _clean_id(v):
    if v is None:return ''
    try:
        if pd.isna(v):return ''
    except Exception:pass
    s=str(v).strip()
    if s.endswith('.0') and s[:-2].isdigit():s=s[:-2]
    return s


def load_free_stack(year:int, week:int):
    errors={}; health={}
    def grab(ds,stem=None):
        try:
            x=base._parquet(ds,int(year),stem or ds); health[ds]=len(x); return x
        except Exception as e:
            errors[ds]=str(e); health[ds]=0; return pd.DataFrame()

    schedule=grab('schedules','cfb_schedule')
    player_box=grab('player_box','player_box')
    adv=grab('adv_team','adv_team')
    pidx=grab('power_index','power_index')
    betting=grab('betting','betting')

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

    # Add stable team metadata from the SportsDataverse schedule itself. cfbfastR
    # carries ESPN team IDs on modern schedules; those IDs can be used directly
    # with ESPN's public CDN even if a separate teams endpoint changes shape.
    if games and schedule is not None and not schedule.empty:
        gidc=base._col(schedule,'game_id','id','event_id','espn_id')
        hac=base._col(schedule,'home_abbreviation','home_abbr','home_team_abbreviation')
        aac=base._col(schedule,'away_abbreviation','away_abbr','away_team_abbreviation')
        hic=base._col(schedule,'home_id','home_team_id','home_espn_id','home_team_espn_id')
        aic=base._col(schedule,'away_id','away_team_id','away_espn_id','away_team_espn_id')
        hlc=base._col(schedule,'home_logo','home_team_logo','home_logo_url')
        alc=base._col(schedule,'away_logo','away_team_logo','away_logo_url')
        if gidc:
            lookup={str(r.get(gidc)):r for _,r in schedule.iterrows()}
            for g in games:
                rr=lookup.get(str(g.get('id')))
                if rr is not None:
                    g['home_abbreviation']=str(rr.get(hac) or '') if hac else ''
                    g['away_abbreviation']=str(rr.get(aac) or '') if aac else ''
                    g['home_team_id']=_clean_id(rr.get(hic)) if hic else ''
                    g['away_team_id']=_clean_id(rr.get(aic)) if aic else ''
                    g['home_logo']=str(rr.get(hlc) or '') if hlc else ''
                    g['away_logo']=str(rr.get(alc) or '') if alc else ''
                    if not g['home_logo'] and g['home_team_id']:
                        g['home_logo']=f"https://a.espncdn.com/i/teamlogos/ncaa/500/{g['home_team_id']}.png"
                    if not g['away_logo'] and g['away_team_id']:
                        g['away_logo']=f"https://a.espncdn.com/i/teamlogos/ncaa/500/{g['away_team_id']}.png"

    players=base._players(player_box,resolved_week)
    ctx=base._team_context(schedule,adv,pidx,resolved_week)
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
    print('CFB_FREE_V16','requested',week,'resolved',resolved_week,'available',available,
          'games',len(games),'players',len(players),'ctx',len(ctx),'markets',len(market),'health',health,'errors',errors,flush=True)
    return bundle,ctx,players,market
