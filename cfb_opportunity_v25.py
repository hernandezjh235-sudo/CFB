from __future__ import annotations

import math, re
from functools import lru_cache
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import requests
import free_data_v15 as base


def _norm(x):
    return re.sub(r'[^a-z0-9]', '', str(x or '').lower())


def _num(x, default=0.0):
    try:
        v=float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _pct_pair(v):
    s=str(v or '')
    m=re.search(r'(\d+)\s*[-/]\s*(\d+)',s)
    if not m:return 0.0
    a,b=float(m.group(1)),float(m.group(2)); return a/b if b else 0.0


def _clock_minutes(v):
    s=str(v or '')
    m=re.search(r'(\d+):(\d+)',s)
    if not m:return 0.0
    return float(m.group(1))+float(m.group(2))/60.0


def _team_alias_maps(ctx:Dict[str,dict]):
    by_id={}; by_norm={}
    for k,d in (ctx or {}).items():
        if not isinstance(d,dict):continue
        name=str(d.get('canonical_name') or d.get('display_name') or k)
        eid=str(d.get('espn_id') or '').replace('.0','')
        if eid:by_id[eid]=name
        for z in (k,name,d.get('abbreviation')):
            if z:by_norm[_norm(z)]=name
    return by_id,by_norm


def _ctx_team(ctx, team, by_norm):
    if not team:return None
    if team in ctx:return team
    return by_norm.get(_norm(team))


def _load(ds, year):
    try:return base._parquet(ds,int(year),ds)
    except Exception:return pd.DataFrame()


def _drive_metrics(drives, by_id):
    out={}
    if drives is None or drives.empty:return out
    d=drives.copy()
    d['team_key']=d.get('team_id',pd.Series(dtype=object)).astype(str).str.replace('.0','',regex=False).map(by_id)
    d=d[d.team_key.notna()]
    if d.empty:return out
    for team,sub in d.groupby('team_key'):
        games=max(1,sub['game_id'].astype(str).nunique()) if 'game_id' in sub else 1
        n=len(sub); plays=pd.to_numeric(sub.get('offensive_plays'),errors='coerce').fillna(pd.to_numeric(sub.get('n_plays'),errors='coerce')).fillna(0)
        yards=pd.to_numeric(sub.get('yards'),errors='coerce').fillna(0)
        score=sub.get('is_score',pd.Series(False,index=sub.index)).fillna(False).astype(bool)
        result=sub.get('result',pd.Series('',index=sub.index)).astype(str).str.upper()
        three=((plays<=3)&(~score)&result.isin(['PUNT','DOWNS'])).mean() if n else 0
        td=result.str.contains('TD|TOUCHDOWN',regex=True).mean() if n else 0
        start=pd.to_numeric(sub.get('start_yard_line'),errors='coerce').dropna()
        mins=sub.get('time_elapsed',pd.Series('',index=sub.index)).map(_clock_minutes)
        out[team]={
            'drives_pg':n/games,'plays_per_drive':float(plays.mean()),'yards_per_drive':float(yards.mean()),
            'score_drive_rate':float(score.mean()),'td_drive_rate':float(td),'three_out_rate':float(three),
            'avg_start_yard_line':float(start.mean()) if len(start) else 50.0,'drive_minutes':float(mins.mean()) if len(mins) else 0.0,
        }
    return out


def _box_metrics(box, by_norm):
    out={}
    if box is None or box.empty:return out
    for raw,sub in box.groupby('team_name'):
        team=by_norm.get(_norm(raw),str(raw)); games=max(1,sub['game_id'].astype(str).nunique()) if 'game_id' in sub else max(1,len(sub))
        rush_att=pd.to_numeric(sub.get('rushingAttempts'),errors='coerce').fillna(0)
        def pass_att(v):
            m=re.search(r'(\d+)\s*[-/]\s*(\d+)',str(v or ''))
            return float(m.group(2)) if m else 0.0
        pa=sub.get('completionAttempts',pd.Series('',index=sub.index)).map(pass_att)
        plays=rush_att+pa
        total=pd.to_numeric(sub.get('totalYards'),errors='coerce').fillna(0)
        vals={
            'plays_pg':float(plays.sum()/games),'first_downs_pg':float(pd.to_numeric(sub.get('firstDowns'),errors='coerce').fillna(0).sum()/games),
            'third_down_rate':float(sub.get('thirdDownEff',pd.Series('',index=sub.index)).map(_pct_pair).mean()),
            'turnovers_pg':float(pd.to_numeric(sub.get('turnovers'),errors='coerce').fillna(0).sum()/games),
            'possession_minutes':float(sub.get('possessionTime',pd.Series('',index=sub.index)).map(_clock_minutes).mean()),
            'yards_per_play':float(total.sum()/max(plays.sum(),1)),
            'rush_rate_box':float(rush_att.sum()/max(plays.sum(),1)), 'pass_rate_box':float(pa.sum()/max(plays.sum(),1)),
        }
        out[team]=vals
    return out


def _situational_metrics(df, by_norm):
    out={}
    if df is None or df.empty:return out
    for raw,sub in df.groupby('pos_team'):
        team=by_norm.get(_norm(raw),str(raw)); last=sub.sort_values(['season','week']).iloc[-1]
        out[team]={
            'early_down_pass_rate':_num(last.get('early_down_pass_rate')),
            'early_down_rush_rate':_num(last.get('early_down_rush_rate')),
            'red_zone_success_rate':_num(last.get('EPA_success_rate_rz')),
            'third_down_success_rate':_num(last.get('EPA_success_rate_third')),
            'passing_down_epa':_num(last.get('EPA_passing_down_per_play')),
            'early_down_epa':_num(last.get('EPA_early_down_per_play')),
        }
    return out


def _team_pass_pressure(df, by_norm):
    out={}
    if df is None or df.empty:return out
    for raw,sub in df.groupby('pos_team'):
        team=by_norm.get(_norm(raw),str(raw)); att=pd.to_numeric(sub.get('Att'),errors='coerce').fillna(0); sacks=pd.to_numeric(sub.get('Sck'),errors='coerce').fillna(0)
        adot=pd.to_numeric(sub.get('aDOT'),errors='coerce'); ypa=pd.to_numeric(sub.get('YPA'),errors='coerce')
        out[team]={
            'sack_rate_allowed':float(sacks.sum()/max(att.sum()+sacks.sum(),1)),
            'team_adot':float(adot.mean()) if adot.notna().any() else 0.0,
            'team_ypa_adv':float(ypa.mean()) if ypa.notna().any() else 0.0,
            'qb1_attempt_share':float(att.max()/max(att.sum(),1)) if len(att) else 0.0,
        }
    return out


def _player_usage(players, passing, rushing, receiving, rosters, by_norm):
    if players is None or players.empty:return players
    p=players.copy()
    for c in ['starter_current','qb_rush_share','air_yard_share','redzone_td_proxy','sack_rate','qb1_attempt_share']:
        if c not in p.columns:p[c]=0.0
    # current starter flags from the freshest game-roster observation
    starter={}
    if rosters is not None and not rosters.empty:
        namec='athlete_display_name' if 'athlete_display_name' in rosters else ('full_name' if 'full_name' in rosters else None)
        if namec:
            rr=rosters.sort_values(['season','week','game_id']) if all(c in rosters for c in ['season','week','game_id']) else rosters
            for _,r in rr.iterrows():starter[_norm(r.get(namec))]=bool(r.get('starter'))
    p['starter_current']=p['player'].astype(str).map(lambda x: starter.get(_norm(x),False))
    # team rushing totals and air-yard totals give true opportunity shares
    rush_tot={}; air_tot={}; pass_team={}
    if rushing is not None and not rushing.empty:
        rush_tot=rushing.groupby('pos_team')['Car'].sum().to_dict()
    if receiving is not None and not receiving.empty:
        air_tot=receiving.groupby('pos_team')['AirYds'].sum().to_dict()
    if passing is not None and not passing.empty:
        for _,r in passing.iterrows():pass_team[_norm(r.get('passer_player_name'))]=(_num(r.get('Sck'))/max(_num(r.get('Att'))+_num(r.get('Sck')),1), str(r.get('pos_team') or ''))
    rush_rows={}
    if rushing is not None and not rushing.empty:
        for _,r in rushing.iterrows():rush_rows[_norm(r.get('rusher_player_name'))]=r
    rec_rows={}
    if receiving is not None and not receiving.empty:
        for _,r in receiving.iterrows():rec_rows[_norm(r.get('receiver_player_name'))]=r
    for i,row in p.iterrows():
        n=_norm(row.get('player')); team=str(row.get('current_team') or row.get('team') or '')
        if n in pass_team:
            sr,raw=pass_team[n]; p.at[i,'sack_rate']=sr
        rr=rush_rows.get(n)
        if rr is not None:
            raw=str(rr.get('pos_team') or team); p.at[i,'qb_rush_share']=_num(rr.get('Car'))/max(_num(rush_tot.get(raw)),1)
        rc=rec_rows.get(n)
        if rc is not None:
            raw=str(rc.get('pos_team') or team); p.at[i,'air_yard_share']=_num(rc.get('AirYds'))/max(_num(air_tot.get(raw)),1)
        # TD opportunity proxy is deliberately independent of the live prop line.
        td=_num(row.get('rush_td'))+_num(row.get('rec_td'))
        gp=max(_num(row.get('games'),1),1); p.at[i,'redzone_td_proxy']=td/gp
    return p


def enrich_opportunity(year:int, week:int, ctx:Dict[str,dict], players:pd.DataFrame) -> Tuple[Dict[str,dict],pd.DataFrame,dict]:
    by_id,by_norm=_team_alias_maps(ctx)
    drives=_load('drives',year); box=_load('team_box',year); passing=_load('adv_passing',year); rushing=_load('adv_rushing',year); receiving=_load('adv_receiving',year); situ=_load('adv_situational',year); rosters=_load('game_rosters',year)
    layers=[_drive_metrics(drives,by_id),_box_metrics(box,by_norm),_situational_metrics(situ,by_norm),_team_pass_pressure(passing,by_norm)]
    for layer in layers:
        for team,vals in layer.items():
            key=_ctx_team(ctx,team,by_norm) or team
            ctx.setdefault(key,{}).update(vals)
    players=_player_usage(players,passing,rushing,receiving,rosters,by_norm)
    health={'drives':len(drives),'team_box':len(box),'adv_passing':len(passing),'adv_rushing':len(rushing),'adv_receiving':len(receiving),'adv_situational':len(situ),'game_rosters':len(rosters)}
    return ctx,players,health


@lru_cache(maxsize=64)
def _geocode(city:str,state:str=''):
    if not city:return None
    try:
        q=f'{city}, {state}' if state else city
        r=requests.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':q,'count':1,'language':'en','format':'json'},timeout=(4,12),headers={'User-Agent':'Mozilla/5.0'})
        r.raise_for_status(); rows=r.json().get('results') or []
        if not rows:return None
        return float(rows[0]['latitude']),float(rows[0]['longitude'])
    except Exception:return None


def automatic_weather(game:dict):
    city=str(game.get('venue_city') or ''); state=str(game.get('venue_state') or '')
    loc=_geocode(city,state)
    if not loc:return {}
    dt=str(game.get('start_date') or '')[:10]
    if not dt:return {}
    try:
        lat,lon=loc
        r=requests.get('https://api.open-meteo.com/v1/forecast',params={'latitude':lat,'longitude':lon,'hourly':'temperature_2m,precipitation_probability,wind_speed_10m','temperature_unit':'fahrenheit','wind_speed_unit':'mph','start_date':dt,'end_date':dt,'timezone':'auto'},timeout=(4,12),headers={'User-Agent':'Mozilla/5.0'})
        r.raise_for_status(); h=r.json().get('hourly') or {}; times=h.get('time') or []
        if not times:return {}
        # Without a guaranteed venue timezone kickoff conversion, use the day's median/peak conservative weather context.
        temps=[_num(x,70) for x in h.get('temperature_2m') or []]; winds=[_num(x) for x in h.get('wind_speed_10m') or []]; rain=[_num(x) for x in h.get('precipitation_probability') or []]
        return {'temp_f':float(np.median(temps)) if temps else 70.0,'wind_mph':float(np.percentile(winds,75)) if winds else 0.0,'precip_prob':float(max(rain)) if rain else 0.0,'source':'Open-Meteo auto'}
    except Exception:return {}
