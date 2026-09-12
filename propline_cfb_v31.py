from __future__ import annotations

import math, os, re, time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

BASE_URL = "https://api.prop-line.com/v1"

# PropLine's documented NFL/NCAAF market keys. Keep this map explicit so specialty
# markets cannot be misclassified as standard player props.
MARKET_TO_LABEL = {
    "player_pass_yds": "Passing Yards",
    "player_pass_tds": "Passing TDs",
    "player_pass_interceptions": "Interceptions",
    "player_pass_completions": "Completions",
    "player_pass_attempts": "Pass Attempts",
    "player_rush_yds": "Rushing Yards",
    "player_rush_attempts": "Rush Attempts",
    "player_reception_yds": "Receiving Yards",
    "player_receptions": "Receptions",
    "player_pass_rush_yds": "Pass + Rush Yards",
    "player_rush_reception_yds": "Rush + Rec Yards",
    "player_anytime_td": "Rush + Rec TDs",
    "player_kicking_points": "Kicking Points",
}
LABEL_TO_MARKET = {v: k for k, v in MARKET_TO_LABEL.items()}
STANDARD_MARKETS = list(MARKET_TO_LABEL)

_CACHE: Dict[str, Tuple[float, Any, Dict[str, str]]] = {}


def _norm(x: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x or "").lower())


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _request(path: str, api_key: str, params: Optional[dict] = None, ttl: int = 300) -> Tuple[Any, Dict[str, str]]:
    if not api_key:
        return None, {}
    key = path + "|" + repr(sorted((params or {}).items()))
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < ttl:
        return cached[1], cached[2]
    r = requests.get(
        BASE_URL + path,
        params=params or {},
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "CFB-Prop-Engine/3.1"},
        timeout=(5, 25),
    )
    r.raise_for_status()
    data = r.json()
    quota = {k: r.headers.get(k, "") for k in ["X-Daily-Limit", "X-Daily-Used", "X-Daily-Remaining", "X-Daily-Reset"]}
    _CACHE[key] = (now, data, quota)
    return data, quota


def discover_cfb_sport(api_key: str) -> str:
    # Official PropLine NCAAF sport key. Do not make /sports a prerequisite.
    # Their documented CFB endpoints use /sports/football_ncaaf/... directly.
    return "football_ncaaf"


def _event_date(commence_time: Any) -> str:
    s = str(commence_time or "")
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).date().isoformat()
    except Exception:
        return s[:10]


def fetch_events(api_key: str, target_date: Optional[str] = None) -> Tuple[List[dict], dict]:
    sport = discover_cfb_sport(api_key)
    data, quota = _request(f"/sports/{sport}/events", api_key, ttl=300)
    rows = data if isinstance(data, list) else (data or {}).get("events", [])
    if target_date:
        rows = [r for r in rows if _event_date(r.get("commence_time")) == str(target_date)]
    return rows, {"sport": sport, "quota": quota}


def _player_name(outcome: dict) -> str:
    # PropLine uses description for player name on player prop outcomes.
    return str(outcome.get("description") or outcome.get("player_name") or outcome.get("player") or "").strip()


def _side(outcome: dict) -> str:
    n = str(outcome.get("name") or outcome.get("outcome_name") or "").lower()
    if n in {"over", "higher", "yes"}:
        return "Over"
    if n in {"under", "lower", "no"}:
        return "Under"
    return ""


def _flatten_event_props(payload: dict) -> List[dict]:
    event_id = str(payload.get("id") or payload.get("event_id") or "")
    away = str(payload.get("away_team") or "")
    home = str(payload.get("home_team") or "")
    starts = payload.get("commence_time")
    buckets: Dict[Tuple[str, str], dict] = {}
    for bm in payload.get("bookmakers", []) or []:
        book = str(bm.get("key") or bm.get("title") or "")
        for market in bm.get("markets", []) or []:
            key = str(market.get("key") or "")
            label = MARKET_TO_LABEL.get(key)
            if not label:
                continue
            for o in market.get("outcomes", []) or []:
                player = _player_name(o)
                side = _side(o)
                point = o.get("point")
                if not player or not side or point is None:
                    continue
                bkey = (_norm(player), label)
                d = buckets.setdefault(bkey, {
                    "player": player, "prop": label, "lines": [], "books": set(),
                    "away": away, "home": home, "event_id": event_id,
                    "scheduled_at": starts,
                })
                d["lines"].append(_f(point))
                if book:
                    d["books"].add(book)
    out = []
    for d in buckets.values():
        if not d["lines"]:
            continue
        line = float(np.median(d.pop("lines")))
        books = sorted(d.pop("books"))
        d.update({
            "team": "", "matchup": f"{away} @ {home}", "line": line,
            "side": "AUTO", "source": "PropLine", "source_url": "",
            "line_status": "active", "line_type": "sportsbook_consensus",
            "non_discounted_line": None, "books": ",".join(books),
        })
        out.append(d)
    return out


def fetch_propline_cfb_props(api_key: str, target_date: Optional[str] = None, max_events: int = 40) -> Tuple[List[dict], dict]:
    debug: Dict[str, Any] = {"provider": "PropLine", "target_date": target_date, "errors": []}
    if not api_key:
        debug["status"] = "NO_KEY"
        return [], debug
    try:
        events, meta = fetch_events(api_key, target_date=target_date)
        debug.update(meta)
        debug["events"] = len(events)
        rows: List[dict] = []
        last_quota = meta.get("quota", {})
        markets = ",".join(STANDARD_MARKETS)
        for ev in events[:max_events]:
            eid = str(ev.get("id") or "")
            if not eid:
                continue
            try:
                payload, quota = _request(f"/sports/{meta['sport']}/events/{eid}/odds", api_key, params={"markets": markets}, ttl=300)
                last_quota = quota or last_quota
                if isinstance(payload, dict):
                    rows.extend(_flatten_event_props(payload))
            except Exception as exc:
                debug["errors"].append(f"event {eid}: {exc}")
        debug["rows"] = len(rows)
        debug["quota"] = last_quota
        debug["status"] = "OK" if rows else "EMPTY"
        return rows, debug
    except Exception as exc:
        debug["status"] = "ERROR"
        debug["errors"].append(str(exc))
        return [], debug


def fetch_propline_game_markets(api_key: str) -> Tuple[Dict[Tuple[str, str], dict], dict]:
    """One-call game-line backup for h2h/spreads/totals."""
    debug: Dict[str, Any] = {"provider": "PropLine", "errors": []}
    if not api_key:
        debug["status"] = "NO_KEY"
        return {}, debug
    try:
        sport = discover_cfb_sport(api_key)
        data, quota = _request(f"/sports/{sport}/odds", api_key, params={"markets": "h2h,spreads,totals"}, ttl=300)
        events = data if isinstance(data, list) else (data or {}).get("events", [])
        out: Dict[Tuple[str, str], dict] = {}
        for e in events:
            away, home = str(e.get("away_team") or ""), str(e.get("home_team") or "")
            if not away or not home:
                continue
            spreads, totals = [], []
            for bm in e.get("bookmakers", []) or []:
                for m in bm.get("markets", []) or []:
                    if m.get("key") == "spreads":
                        for o in m.get("outcomes", []) or []:
                            if _norm(o.get("name")) == _norm(home) and o.get("point") is not None:
                                spreads.append(_f(o.get("point")))
                    elif m.get("key") == "totals":
                        for o in m.get("outcomes", []) or []:
                            if str(o.get("name") or "").lower() == "over" and o.get("point") is not None:
                                totals.append(_f(o.get("point")))
            rec = {"event_id": str(e.get("id") or ""), "away": away, "home": home, "source": "PropLine"}
            if spreads:
                rec["market_home_spread"] = float(np.median(spreads))
            if totals:
                rec["market_total"] = float(np.median(totals))
            out[(_norm(away), _norm(home))] = rec
        debug.update({"sport": sport, "games": len(out), "quota": quota, "status": "OK"})
        return out, debug
    except Exception as exc:
        debug["status"] = "ERROR"
        debug["errors"].append(str(exc))
        return {}, debug


def merge_line_feeds(primary: List[dict], fallback: List[dict]) -> List[dict]:
    """Prefer Underdog for exact player/market/line duplicates, fill gaps from PropLine."""
    out = list(primary or [])
    seen = {(_norm(r.get("player")), str(r.get("prop") or ""), round(_f(r.get("line")), 3), _norm(r.get("away")), _norm(r.get("home"))) for r in out}
    for r in fallback or []:
        key = (_norm(r.get("player")), str(r.get("prop") or ""), round(_f(r.get("line")), 3), _norm(r.get("away")), _norm(r.get("home")))
        if key not in seen:
            out.append(r)
            seen.add(key)
    return out
