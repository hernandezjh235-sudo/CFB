from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
from typing import Dict, Iterable, List, Optional

from cfb_nfl_ui_v18 import espn_team_branding

PT = ZoneInfo('America/Los_Angeles')


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
    out = []
    for g in games or []:
        dt = local_game_dt(g)
        if dt and dt.date() == target:
            out.append(g)
    return out


def filter_props_by_scope(rows: List[dict], scope: str, now=None) -> List[dict]:
    target = scope_target_date(scope, now)
    if target is None:
        return list(rows or [])
    dated, undated = [], []
    for r in rows or []:
        dt = local_prop_dt(r)
        if dt is None:
            undated.append(r)
        elif dt.date() == target:
            dated.append(r)
    # Prefer truly dated rows. If a provider omits timestamps, keep undated rows
    # rather than blanking the live board.
    return dated if dated else undated


def _brand_for(name: str, abbreviation: str = '') -> dict:
    brands = espn_team_branding() or {}
    keys = [_norm(name), _norm(abbreviation)]
    for k in keys:
        if k and k in brands:
            return dict(brands[k])
    n = _norm(name)
    if not n:
        return {}
    candidates = []
    for k, info in brands.items():
        if len(k) < 3:
            continue
        if k in n or n in k:
            score = min(len(k), len(n)) / max(len(k), len(n))
            candidates.append((score, len(k), info))
    if not candidates:
        return {}
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if candidates[0][0] < 0.45:
        return {}
    return dict(candidates[0][2])


def ensure_branding(ctx: Dict[str, dict], games: Iterable[dict] = (), players=None) -> Dict[str, dict]:
    ctx = ctx or {}

    def ensure(team: str, abbr: str = ''):
        if not team:
            return
        current = ctx.setdefault(str(team), {})
        info = _brand_for(str(team), str(abbr or ''))
        if not info:
            return
        if not current.get('logo'):
            current['logo'] = info.get('logo') or ''
        if not current.get('color'):
            current['color'] = info.get('color') or '#2f81f7'
        if not current.get('alternate_color'):
            current['alternate_color'] = info.get('alternate_color') or '#8fa4b8'
        if not current.get('abbreviation'):
            current['abbreviation'] = info.get('abbreviation') or abbr or ''
        if not current.get('espn_id'):
            current['espn_id'] = info.get('espn_id') or ''

    for g in games or []:
        ensure(g.get('away_team') or g.get('awayTeam') or g.get('away'), g.get('away_abbreviation') or g.get('awayAbbreviation') or '')
        ensure(g.get('home_team') or g.get('homeTeam') or g.get('home'), g.get('home_abbreviation') or g.get('homeAbbreviation') or '')

    try:
        if players is not None and not players.empty and 'team' in players.columns:
            for team in players['team'].dropna().astype(str).unique().tolist():
                ensure(team)
    except Exception:
        pass
    return ctx


def logo_coverage(ctx: Dict[str, dict], games: Iterable[dict]) -> dict:
    teams = []
    for g in games or []:
        teams.extend([g.get('away_team') or g.get('away'), g.get('home_team') or g.get('home')])
    teams = [str(t) for t in teams if t]
    unique = list(dict.fromkeys(teams))
    ready = 0
    missing = []
    for t in unique:
        d = ctx.get(t, {})
        if d.get('logo'):
            ready += 1
        else:
            missing.append(t)
    return {'teams': len(unique), 'logos': ready, 'missing': missing, 'coverage': (ready / len(unique) if unique else 1.0)}
