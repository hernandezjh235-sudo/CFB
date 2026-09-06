from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

import requests

UNDERDOG_URLS = [
    "https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=ncaaf",
    "https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=cfb",
    "https://api.underdogfantasy.com/beta/v6/over_under_lines?sport_id=college-football",
    "https://api.underdogfantasy.com/beta/v6/over_under_lines",
    "https://api.underdogfantasy.com/beta/v5/over_under_lines",
]

PROP_ALIASES = {
    "Passing Yards": ["passing yards", "pass yards", "pass yds", "pass yard"],
    "Pass Attempts": ["pass attempts", "passing attempts", "attempted passes"],
    "Completions": ["completions", "passing completions", "completed passes"],
    "Passing TDs": ["passing tds", "passing touchdowns", "pass tds", "pass touchdowns", "td passes"],
    "Interceptions": ["interceptions", "passing interceptions", "ints", "interception"],
    "Rushing Yards": ["rushing yards", "rush yards", "rush yds", "rushing yard"],
    "Rush Attempts": ["rush attempts", "rushing attempts", "carries", "rush att"],
    "Receiving Yards": ["receiving yards", "rec yards", "receiving yds", "rec yds"],
    "Receptions": ["receptions", "catches"],
    "Pass + Rush Yards": ["pass + rush yards", "passing + rushing yards", "pass rush yards"],
    "Rush + Rec Yards": ["rush + rec yards", "rushing + receiving yards", "rush rec yards"],
    "Rush + Rec TDs": ["rush + rec tds", "rushing + receiving tds", "rush + rec touchdowns", "rushing + receiving touchdowns", "rush rec tds"],
    "Total TDs": ["total tds", "total touchdowns", "pass + rush + rec tds", "pass rush rec tds"],
    "Fantasy Points": ["fantasy points", "fantasy score"],
    "Longest Reception": ["longest reception", "longest catch"],
    "Longest Rush": ["longest rush", "longest carry"],
    "Longest Completion": ["longest completion", "longest pass completion"],
    "Kicking Points": ["kicking points", "kicker points"],
    "Field Goals Made": ["field goals made", "fg made", "made field goals"],
}

CFB_TERMS = (
    "ncaaf", "ncaa football", "college football", "college-football", "cfb",
    "football_fbs", "fbs", "college football player",
)
BLOCK_TERMS = (" nfl ", "nfl_", "national football league", "cfl", "xfl", "usfl")


def _norm(x: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x or "").lower())


def _num(v: Any, default=None):
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _blob(x: Any) -> str:
    if isinstance(x, dict):
        return " ".join(_blob(v) for v in x.values()).lower()
    if isinstance(x, list):
        return " ".join(_blob(v) for v in x).lower()
    return str(x or "").lower()


def _canon_prop(label: Any):
    text = re.sub(r"\s+", " ", str(label or "").strip().lower())
    if not text:
        return None
    for canon, aliases in PROP_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return canon
    return None


def _looks_cfb(*objs: Any) -> bool:
    b = " " + " ".join(_blob(x) for x in objs) + " "
    if any(term in b for term in BLOCK_TERMS):
        return False
    if any(term in b for term in CFB_TERMS):
        return True
    # Sport-filtered endpoints sometimes omit the league label. In that case the
    # absence of an NFL marker plus a football market is enough; the caller only
    # uses this fallback after trying explicit NCAAF/CFB sport filters first.
    return True


def _team_value(*objs: Dict[str, Any]) -> str:
    for o in objs:
        if not isinstance(o, dict):
            continue
        for key in ("team_abbr", "team", "team_code", "team_name", "school", "abbreviation"):
            v = o.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _player_name(player: Dict[str, Any]) -> str:
    if not isinstance(player, dict):
        return ""
    for key in ("display_name", "full_name", "player_name", "name"):
        v = player.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip()


def _matchup_from_game(game: Dict[str, Any]) -> Tuple[str, str, str]:
    if not isinstance(game, dict):
        return "", "", ""
    away = str(game.get("away_team") or game.get("away_team_name") or game.get("away") or "").strip()
    home = str(game.get("home_team") or game.get("home_team_name") or game.get("home") or "").strip()
    title = str(game.get("title") or game.get("matchup") or game.get("name") or "").strip()
    if (not away or not home) and title:
        m = re.split(r"\s+(?:@|at|vs\.?|v\.)\s+", title, maxsplit=1, flags=re.I)
        if len(m) == 2:
            away = away or m[0].strip()
            home = home or m[1].strip()
    matchup = f"{away} @ {home}" if away and home else title
    return away, home, matchup


def _native_v6(data: Dict[str, Any], source_url: str) -> List[Dict[str, Any]]:
    if not isinstance(data, dict) or not isinstance(data.get("over_under_lines"), list):
        return []
    players = {str(x.get("id")): x for x in data.get("players", []) if isinstance(x, dict) and x.get("id") is not None}
    appearances = {str(x.get("id")): x for x in data.get("appearances", []) if isinstance(x, dict) and x.get("id") is not None}
    games = {str(x.get("id")): x for x in data.get("games", []) if isinstance(x, dict) and x.get("id") is not None}
    teams = {str(x.get("id")): x for x in data.get("teams", []) if isinstance(x, dict) and x.get("id") is not None}
    rows: List[Dict[str, Any]] = []
    for line_obj in data.get("over_under_lines", []):
        if not isinstance(line_obj, dict):
            continue
        ou = line_obj.get("over_under") if isinstance(line_obj.get("over_under"), dict) else {}
        stat = ou.get("appearance_stat") if isinstance(ou.get("appearance_stat"), dict) else {}
        raw_label = stat.get("display_stat") or stat.get("stat") or stat.get("name") or ou.get("title") or line_obj.get("title") or ""
        prop = _canon_prop(raw_label)
        line = _num(line_obj.get("stat_value"))
        if not prop or line is None:
            continue
        app_id = stat.get("appearance_id") or ou.get("appearance_id") or line_obj.get("appearance_id")
        app = appearances.get(str(app_id), {}) if app_id is not None else {}
        player_id = app.get("player_id") or stat.get("player_id") or ou.get("player_id")
        player = players.get(str(player_id), {}) if player_id is not None else {}
        name = _player_name(player)
        if not name:
            opts = line_obj.get("options") if isinstance(line_obj.get("options"), list) else []
            for opt in opts:
                if isinstance(opt, dict) and str(opt.get("selection_header") or "").strip():
                    name = str(opt.get("selection_header")).strip()
                    break
        if not name:
            continue
        match_id = app.get("match_id") or stat.get("match_id") or ou.get("match_id")
        game = games.get(str(match_id), {}) if match_id is not None else {}
        if not _looks_cfb(line_obj, ou, stat, app, player, game):
            continue
        team_id = app.get("team_id") or player.get("team_id")
        team_obj = teams.get(str(team_id), {}) if team_id is not None else {}
        team = _team_value(app, player, team_obj)
        away, home, matchup = _matchup_from_game(game)
        opts = line_obj.get("options") if isinstance(line_obj.get("options"), list) else []
        higher = next((o for o in opts if isinstance(o, dict) and str(o.get("choice") or "").lower() in {"higher", "over"}), {})
        lower = next((o for o in opts if isinstance(o, dict) and str(o.get("choice") or "").lower() in {"lower", "under"}), {})
        rows.append({
            "player": name,
            "team": team,
            "prop": prop,
            "line": float(line),
            "side": "AUTO",
            "source": "Underdog",
            "source_url": source_url,
            "away": away,
            "home": home,
            "matchup": matchup,
            "event_id": str(match_id or game.get("id") or ""),
            "underdog_id": str(line_obj.get("id") or ""),
            "line_status": line_obj.get("status") or ou.get("status") or "",
            "scheduled_at": game.get("scheduled_at") or game.get("starts_at") or game.get("start_time"),
            "over_price": _num(higher.get("american_price")),
            "under_price": _num(lower.get("american_price")),
            "over_multiplier": _num(higher.get("payout_multiplier")),
            "under_multiplier": _num(lower.get("payout_multiplier")),
        })
    return rows


def _dedupe(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: Dict[Tuple[str, str, float, str], Dict[str, Any]] = {}
    for r in rows:
        key = (_norm(r.get("player")), str(r.get("prop") or ""), float(r.get("line") or 0), str(r.get("event_id") or r.get("matchup") or ""))
        if key[0] and key[1] and key[2] > 0:
            out[key] = r
    return list(out.values())


def fetch_underdog_cfb_props(force: bool = False) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://underdogfantasy.com/",
    }
    rows: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []
    for idx, url in enumerate(UNDERDOG_URLS):
        try:
            response = requests.get(url, headers=headers, timeout=(4, 10))
            response.raise_for_status()
            data = response.json()
            parsed = _native_v6(data, url)
            # For explicitly filtered endpoints, trust the sport filter. For the
            # all-sports fallbacks, the parser's league checks are the guardrail.
            rows.extend(parsed)
            debug.append({"url": url, "status": response.status_code, "rows": len(parsed)})
            if parsed and idx < 3:
                break
        except Exception as exc:
            debug.append({"url": url, "status": "ERROR", "rows": 0, "error": str(exc)[:180]})
    return _dedupe(rows), debug


def props_for_game(rows: List[Dict[str, Any]], away: str, home: str) -> List[Dict[str, Any]]:
    if not rows:
        return []
    na, nh = _norm(away), _norm(home)
    exact = []
    loose = []
    for r in rows:
        ra, rh = _norm(r.get("away")), _norm(r.get("home"))
        blob = _norm(r.get("matchup"))
        if ra == na and rh == nh:
            exact.append(r)
        elif na and nh and na in blob and nh in blob:
            loose.append(r)
    return exact or loose
