from __future__ import annotations

from io import BytesIO
import math, re
from typing import Dict, Tuple
import numpy as np
import pandas as pd
import requests

RAW='https://raw.githubusercontent.com/sportsdataverse/cfbfastR-cfb-data/main/cfb'
NCAA='https://ncaa-api.henrygd.me'

def _norm(s): return re.sub(r'[^a-z0-9]','',str(s).lower())
def _num(v, d=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else d
    except Exception: return d

def _parquet(dataset, year, stem=None, timeout=45):
    stem=stem or dataset
    url=f'{RAW}/{dataset}/parquet/{stem}_{year}.parquet'
    r=requests.get(url,timeout=timeout); r.raise_for_status()
    return pd.read_parquet(BytesIO(r.content))

def _col(df,*names):
    if df is None or df.empty: return None
    m={_norm(c):c for c in df.columns}
    for n in names:
        if _norm(n) in m: return m[_norm(n)]
    for n in names:
        nn=_norm(n)
        for k,c in m.items():
            if nn and nn in k: return c
    return None

def _series(df,*names,default=0.0):
    c=_col(df,*names)
    if not c: return pd.Series(default,index=df.index,dtype=float)
    return pd.to_numeric(df[c],errors='coerce').fillna(default)

def _text(df,*names,default=''):
    c=_col(df,*names)
    if not c: return pd.Series(default,index=df.index,dtype=str)
    return df[c].fillna(default).astype(str)

def _z(s):
    s=pd.to_numeric(s,errors='coerce'); sd=s.std(skipna=True)
    return (s-s.mean(skipna=True))/(sd if sd and sd>1e-9 else 1.0)

def _schedule_rows(df, week):
    if df is None or df.empty:return []
    wc=_col(df,'week')
    if wc: df=df[pd.to_numeric(df[wc],errors='coerce').fillna(-1).astype(int)==int(week)]
    home=_text(df,'home_team','home_display_name','home_team_name')
    away=_text(df,'away_team','away_display_name','away_team_name')
    hp=_series(df,'home_score','home_points','home_team_score',default=np.nan)
    ap=_series(df,'away_score','away_points','away_team_score',default=np.nan)
    gid=_text(df,'id','game_id','event_id')
    dt=_text(df,'start_date','date','start_time','game_date')
    neutral=_text(df,'neutral_site','neutral')
    out=[]
    for i in df.index:
        if not home.loc[i] or not away.loc[i]: continue
        out.append({'id':gid.loc[i],'week':int(week),'home_team':home.loc[i],'away_team':away.loc[i],
                    'home_points':None if pd.isna(hp.loc[i]) else float(hp.loc[i]),'away_points':None if pd.isna(ap.loc[i]) else float(ap.loc[i]),
                    'start_date':dt.loc[i],'neutral_site':str(neutral.loc[i]).lower() in {'1','true','yes'}})
    return out

def _players(df, through_week):
    if df is None or df.empty:return pd.DataFrame()
    wc=_col(df,'week')
    if wc: df=df[pd.to_numeric(df[wc],errors='coerce').fillna(99)<=int(through_week)]
    name=_text(df,'athlete_display_name','player_name','athlete_name','player')
    team=_text(df,'team','team_display_name','team_name')
    game=_text(df,'game_id','id','event_id')
    tmp=pd.DataFrame({'player':name,'team':team,'game':game})
    aliases={
      'pass_yds':('passing_yards','pass_yards'),'pass_att':('passing_attempts','pass_attempts'),'pass_comp':('passing_completions','completions'),
      'pass_td':('passing_touchdowns','passing_tds','pass_tds'),'pass_int':('interceptions','passing_interceptions'),
      'rush_yds':('rushing_yards','rush_yards'),'rush_att':('rushing_attempts','rushing_carries','carries'),'rush_td':('rushing_touchdowns','rushing_tds'),
      'rec_yds':('receiving_yards','reception_yards'),'receptions':('receptions','receiving_receptions'),'rec_td':('receiving_touchdowns','receiving_tds')}
    for k,a in aliases.items(): tmp[k]=_series(df,*a)
    tmp=tmp[(tmp.player!='')&(tmp.team!='')]
    agg={k:'sum' for k in aliases}; agg['game']='nunique'
    out=tmp.groupby(['player','team'],as_index=False).agg(agg).rename(columns={'game':'games'})
    return out

def _team_context(schedule, adv, pidx, through_week):
    teams={}
    # Start from schedule results: scoring margin, points for/against, recent strength.
    wc=_col(schedule,'week') if schedule is not None else None
    s=schedule.copy() if schedule is not None else pd.DataFrame()
    if wc: s=s[pd.to_numeric(s[wc],errors='coerce').fillna(99)<=int(through_week)]
    hc=_col(s,'home_team','home_display_name'); ac=_col(s,'away_team','away_display_name')
    hpc=_col(s,'home_score','home_points'); apc=_col(s,'away_score','away_points')
    rows=[]
    if hc and ac and hpc and apc:
        for _,r in s.iterrows():
            h=str(r.get(hc,'')); a=str(r.get(ac,'')); hp=_num(r.get(hpc),np.nan); ap=_num(r.get(apc),np.nan)
            if not h or not a or math.isnan(hp) or math.isnan(ap): continue
            rows += [(h,hp,ap),(a,ap,hp)]
    if rows:
        g=pd.DataFrame(rows,columns=['team','pf','pa']).groupby('team').agg(pf=('pf','mean'),pa=('pa','mean'),games=('pf','size')).reset_index()
        g['margin']=g.pf-g.pa; g['power']=_z(g['margin'])
        for _,r in g.iterrows():
            teams[r.team]={'sp':r['margin'],'srs':r['margin'],'core':r['margin']*4,'elo':1500+r['power']*85,'talent':0,
                           'off_rating':(r['pf']-28)/4,'def_rating':(28-r['pa'])/4,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0}
    # Enrich with ESPN FPI/power index when present.
    if pidx is not None and not pidx.empty:
        tc=_col(pidx,'team','team_display_name','team_name'); rc=_col(pidx,'fpi','rating','power_index','powerindex')
        oc=_col(pidx,'offense','offensive_efficiency'); dc=_col(pidx,'defense','defensive_efficiency')
        if tc:
            for _,r in pidx.iterrows():
                t=str(r.get(tc,''));
                if not t: continue
                d=teams.setdefault(t,{'sp':0,'srs':0,'core':0,'elo':1500,'talent':0,'off_rating':0,'def_rating':0,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0})
                if rc: d['sp']=_num(r.get(rc)); d['srs']=d['sp']; d['core']=d['sp']*4
                if oc: d['off_rating']=_num(r.get(oc))
                if dc: d['def_rating']=_num(r.get(dc))
    # Advanced team game logs: derive pass/rush matchup, explosiveness, havoc/pace using flexible column matching.
    if adv is not None and not adv.empty:
        wc=_col(adv,'week')
        if wc: adv=adv[pd.to_numeric(adv[wc],errors='coerce').fillna(99)<=int(through_week)]
        tc=_col(adv,'team','team_display_name','team_name')
        if tc:
            adv=adv.copy(); adv['_team']=adv[tc].astype(str)
            feature_alias={
              'pace':('plays','offensive_plays','total_plays'),'def_passing':('def_pass_epa','defensive_passing_epa','pass_epa_allowed','opponent_pass_epa'),
              'def_rushing':('def_rush_epa','defensive_rushing_epa','rush_epa_allowed','opponent_rush_epa'),'def_expl':('def_explosiveness','explosiveness_allowed'),
              'off_expl':('off_explosiveness','explosiveness'),'havoc':('havoc','def_havoc','defensive_havoc')}
            grp=adv.groupby('_team')
            for t,sub in grp:
                d=teams.setdefault(t,{'sp':0,'srs':0,'core':0,'elo':1500,'talent':0,'off_rating':0,'def_rating':0,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0})
                for key,als in feature_alias.items():
                    c=_col(sub,*als)
                    if c: d[key]=float(pd.to_numeric(sub[c],errors='coerce').mean())
    # Rank from composite power. Higher offense/margin, lower defensive EPA allowed.
    names=list(teams)
    vals=np.array([_num(teams[t].get('sp'))+0.18*_num(teams[t].get('off_rating'))-0.18*_num(teams[t].get('def_rating')) for t in names])
    mu=float(np.nanmean(vals)) if len(vals) else 0; sd=float(np.nanstd(vals)) if len(vals) else 1; sd=sd if sd>1e-9 else 1
    for t,v in zip(names,vals): teams[t]['power_z']=(v-mu)/sd
    for i,t in enumerate(sorted(names,key=lambda x:teams[x]['power_z'],reverse=True),1): teams[t]['model_rank']=i
    return teams

def ncaa_ap_rankings():
    try:
        r=requests.get(f'{NCAA}/rankings/football/fbs/associated-press',timeout=12); r.raise_for_status(); j=r.json()
        rows=j.get('data') or j.get('rankings') or j.get('content') or []
        out={}
        def walk(x):
            if isinstance(x,dict):
                team=x.get('school') or x.get('team') or x.get('name'); rank=x.get('rank') or x.get('ranking')
                if team and rank:
                    try: out[str(team)]=int(rank)
                    except: pass
                for v in x.values(): walk(v)
            elif isinstance(x,list):
                for v in x: walk(v)
        walk(rows); return out
    except Exception: return {}

def load_free_stack(year:int, week:int):
    errors={}; health={}
    def grab(ds,stem=None):
        try:
            x=_parquet(ds,year,stem); health[ds]=len(x); return x
        except Exception as e:
            errors[ds]=str(e); health[ds]=0; return pd.DataFrame()
    schedule=grab('schedules','cfb_schedule')
    player_box=grab('player_box','player_box')
    adv=grab('adv_team','adv_team')
    pidx=grab('power_index','power_index')
    betting=grab('betting','betting')
    games=_schedule_rows(schedule,week)
    players=_players(player_box,week)
    ctx=_team_context(schedule,adv,pidx,week)
    ap=ncaa_ap_rankings()
    for t,r in ap.items():
        for key in list(ctx):
            if _norm(key)==_norm(t): ctx[key]['ap_rank']=r
    # Free game-line layer from SportsDataverse betting dataset where available.
    market={}
    if betting is not None and not betting.empty:
        away=_text(betting,'away_team','away_display_name'); home=_text(betting,'home_team','home_display_name')
        spread=_series(betting,'spread','home_spread','spread_line',default=np.nan); total=_series(betting,'over_under','total','total_line',default=np.nan)
        bw=_series(betting,'week',default=week)
        for i in betting.index:
            if int(_num(bw.loc[i],week))!=int(week): continue
            if not away.loc[i] or not home.loc[i]: continue
            market[(_norm(away.loc[i]),_norm(home.loc[i]))]={'away':away.loc[i],'home':home.loc[i],
                'market_home_spread':None if pd.isna(spread.loc[i]) else float(spread.loc[i]),
                'market_total':None if pd.isna(total.loc[i]) else float(total.loc[i])}
    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],'player_stats':[],'advanced':[],'errors':errors,'free_health':health}
    return bundle,ctx,players,market
