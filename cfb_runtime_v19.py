from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from functools import lru_cache
import re
from typing import Dict, Iterable, List

import requests

PT = ZoneInfo('America/Los_Angeles')
ESPN_SCOREBOARD = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'


def _norm(x):
    return re.sub(r'[^a-z0-9]', '', str(x or '').lower())


def _parse_dt(value):
    if not value:return None
    s=str(value).strip()
    if not s:return None
    try:
        if s.endswith('Z'):s=s[:-1]+'+00:00'
        dt=datetime.fromisoformat(s)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:return None


def local_now():return datetime.now(PT)

def local_game_dt(game:dict):
    dt=_parse_dt(game.get('start_date') or game.get('startDate') or game.get('scheduled_at'))
    return dt.astimezone(PT) if dt else None

def local_prop_dt(row:dict):
    dt=_parse_dt(row.get('scheduled_at') or row.get('start_date') or row.get('startDate'))
    return dt.astimezone(PT) if dt else None


def annotate_games(games:List[dict])->List[dict]:
    out=[]
    for g in games or []:
        q=dict(g);dt=local_game_dt(q)
        if dt:
            q['local_date']=dt.date().isoformat();q['local_start_label']=dt.strftime('%a %b %-d · %-I:%M %p PT')
            tags=list(q.get('tags') or [])
            if q['local_start_label'] not in tags:tags.insert(0,q['local_start_label'])
            q['tags']=tags
        out.append(q)
    return out


def scope_target_date(scope:str,now=None):
    now=now or local_now()
    if scope=='Tomorrow':return now.date()+timedelta(days=1)
    if scope=='Today':return now.date()
    return None

def filter_games_by_scope(games:List[dict],scope:str,now=None)->List[dict]:
    target=scope_target_date(scope,now)
    if target is None:return list(games or [])
    return [g for g in (games or []) if local_game_dt(g) and local_game_dt(g).date()==target]

def filter_props_by_scope(rows:List[dict],scope:str,now=None)->List[dict]:
    now=now or local_now();target=scope_target_date(scope,now)
    if target is None:return list(rows or [])
    dated=[];undated=[];future=[]
    for r in rows or []:
        dt=local_prop_dt(r)
        if dt is None:undated.append(r);continue
        if dt.date()==target:dated.append(r)
        if dt.date()>=now.date():future.append(dt.date())
    if dated:return dated
    if future:
        nxt=min(future)
        return [r for r in (rows or []) if local_prop_dt(r) and local_prop_dt(r).date()==nxt]
    return undated

def prop_rows_date_label(rows:List[dict])->str:
    dates=sorted({local_prop_dt(r).date() for r in (rows or []) if local_prop_dt(r)})
    if not dates:return ''
    if len(dates)==1:return dates[0].strftime('%A, %B %-d')
    return f"{dates[0].strftime('%b %-d')}–{dates[-1].strftime('%b %-d')}"


def _hex(c,default='#2f81f7'):
    c=str(c or '').strip().lstrip('#')
    return f'#{c}' if len(c) in (3,6) else default

def _cdn_logo(espn_id):
    s=str(espn_id or '').strip()
    return f'https://a.espncdn.com/i/teamlogos/ncaa/500/{s}.png' if s and s.lower()!='nan' else ''

def _team_info(team:dict)->dict:
    if not isinstance(team,dict):return {}
    logo=str(team.get('logo') or '')
    if not logo:
        for z in team.get('logos') or []:
            if isinstance(z,dict) and z.get('href'):logo=str(z['href']);break
    eid=str(team.get('id') or '')
    if not logo:logo=_cdn_logo(eid)
    return {'logo':logo,'color':_hex(team.get('color')),'alternate_color':_hex(team.get('alternateColor'),'#8fa4b8'),'abbreviation':str(team.get('abbreviation') or ''),'espn_id':eid}


@lru_cache(maxsize=16)
def _scoreboard_branding_for_date(date_key:str)->Dict[str,dict]:
    out={}
    try:
        r=requests.get(ESPN_SCOREBOARD,params={'dates':date_key,'limit':1000},timeout=(4,15),headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        r.raise_for_status();data=r.json()
        for ev in data.get('events') or []:
            for comp in ev.get('competitions') or []:
                for competitor in comp.get('competitors') or []:
                    team=competitor.get('team') or {};info=_team_info(team)
                    for n in {team.get('displayName'),team.get('shortDisplayName'),team.get('location'),team.get('name'),team.get('abbreviation')}:
                        if n:out[_norm(n)]=info
    except Exception:return {}
    return out

def scoreboard_branding(games:Iterable[dict])->Dict[str,dict]:
    dates=set()
    for g in games or []:
        dt=local_game_dt(g)
        if dt:dates.update({dt.date()-timedelta(days=1),dt.date(),dt.date()+timedelta(days=1)})
    out={}
    for d in sorted(dates):out.update(_scoreboard_branding_for_date(d.strftime('%Y%m%d')))
    return out

def _best_brand(brands:Dict[str,dict],name:str,abbreviation:str='')->dict:
    for k in (_norm(name),_norm(abbreviation)):
        if k and k in brands:return dict(brands[k])
    n=_norm(name);hits=[]
    if not n:return {}
    for k,info in brands.items():
        if len(k)>=3 and (k in n or n in k):hits.append((min(len(k),len(n))/max(len(k),len(n)),len(k),info))
    if not hits:return {}
    hits.sort(key=lambda x:(x[0],x[1]),reverse=True)
    return dict(hits[0][2]) if hits[0][0]>=.42 else {}


def ensure_branding(ctx:Dict[str,dict],games:Iterable[dict]=(),players=None)->Dict[str,dict]:
    ctx=ctx or {};games=list(games or []);brands=scoreboard_branding(games)
    def apply(team,abbr='',logo='',eid=''):
        if not team:return
        d=ctx.setdefault(str(team),{})
        direct_logo=str(logo or '').strip() or _cdn_logo(eid)
        info=_best_brand(brands,str(team),str(abbr or ''))
        if not d.get('logo'):d['logo']=direct_logo or info.get('logo','')
        if not d.get('color'):d['color']=info.get('color','#2f81f7')
        if not d.get('alternate_color'):d['alternate_color']=info.get('alternate_color','#8fa4b8')
        if not d.get('abbreviation'):d['abbreviation']=str(abbr or info.get('abbreviation') or '')
        if not d.get('espn_id'):d['espn_id']=str(eid or info.get('espn_id') or '')
    for g in games:
        apply(g.get('away_team') or g.get('awayTeam') or g.get('away'),g.get('away_abbreviation') or g.get('awayAbbreviation') or '',g.get('away_logo') or '',g.get('away_team_id') or g.get('away_id') or '')
        apply(g.get('home_team') or g.get('homeTeam') or g.get('home'),g.get('home_abbreviation') or g.get('homeAbbreviation') or '',g.get('home_logo') or '',g.get('home_team_id') or g.get('home_id') or '')
    try:
        if players is not None and not players.empty and 'team' in players.columns:
            for team in players['team'].dropna().astype(str).unique().tolist():apply(team)
    except Exception:pass
    return ctx


def logo_coverage(ctx:Dict[str,dict],games:Iterable[dict])->dict:
    teams=[]
    for g in games or []:teams.extend([g.get('away_team') or g.get('away'),g.get('home_team') or g.get('home')])
    unique=list(dict.fromkeys(str(t) for t in teams if t));missing=[t for t in unique if not (ctx.get(t,{}) or {}).get('logo')];ready=len(unique)-len(missing)
    return {'teams':len(unique),'logos':ready,'missing':missing,'coverage':ready/len(unique) if unique else 1.0}
