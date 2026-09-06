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
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def local_now():
    return datetime.now(PT)


def local_game_dt(game: dict):
    dt = _parse_dt(game.get('start_date') or game.get('startDate') or game.get('scheduled_at'))
    return dt.astimezone(PT) if dt else None


def local_prop_dt(row: dict):
    dt = _parse_dt(row.get('scheduled_at') or row.get('start_date') or row.get('startDate'))
    return dt.astimezone(PT) if dt else None


def annotate_games(games: List[dict]) -> List[dict]:
    out = []
    for g in games or []:
        q = dict(g)
        dt = local_game_dt(q)
        if dt:
            q['local_date'] = dt.date().isoformat()
            q['local_start_label'] = dt.strftime('%a %b %-d · %-I:%M %p PT')
            tags = list(q.get('tags') or [])
            if q['local_start_label'] not in tags:
                tags.insert(0, q['local_start_label'])
            q['tags'] = tags
        out.append(q)
    return out


def scope_target_date(scope: str, now=None):
    now = now or local_now()
    if scope == 'Tomorrow':
        return now.date() + timedelta(days=1)
    if scope == 'Today':
        return now.date()
    return None


def filter_games_by_scope(games: List[dict], scope: str, now=None) -> List[dict]:
    target = scope_target_date(scope, now)
    if target is None:
        return list(games or [])
    return [g for g in (games or []) if local_game_dt(g) and local_game_dt(g).date() == target]


def filter_props_by_scope(rows: List[dict], scope: str, now=None) -> List[dict]:
    now = now or local_now()
    target = scope_target_date(scope, now)
    if target is None:
        return list(rows or [])
    dated=[]; undated=[]; future=[]
    for r in rows or []:
        dt=local_prop_dt(r)
        if dt is None:
            undated.append(r); continue
        if dt.date()==target: dated.append(r)
        if dt.date()>=now.date(): future.append(dt.date())
    if dated:return dated
    if future:
        nxt=min(future)
        return [r for r in (rows or []) if local_prop_dt(r) and local_prop_dt(r).date()==nxt]
    return undated


def prop_rows_date_label(rows: List[dict]) -> str:
    dates=sorted({local_prop_dt(r).date() for r in (rows or []) if local_prop_dt(r)})
    if not dates:return ''
    if len(dates)==1:return dates[0].strftime('%A, %B %-d')
    return f"{dates[0].strftime('%b %-d')}–{dates[-1].strftime('%b %-d')}"


def _hex(c, default='#2f81f7'):
    c=str(c or '').strip().lstrip('#')
    return f'#{c}' if len(c) in (3,6) else default


def _team_info(team:dict)->dict:
    if not isinstance(team,dict):return {}
    logo=str(team.get('logo') or '')
    if not logo:
        for z in team.get('logos') or []:
            if isinstance(z,dict) and z.get('href'):
                logo=str(z['href']);break
    espn_id=str(team.get('id') or '')
    if not logo and espn_id:logo=f'https://a.espncdn.com/i/teamlogos/ncaa/500/{espn_id}.png'
    return {'logo':logo,'color':_hex(team.get('color')),'alternate_color':_hex(team.get('alternateColor'),'#8fa4b8'),'abbreviation':str(team.get('abbreviation') or ''),'espn_id':espn_id,'display_name':str(team.get('displayName') or team.get('shortDisplayName') or '')}


def _score(x):
    try:
        v=x.get('score');return float(v) if v not in (None,'') else None
    except Exception:return None


@lru_cache(maxsize=24)
def espn_games_for_date(date_key:str)->List[dict]:
    out=[]
    try:
        r=requests.get(ESPN_SCOREBOARD,params={'dates':date_key,'limit':1000},timeout=(4,15),headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        r.raise_for_status();data=r.json()
        for ev in data.get('events') or []:
            comp=((ev.get('competitions') or [{}])[0])
            competitors=comp.get('competitors') or []
            home=next((x for x in competitors if x.get('homeAway')=='home'),{})
            away=next((x for x in competitors if x.get('homeAway')=='away'),{})
            ht=home.get('team') or {}; at=away.get('team') or {}
            hn=ht.get('displayName') or ht.get('shortDisplayName'); an=at.get('displayName') or at.get('shortDisplayName')
            if not hn or not an:continue
            out.append({'id':ev.get('id'),'week':None,'home_team':hn,'away_team':an,'home_points':_score(home),'away_points':_score(away),'start_date':ev.get('date') or comp.get('date'),'neutral_site':bool(comp.get('neutralSite')),'home_abbreviation':ht.get('abbreviation') or '','away_abbreviation':at.get('abbreviation') or '','home_espn_id':str(ht.get('id') or ''),'away_espn_id':str(at.get('id') or ''),'home_logo':_team_info(ht).get('logo'),'away_logo':_team_info(at).get('logo'),'status':((ev.get('status') or {}).get('type') or {}).get('name') or ''})
    except Exception:
        return []
    return out


def day_games(scope:str, week_games:List[dict], now=None)->List[dict]:
    """NFL-style day resolver: exact calendar date first, then ESPN date scoreboard.
    This prevents a stale provider week label from hiding tomorrow's games."""
    now=now or local_now(); target=scope_target_date(scope,now)
    if target is None:return list(week_games or [])
    local=filter_games_by_scope(week_games,scope,now)
    # Always query the exact target date and merge, because free season files can lag a day.
    espn=espn_games_for_date(target.strftime('%Y%m%d'))
    if not espn:return local
    merged={}
    for g in list(local)+list(espn):
        key=(_norm(g.get('away_team') or g.get('away')),_norm(g.get('home_team') or g.get('home')))
        if not all(key):continue
        old=merged.get(key,{})
        q=dict(old);q.update({k:v for k,v in g.items() if v not in (None,'')})
        merged[key]=q
    return list(merged.values())


def _branding_from_games(games:Iterable[dict])->Dict[str,dict]:
    out={}
    for g in games or []:
        for side in ('away','home'):
            name=g.get(f'{side}_team') or g.get(side)
            abbr=g.get(f'{side}_abbreviation') or ''
            eid=str(g.get(f'{side}_espn_id') or '')
            logo=g.get(f'{side}_logo') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{eid}.png' if eid else '')
            info={'logo':logo,'color':'#2f81f7','alternate_color':'#8fa4b8','abbreviation':abbr,'espn_id':eid,'display_name':name or ''}
            for k in (_norm(name),_norm(abbr)):
                if k:out[k]=info
    return out


def ensure_branding(ctx:Dict[str,dict],games:Iterable[dict]=(),players=None,props:Iterable[dict]=())->Dict[str,dict]:
    ctx=ctx or {}; games=list(games or [])
    brands=_branding_from_games(games)
    # supplement with exact date scoreboard branding for each represented date
    for g in games:
        dt=local_game_dt(g)
        if dt:
            for eg in espn_games_for_date(dt.strftime('%Y%m%d')):
                brands.update(_branding_from_games([eg]))
    def ensure(team:str,abbr:str=''):
        if not team:return
        info=brands.get(_norm(team)) or brands.get(_norm(abbr)) or {}
        current=ctx.setdefault(str(team),{})
        if info:
            if not current.get('logo'):current['logo']=info.get('logo') or ''
            if not current.get('color'):current['color']=info.get('color') or '#2f81f7'
            current.setdefault('alternate_color',info.get('alternate_color') or '#8fa4b8')
            current.setdefault('abbreviation',info.get('abbreviation') or abbr or '')
            current.setdefault('espn_id',info.get('espn_id') or '')
        # Alias abbreviations to the full team's metrics/branding, not a blank shell.
        alias=str(abbr or current.get('abbreviation') or '')
        if alias:
            merged=dict(current)
            ctx[alias]=merged
    for g in games:
        ensure(g.get('away_team') or g.get('away'),g.get('away_abbreviation') or '')
        ensure(g.get('home_team') or g.get('home'),g.get('home_abbreviation') or '')
    try:
        if players is not None and not players.empty and 'team' in players.columns:
            for team in players['team'].dropna().astype(str).unique().tolist():ensure(team)
    except Exception:pass
    for r in props or []:
        tm=str(r.get('team') or '')
        if tm:ensure(tm,tm)
    return ctx


def canonical_prop_team(row:dict,game:dict,player:dict=None)->str:
    """Resolve book abbreviations (MISS/WIS/WSU/etc.) to the full school used by the model."""
    player=player or {}; raw=str(row.get('team') or ''); pr=str(player.get('team') or '')
    away=str(game.get('away') or game.get('away_team') or ''); home=str(game.get('home') or game.get('home_team') or '')
    aa=str(game.get('away_abbreviation') or ''); ha=str(game.get('home_abbreviation') or '')
    n=_norm(raw)
    if n and n==_norm(aa):return away
    if n and n==_norm(ha):return home
    for full in (away,home):
        fn=_norm(full)
        if n and (n==fn or n in fn or fn in n):return full
    pn=_norm(pr)
    for full in (away,home):
        if pn and pn==_norm(full):return full
    return raw or pr


def logo_coverage(ctx:Dict[str,dict],games:Iterable[dict])->dict:
    teams=[]
    for g in games or []:teams.extend([g.get('away_team') or g.get('away'),g.get('home_team') or g.get('home')])
    unique=list(dict.fromkeys(str(t) for t in teams if t));missing=[t for t in unique if not (ctx.get(t,{}) or {}).get('logo')];ready=len(unique)-len(missing)
    return {'teams':len(unique),'logos':ready,'missing':missing,'coverage':ready/len(unique) if unique else 1.0}
