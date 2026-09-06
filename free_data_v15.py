from __future__ import annotations

from functools import lru_cache
from io import BytesIO
import math, re
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import requests

RAW='https://raw.githubusercontent.com/sportsdataverse/cfbfastR-cfb-data/main/cfb'
ESPN_SCOREBOARD='https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
NCAA='https://ncaa-api.henrygd.me'


def _norm(s): return re.sub(r'[^a-z0-9]','',str(s or '').lower())
def _num(v, d=0.0):
    try:
        x=float(v); return x if math.isfinite(x) else d
    except Exception: return d

@lru_cache(maxsize=24)
def _parquet(dataset:str, year:int, stem:str='') -> pd.DataFrame:
    stem=stem or dataset
    url=f'{RAW}/{dataset}/parquet/{stem}_{year}.parquet'
    r=requests.get(url,timeout=(5,25),headers={'User-Agent':'Mozilla/5.0','Cache-Control':'no-cache'})
    r.raise_for_status()
    return pd.read_parquet(BytesIO(r.content))

def _col(df,*names):
    if df is None or df.empty: return None
    m={_norm(c):c for c in df.columns}
    for n in names:
        if _norm(n) in m:return m[_norm(n)]
    for n in names:
        nn=_norm(n)
        for k,c in m.items():
            if nn and nn in k:return c
    return None

def _series(df,*names,default=0.0):
    c=_col(df,*names)
    if not c:return pd.Series(default,index=df.index,dtype=float)
    return pd.to_numeric(df[c],errors='coerce').fillna(default)

def _text(df,*names,default=''):
    c=_col(df,*names)
    if not c:return pd.Series(default,index=df.index,dtype=str)
    return df[c].fillna(default).astype(str)

def _z(s):
    s=pd.to_numeric(s,errors='coerce'); sd=s.std(skipna=True)
    return (s-s.mean(skipna=True))/(sd if sd and sd>1e-9 else 1.0)

def _schedule_rows(df,week):
    if df is None or df.empty:return []
    wc=_col(df,'week','season_week')
    use=df.copy()
    if wc: use=use[pd.to_numeric(use[wc],errors='coerce').fillna(-1).astype(int)==int(week)]
    home=_text(use,'home_team','home_display_name','home_team_name','home_name')
    away=_text(use,'away_team','away_display_name','away_team_name','away_name')
    hp=_series(use,'home_score','home_points','home_team_score',default=np.nan)
    ap=_series(use,'away_score','away_points','away_team_score',default=np.nan)
    gid=_text(use,'id','game_id','event_id','espn_id')
    dt=_text(use,'start_date','date','start_time','game_date','start_date_time')
    neutral=_text(use,'neutral_site','neutral')
    out=[]
    for i in use.index:
        h=str(home.loc[i]).strip(); a=str(away.loc[i]).strip()
        if not h or not a or h.lower()=='nan' or a.lower()=='nan':continue
        out.append({'id':gid.loc[i],'week':int(week),'home_team':h,'away_team':a,
                    'home_points':None if pd.isna(hp.loc[i]) else float(hp.loc[i]),
                    'away_points':None if pd.isna(ap.loc[i]) else float(ap.loc[i]),
                    'start_date':dt.loc[i],'neutral_site':str(neutral.loc[i]).lower() in {'1','true','yes'}})
    return out

def _espn_schedule(year:int,week:int)->List[dict]:
    try:
        params={'dates':str(year),'seasontype':'2','week':int(week),'limit':'1000'}
        r=requests.get(ESPN_SCOREBOARD,params=params,timeout=(4,12),headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        r.raise_for_status(); j=r.json(); out=[]
        for ev in j.get('events',[]) or []:
            comp=((ev.get('competitions') or [{}])[0])
            competitors=comp.get('competitors') or []
            home=next((x for x in competitors if x.get('homeAway')=='home'),{})
            away=next((x for x in competitors if x.get('homeAway')=='away'),{})
            ht=(home.get('team') or {}).get('displayName') or (home.get('team') or {}).get('shortDisplayName')
            at=(away.get('team') or {}).get('displayName') or (away.get('team') or {}).get('shortDisplayName')
            if not ht or not at:continue
            def score(x):
                v=x.get('score')
                try:return float(v) if v not in (None,'') else None
                except:return None
            out.append({'id':ev.get('id'),'week':int(week),'home_team':ht,'away_team':at,'home_points':score(home),'away_points':score(away),
                        'start_date':ev.get('date') or comp.get('date'),'neutral_site':bool(comp.get('neutralSite'))})
        return out
    except Exception:return []

def _players(df,through_week):
    if df is None or df.empty:return pd.DataFrame()
    use=df.copy(); wc=_col(use,'week','season_week')
    if wc: use=use[pd.to_numeric(use[wc],errors='coerce').fillna(99)<=int(through_week)]
    name=_text(use,'athlete_display_name','player_name','athlete_name','player','athlete')
    team=_text(use,'team','team_display_name','team_name','school')
    game=_text(use,'game_id','id','event_id')
    tmp=pd.DataFrame({'player':name,'team':team,'game':game})
    aliases={
      'pass_yds':('passing_yards','pass_yards','pass_yds'),'pass_att':('passing_attempts','pass_attempts','pass_att'),
      'pass_comp':('passing_completions','completions','pass_completions'),'pass_td':('passing_touchdowns','passing_tds','pass_tds'),
      'pass_int':('interceptions','passing_interceptions','pass_interceptions'),'rush_yds':('rushing_yards','rush_yards','rush_yds'),
      'rush_att':('rushing_attempts','rushing_carries','carries','rush_attempts'),'rush_td':('rushing_touchdowns','rushing_tds','rush_tds'),
      'rec_yds':('receiving_yards','reception_yards','rec_yards'),'receptions':('receptions','receiving_receptions'),
      'rec_td':('receiving_touchdowns','receiving_tds','rec_tds')}
    for k,a in aliases.items():tmp[k]=_series(use,*a)
    tmp=tmp[(tmp.player.astype(str)!='')&(tmp.team.astype(str)!='')]
    if tmp.empty:return tmp
    agg={k:'sum' for k in aliases}; agg['game']='nunique'
    return tmp.groupby(['player','team'],as_index=False).agg(agg).rename(columns={'game':'games'})

def _team_context(schedule,adv,pidx,through_week):
    teams={}; s=schedule.copy() if schedule is not None else pd.DataFrame(); wc=_col(s,'week','season_week')
    if wc:s=s[pd.to_numeric(s[wc],errors='coerce').fillna(99)<=int(through_week)]
    hc=_col(s,'home_team','home_display_name'); ac=_col(s,'away_team','away_display_name'); hpc=_col(s,'home_score','home_points'); apc=_col(s,'away_score','away_points')
    rows=[]
    if hc and ac and hpc and apc:
        for _,r in s.iterrows():
            h=str(r.get(hc,'')); a=str(r.get(ac,'')); hp=_num(r.get(hpc),np.nan); ap=_num(r.get(apc),np.nan)
            if not h or not a or math.isnan(hp) or math.isnan(ap):continue
            rows += [(h,hp,ap),(a,ap,hp)]
    if rows:
        g=pd.DataFrame(rows,columns=['team','pf','pa']).groupby('team').agg(pf=('pf','mean'),pa=('pa','mean'),games=('pf','size')).reset_index(); g['margin']=g.pf-g.pa; g['power']=_z(g['margin'])
        for _,r in g.iterrows():teams[r.team]={'sp':r['margin'],'srs':r['margin'],'core':r['margin']*4,'elo':1500+r['power']*85,'talent':0,'off_rating':(r['pf']-28)/4,'def_rating':(28-r['pa'])/4,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0}
    if pidx is not None and not pidx.empty:
        tc=_col(pidx,'team','team_display_name','team_name','school'); rc=_col(pidx,'fpi','rating','power_index','powerindex'); oc=_col(pidx,'offense','offensive_efficiency'); dc=_col(pidx,'defense','defensive_efficiency')
        if tc:
            for _,r in pidx.iterrows():
                t=str(r.get(tc,'')).strip()
                if not t:continue
                d=teams.setdefault(t,{'sp':0,'srs':0,'core':0,'elo':1500,'talent':0,'off_rating':0,'def_rating':0,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0})
                if rc:d['sp']=_num(r.get(rc)); d['srs']=d['sp']; d['core']=d['sp']*4
                if oc:d['off_rating']=_num(r.get(oc))
                if dc:d['def_rating']=_num(r.get(dc))
    if adv is not None and not adv.empty:
        use=adv.copy(); wc=_col(use,'week','season_week')
        if wc:use=use[pd.to_numeric(use[wc],errors='coerce').fillna(99)<=int(through_week)]
        tc=_col(use,'team','team_display_name','team_name','school')
        if tc:
            use['_team']=use[tc].astype(str)
            aliases={'pace':('plays','offensive_plays','total_plays'),'def_passing':('def_pass_epa','defensive_passing_epa','pass_epa_allowed','opponent_pass_epa'),'def_rushing':('def_rush_epa','defensive_rushing_epa','rush_epa_allowed','opponent_rush_epa'),'def_expl':('def_explosiveness','explosiveness_allowed'),'off_expl':('off_explosiveness','explosiveness'),'havoc':('havoc','def_havoc','defensive_havoc')}
            for t,sub in use.groupby('_team'):
                d=teams.setdefault(t,{'sp':0,'srs':0,'core':0,'elo':1500,'talent':0,'off_rating':0,'def_rating':0,'pace':0,'off_expl':0,'def_expl':0,'def_passing':0,'def_rushing':0,'havoc':0})
                for key,als in aliases.items():
                    c=_col(sub,*als)
                    if c:d[key]=float(pd.to_numeric(sub[c],errors='coerce').mean())
    names=list(teams); vals=np.array([_num(teams[t].get('sp'))+.18*_num(teams[t].get('off_rating'))-.18*_num(teams[t].get('def_rating')) for t in names])
    mu=float(np.nanmean(vals)) if len(vals) else 0; sd=float(np.nanstd(vals)) if len(vals) else 1; sd=sd if sd>1e-9 else 1
    for t,v in zip(names,vals):teams[t]['power_z']=(v-mu)/sd
    for i,t in enumerate(sorted(names,key=lambda x:teams[x]['power_z'],reverse=True),1):teams[t]['model_rank']=i
    return teams

def ncaa_ap_rankings():
    try:
        r=requests.get(f'{NCAA}/rankings/football/fbs/associated-press',timeout=(3,8)); r.raise_for_status(); j=r.json(); out={}
        def walk(x):
            if isinstance(x,dict):
                team=x.get('school') or x.get('team') or x.get('name'); rank=x.get('rank') or x.get('ranking')
                if team and rank:
                    try:out[str(team)]=int(rank)
                    except:pass
                for v in x.values():walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        walk(j); return out
    except Exception:return {}

def load_free_stack(year:int,week:int):
    errors={}; health={}
    def grab(ds,stem=None):
        try:
            x=_parquet(ds,int(year),stem or ds); health[ds]=len(x); return x
        except Exception as e:errors[ds]=str(e); health[ds]=0; return pd.DataFrame()
    schedule=grab('schedules','cfb_schedule'); player_box=grab('player_box','player_box'); adv=grab('adv_team','adv_team'); pidx=grab('power_index','power_index'); betting=grab('betting','betting')
    games=_schedule_rows(schedule,week)
    if not games:
        games=_espn_schedule(year,week)
        health['espn_schedule']=len(games)
        if games:errors.pop('schedules',None)
    players=_players(player_box,week); ctx=_team_context(schedule,adv,pidx,week)
    ap=ncaa_ap_rankings()
    for t,r in ap.items():
        for key in list(ctx):
            if _norm(key)==_norm(t):ctx[key]['ap_rank']=r
    market={}
    if betting is not None and not betting.empty:
        away=_text(betting,'away_team','away_display_name'); home=_text(betting,'home_team','home_display_name'); spread=_series(betting,'spread','home_spread','spread_line',default=np.nan); total=_series(betting,'over_under','total','total_line',default=np.nan); bw=_series(betting,'week',default=week)
        for i in betting.index:
            if int(_num(bw.loc[i],week))!=int(week) or not away.loc[i] or not home.loc[i]:continue
            market[(_norm(away.loc[i]),_norm(home.loc[i]))]={'away':away.loc[i],'home':home.loc[i],'market_home_spread':None if pd.isna(spread.loc[i]) else float(spread.loc[i]),'market_total':None if pd.isna(total.loc[i]) else float(total.loc[i])}
    bundle={'games':games,'teams':[],'sp':[],'core':[],'srs':[],'elo':[],'rankings':[],'talent':[],'player_stats':[],'advanced':[],'errors':errors,'free_health':health}
    print('CFB_FREE_HEALTH',health,'games',len(games),'players',len(players),'ctx',len(ctx),'errors',errors,flush=True)
    return bundle,ctx,players,market
