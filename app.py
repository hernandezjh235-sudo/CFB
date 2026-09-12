from __future__ import annotations

import json, math, os, re, time, hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import streamlit as st
from free_data_v16 import load_free_stack
from underdog_cfb_v15 import fetch_underdog_cfb_props, props_for_game
from cfb_nfl_ui_v18 import hydrate_team_branding, inject_nfl_cfb_css, render_moneyline_nfl, render_player_nfl, render_fast_rows
from cfb_runtime_v20 import (annotate_games, ensure_branding, filter_games_by_scope, filter_props_by_scope,
    local_now, scope_target_date, logo_coverage, day_games, canonical_prop_team, prop_rows_date_label, games_from_props)
from cfb_opportunity_v25 import enrich_opportunity, automatic_weather
from cfb_blowout_v26 import enrich_blowout_context, game_blowout_profile, player_blowout_modifier
from cfb_quality_v27 import stabilize_projection, calibrate_probability, status_from_quality
from cfb_integrity_v28 import integrity_audit, enforce_integrity_status, market_grade_summary, segment_grade_summary, miss_audit
from cfb_role_v30 import enrich_role_depth, role_adjust_projection, qb_upset_margin_delta
from propline_cfb_v31 import fetch_propline_cfb_props, fetch_propline_game_markets, merge_line_feeds

APP_VERSION = "CFB Prop Engine v3.1 — ROLE DEPTH + QB UPSET + PROPLINE FALLBACK"
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
CACHE_DIR = BASE / "cache"
DATA_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)

CFBD_BASE = "https://api.collegefootballdata.com"
ODDS_BASE = "https://api.the-odds-api.com/v4"
NCAAF_SPORT_KEY = "americanfootball_ncaaf"

PLAYER_MARKETS = {
    "Passing Yards": "player_pass_yds",
    "Pass Attempts": "player_pass_attempts",
    "Completions": "player_pass_completions",
    "Passing TDs": "player_pass_tds",
    "Interceptions": "player_pass_interceptions",
    "Rushing Yards": "player_rush_yds",
    "Rush Attempts": "player_rush_attempts",
    "Receiving Yards": "player_reception_yds",
    "Receptions": "player_receptions",
    "Pass + Rush Yards": "player_pass_rush_yds",
    "Rush + Rec Yards": "player_rush_reception_yds",
    "Rush + Rec TDs": "player_rush_reception_tds",
    "Total TDs": "player_pass_rush_reception_tds",
}
ODDS_TO_LABEL = {v: k for k, v in PLAYER_MARKETS.items()}

st.set_page_config(page_title="CFB Prop Engine", page_icon="🏈", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
:root{--panel:#0f1720;--panel2:#151e29;--line:#263241;--muted:#9aa8b7;--good:#46e59b;--warn:#ffd166;--bad:#ff6b6b;--blue:#35a7ff}
.stApp{background:linear-gradient(180deg,#071018 0%,#0a1118 100%);color:#f5f7fb}
.block-container{padding-top:1.2rem;max-width:1500px}
.hero{background:linear-gradient(135deg,#0d1d2b,#121b27);border:1px solid #243342;border-radius:22px;padding:22px 24px;margin-bottom:16px}
.hero h1{margin:0;font-size:2rem}.hero p{color:#aab7c5;margin:.35rem 0 0}
.badge{display:inline-block;background:#182736;border:1px solid #2c4154;padding:5px 10px;border-radius:999px;margin:8px 6px 0 0;font-size:.82rem}
.card{background:#0e1720;border:1px solid #22303f;border-radius:18px;padding:15px 16px;margin:7px 0;box-shadow:0 10px 30px rgba(0,0,0,.15)}
.metricbig{font-size:1.55rem;font-weight:800}.small{font-size:.82rem;color:#99a8b8}.good{color:#46e59b}.warn{color:#ffd166}.bad{color:#ff6b6b}.blue{color:#35a7ff}
.tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#18232f;border:1px solid #2a3948;margin:2px;font-size:.76rem}
[data-testid="stMetric"]{background:#0f1822;border:1px solid #253343;padding:12px;border-radius:15px}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.block-container{max-width:1750px!important;padding-left:1rem!important;padding-right:1rem!important}
.cfb-player-card{--team:#2f81f7;position:relative;overflow:hidden;background:radial-gradient(circle at 0% 0%,color-mix(in srgb,var(--team) 28%,transparent),transparent 32%),linear-gradient(145deg,#09131e 0%,#050a11 100%);border:1px solid color-mix(in srgb,var(--team) 58%,#24384c);border-left:4px solid var(--team);border-radius:20px;padding:14px 15px;margin:10px 0;box-shadow:0 12px 35px rgba(0,0,0,.22)}
.cfb-card-top{display:grid;grid-template-columns:62px minmax(0,1fr) auto;gap:11px;align-items:center}.cfb-team-logo{width:58px;height:58px;object-fit:contain;filter:drop-shadow(0 0 8px color-mix(in srgb,var(--team) 55%,transparent))}
.cfb-player-name{font-size:20px;font-weight:950;line-height:1.05;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfb-player-sub{font-size:10px;color:#9fb1c3;text-transform:uppercase;font-weight:850;letter-spacing:.07em;margin-top:4px}
.cfb-status{font-size:10px;font-weight:950;padding:6px 9px;border-radius:999px;border:1px solid #2b4156;background:#0b1722}.cfb-status.playable{color:#66f594;border-color:#2a7044}.cfb-status.lean{color:#ffd166;border-color:#79672d}.cfb-status.track{color:#9eb1c4}
.cfb-prop-title{margin-top:10px;font-size:11px;color:#8da1b5;text-transform:uppercase;font-weight:900;letter-spacing:.08em}.cfb-proj-row{display:grid;grid-template-columns:1.1fr .8fr .8fr .8fr;gap:7px;margin-top:6px}
.cfb-box{background:rgba(3,9,15,.72);border:1px solid #1c3043;border-radius:11px;padding:8px;text-align:center}.cfb-box .lab{font-size:7px;color:#7890a8;text-transform:uppercase;font-weight:900;letter-spacing:.08em}.cfb-box .val{font-size:17px;font-weight:950;margin-top:2px}.cfb-box.main .val{font-size:23px}.cfb-prob{color:#65f28a}.cfb-edge.good{color:#65f28a}.cfb-edge.bad{color:#ff7385}
.cfb-match-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:8px}.cfb-mini{background:#07111a;border:1px solid #172b3e;border-radius:9px;padding:7px;text-align:center}.cfb-mini .lab{font-size:7px;color:#778da4;text-transform:uppercase;font-weight:900}.cfb-mini .val{font-size:12px;font-weight:900;margin-top:2px}
.cfb-why{border-top:1px solid #182b3d;margin-top:9px;padding-top:8px;font-size:9px;color:#a6b7c8;line-height:1.45}.cfb-game-strip{font-size:9px;color:#91a6bb;margin-top:6px}
@media(max-width:900px){.cfb-player-card{border-radius:16px;padding:12px}.cfb-player-name{font-size:18px}}
@media(max-width:560px){.block-container{padding-left:.55rem!important;padding-right:.55rem!important}.cfb-card-top{grid-template-columns:48px minmax(0,1fr) auto}.cfb-team-logo{width:46px;height:46px}.cfb-proj-row{grid-template-columns:1.1fr .8fr}.cfb-match-grid{grid-template-columns:repeat(2,1fr)}.cfb-box .val{font-size:15px}.cfb-box.main .val{font-size:20px}}
</style>
""", unsafe_allow_html=True)


st.markdown("""
<style>
.cfb-live-strip{background:#0a1621;border:1px solid #21415d;border-radius:14px;padding:10px 12px;margin:8px 0 12px;font-size:12px;color:#b9cada}.cfb-live-strip b{color:#65f28a}.cfb-raw-card{background:#0b141d;border:1px solid #203141;border-radius:14px;padding:10px 12px;margin:7px 0}.cfb-raw-name{font-weight:900;font-size:15px}.cfb-raw-sub{font-size:10px;color:#8fa4b8}.cfb-raw-line{font-size:20px;font-weight:950;margin-top:3px}
</style>
""", unsafe_allow_html=True)

def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, os.getenv(name, default)) or default)
    except Exception:
        return str(os.getenv(name, default) or default)


def clamp(x: float, lo: float, hi: float) -> float:
    try: return max(lo, min(hi, float(x)))
    except Exception: return lo


def sf(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def norm_name(x: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x).lower())


def cache_path(key: str) -> Path:
    return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".json")


def get_json(url: str, headers=None, params=None, ttl=900, force=False) -> Any:
    params = params or {}
    key = url + "?" + json.dumps(params, sort_keys=True, default=str)
    p = cache_path(key)
    if p.exists() and not force and time.time() - p.stat().st_mtime < ttl:
        try: return json.loads(p.read_text())
        except Exception: pass
    r = requests.get(url, headers=headers or {}, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()
    try: p.write_text(json.dumps(data))
    except Exception: pass
    return data


class CFBD:
    def __init__(self, key: str): self.key = key.strip()
    @property
    def ready(self): return bool(self.key)
    def get(self, endpoint: str, params=None, ttl=1800, force=False):
        if not self.key: return []
        headers = {"Authorization": f"Bearer {self.key}"}
        return get_json(CFBD_BASE + endpoint, headers=headers, params=params, ttl=ttl, force=force)


class OddsAPI:
    def __init__(self, key: str): self.key = key.strip()
    @property
    def ready(self): return bool(self.key)
    def events(self, force=False):
        if not self.key: return []
        return get_json(f"{ODDS_BASE}/sports/{NCAAF_SPORT_KEY}/events", params={"apiKey":self.key}, ttl=300, force=force)
    def game_odds(self, force=False):
        if not self.key: return []
        return get_json(f"{ODDS_BASE}/sports/{NCAAF_SPORT_KEY}/odds", params={"apiKey":self.key,"regions":"us","markets":"h2h,spreads,totals","oddsFormat":"american"}, ttl=240, force=force)
    def event_props(self, event_id: str, markets: List[str], force=False):
        if not self.key or not event_id: return []
        return get_json(f"{ODDS_BASE}/sports/{NCAAF_SPORT_KEY}/events/{event_id}/odds", params={"apiKey":self.key,"regions":"us","markets":",".join(markets),"oddsFormat":"american"}, ttl=180, force=force)


def zmap(rows: Dict[str, float], reverse=False) -> Dict[str,float]:
    vals=np.array([v for v in rows.values() if math.isfinite(v)], dtype=float)
    if len(vals)<2 or np.nanstd(vals)<1e-9: return {k:0.0 for k in rows}
    mu,sd=float(np.nanmean(vals)),float(np.nanstd(vals))
    return {k:(-1 if reverse else 1)*(v-mu)/sd for k,v in rows.items()}


def latest_ap_rank(rankings: list) -> Dict[str,int]:
    out={}
    for week in rankings or []:
        polls=week.get("polls",[]) if isinstance(week,dict) else []
        for poll in polls:
            name=str(poll.get("poll","")).lower()
            if "ap" in name:
                for r in poll.get("ranks",[]):
                    team=r.get("school") or r.get("team")
                    if team: out[str(team)] = int(sf(r.get("rank"),99))
    return out


def team_games_played(games:list, through_week:int) -> Dict[str,int]:
    c={}
    for g in games or []:
        if int(sf(g.get("week"),0))>through_week: continue
        if g.get("home_points") is None and g.get("homePoints") is None: continue
        for key in [("home_team","homeTeam"),("away_team","awayTeam")]:
            t=g.get(key[0]) or g.get(key[1])
            if t: c[t]=c.get(t,0)+1
    return c


def flatten_sp(row:dict) -> dict:
    off=row.get("offense") or {}; de=row.get("defense") or {}; havoc=de.get("havoc") or {}; stt=row.get("specialTeams") or row.get("special_teams") or {}
    return {
        "sp":sf(row.get("rating")),"sp_sos":sf(row.get("sos")),"off_rating":sf(off.get("rating")),"off_passing":sf(off.get("passing")),"off_rushing":sf(off.get("rushing")),"off_expl":sf(off.get("explosiveness")),"off_success":sf(off.get("success")),"pace":sf(off.get("pace")),"run_rate":sf(off.get("runRate")),
        "def_rating":sf(de.get("rating")),"def_passing":sf(de.get("passing")),"def_rushing":sf(de.get("rushing")),"def_expl":sf(de.get("explosiveness")),"def_success":sf(de.get("success")),"havoc":sf(havoc.get("total")),"special":sf(stt.get("rating"))
    }


def build_team_context(bundle:dict) -> Dict[str,dict]:
    teams={}
    def rowteam(r): return r.get("team") or r.get("school")
    for r in bundle.get("sp",[]):
        t=rowteam(r)
        if t: teams.setdefault(t,{}).update(flatten_sp(r))
    for r in bundle.get("core",[]):
        t=rowteam(r)
        if t: teams.setdefault(t,{}).update({"core":sf(r.get("overall")),"core_off":sf(r.get("offense")),"core_def":sf(r.get("defense"))})
    for r in bundle.get("srs",[]):
        t=rowteam(r)
        if t: teams.setdefault(t,{})["srs"]=sf(r.get("rating"))
    for r in bundle.get("elo",[]):
        t=rowteam(r)
        if t: teams.setdefault(t,{})["elo"]=sf(r.get("elo"),1500)
    for r in bundle.get("teams",[]):
        t=r.get("school")
        if t:
            logos=r.get("logos") or []
            teams.setdefault(t,{}).update({"logo":logos[0] if logos else "","color":("#"+str(r.get("color","")).lstrip("#")) if r.get("color") else "#2f81f7","conference":r.get("conference") or ""})
    for r in bundle.get("talent",[]):
        t=rowteam(r)
        if t: teams.setdefault(t,{})["talent"]=sf(r.get("talent"))
    ap=latest_ap_rank(bundle.get("rankings",[]))
    for t,rk in ap.items(): teams.setdefault(t,{})["ap_rank"]=rk

    # Build a robust model rank from multiple independent power lenses.
    components={
        "sp":zmap({t:d.get("sp",0.0) for t,d in teams.items()}),
        "core":zmap({t:d.get("core",0.0) for t,d in teams.items()}),
        "srs":zmap({t:d.get("srs",0.0) for t,d in teams.items()}),
        "elo":zmap({t:d.get("elo",1500.0) for t,d in teams.items()}),
        "talent":zmap({t:d.get("talent",0.0) for t,d in teams.items()}),
    }
    for t,d in teams.items():
        p=.34*components["sp"].get(t,0)+.26*components["core"].get(t,0)+.18*components["srs"].get(t,0)+.14*components["elo"].get(t,0)+.08*components["talent"].get(t,0)
        d["power_z"]=p
    ordered=sorted(teams, key=lambda t:teams[t].get("power_z",0), reverse=True)
    for i,t in enumerate(ordered,1): teams[t]["model_rank"]=i
    return teams


def get_team(ctx:Dict[str,dict], name:str)->dict:
    if name in ctx: return ctx[name]
    n=norm_name(name)
    for t,d in ctx.items():
        if norm_name(t)==n: return d
    return {}


def implied_market(odds_rows:list)->Dict[Tuple[str,str],dict]:
    out={}
    for e in odds_rows or []:
        away=e.get("away_team"); home=e.get("home_team")
        rec={"event_id":e.get("id"),"away":away,"home":home}
        spreads=[]; totals=[]; h2h=[]
        for bm in e.get("bookmakers",[]):
            for m in bm.get("markets",[]):
                if m.get("key")=="spreads":
                    for o in m.get("outcomes",[]):
                        if o.get("name")==home and o.get("point") is not None: spreads.append(sf(o.get("point")))
                elif m.get("key")=="totals":
                    for o in m.get("outcomes",[]):
                        if str(o.get("name","")).lower()=="over" and o.get("point") is not None: totals.append(sf(o.get("point")))
                elif m.get("key")=="h2h":
                    vals={o.get("name"):sf(o.get("price")) for o in m.get("outcomes",[])}
                    if vals: h2h.append(vals)
        if spreads: rec["market_home_spread"]=float(np.median(spreads))
        if totals: rec["market_total"]=float(np.median(totals))
        out[(norm_name(away),norm_name(home))]=rec
    return out


def logistic(x:float)->float: return 1/(1+math.exp(-clamp(x,-30,30)))


def project_game(away:str,home:str,ctx:dict,market:dict|None=None,neutral=False)->dict:
    a=get_team(ctx,away); h=get_team(ctx,home); market=market or {}
    # Ratings are in heterogeneous units; use SP/SRS in native point-like units and z-score power as stabilization.
    sp_gap=sf(h.get("sp"))-sf(a.get("sp"))
    srs_gap=sf(h.get("srs"))-sf(a.get("srs"))
    core_gap=(sf(h.get("core"))-sf(a.get("core")))*0.18
    elo_gap=(sf(h.get("elo"),1500)-sf(a.get("elo"),1500))/28.0
    power_gap=(sf(h.get("power_z"))-sf(a.get("power_z")))*2.8
    hfa=0 if neutral else 2.25
    model_margin=.44*sp_gap+.22*srs_gap+.16*core_gap+.08*elo_gap+.10*power_gap+hfa
    # v3.0: bounded explosive-QB upset path. Team power still anchors the game,
    # but a major passing-efficiency/explosive mismatch can materially narrow or
    # widen the margin instead of being buried by roster/power ratings.
    upset_delta,upset_notes=qb_upset_margin_delta(h,a)
    model_margin+=upset_delta
    # Market is a low-weight audit/stabilizer, never the driver.
    if market.get("market_home_spread") is not None:
        market_margin=-sf(market["market_home_spread"])
        model_margin=.88*model_margin+.12*market_margin
    home_wp=logistic(model_margin/6.4)

    # v2.5 total: offense/defense remains the stable prior, while actual possessions,
    # drive success, third-down sustain, turnovers and explosives determine opportunity.
    h_off=sf(h.get("off_rating")); a_off=sf(a.get("off_rating")); h_def=sf(h.get("def_rating")); a_def=sf(a.get("def_rating"))
    pace=(sf(h.get("pace"))+sf(a.get("pace")))/2
    expl=(sf(h.get("off_expl"))+sf(a.get("off_expl"))-sf(h.get("def_expl"))-sf(a.get("def_expl")))/4
    drive_pg=np.mean([x for x in [sf(h.get('drives_pg')),sf(a.get('drives_pg'))] if x>0]) if any(sf(x.get('drives_pg'))>0 for x in [h,a]) else 11.5
    score_rate=np.mean([x for x in [sf(h.get('score_drive_rate')),sf(a.get('score_drive_rate'))] if x>0]) if any(sf(x.get('score_drive_rate'))>0 for x in [h,a]) else .34
    td_rate=np.mean([x for x in [sf(h.get('td_drive_rate')),sf(a.get('td_drive_rate'))] if x>0]) if any(sf(x.get('td_drive_rate'))>0 for x in [h,a]) else .24
    sustain=np.mean([sf(h.get('third_down_rate')),sf(a.get('third_down_rate')),sf(h.get('third_down_success_rate')),sf(a.get('third_down_success_rate'))])
    turnovers=sf(h.get('turnovers_pg'))+sf(a.get('turnovers_pg'))
    ypp=np.mean([x for x in [sf(h.get('yards_per_play')),sf(a.get('yards_per_play'))] if x>0]) if any(sf(x.get('yards_per_play'))>0 for x in [h,a]) else 5.7
    drive_signal=clamp((drive_pg-11.5)*1.0 + (score_rate-.34)*24 + (td_rate-.24)*18 + (sustain-.40)*8 - max(turnovers-2.2,0)*.8 + (ypp-5.7)*1.2,-8,9)
    total=55.0 + .25*(h_off+a_off) - .18*(h_def+a_def) + .08*pace + .07*expl + drive_signal
    total=clamp(total,34,86)
    if market.get("market_total") is not None: total=.90*total+.10*sf(market["market_total"])
    home_pts=(total+model_margin)/2; away_pts=(total-model_margin)/2

    talent_gap=(sf(h.get("talent"))-sf(a.get("talent")))
    favorite=home if model_margin>=0 else away
    # Dedicated CFB blowout engine: projected margin + power/talent gap + explosive
    # mismatch + underdog drive sustainability + turnover risk + historical coach hook.
    blow_profile=game_blowout_profile({"away":away,"home":home,"model_home_margin":model_margin,"model_total":total,"favorite":favorite},h,a)
    blowout_p=sf(blow_profile.get("blowout_prob"))
    tags=list(upset_notes)
    if abs(upset_delta)>=2.5: tags.append('⚡ QB UPSET PATH')
    pass_funnel_home = sf(a.get("def_passing"))-sf(a.get("def_rushing"))
    pass_funnel_away = sf(h.get("def_passing"))-sf(h.get("def_rushing"))
    if total>=61: tags.append("🔥 SHOOTOUT")
    if blow_profile.get("blowout_level") in {"HIGH","EXTREME"}: tags.append(f"⚠️ {blow_profile.get('blowout_level')} BLOWOUT")
    if sf(blow_profile.get("coach_hook_aggression"))>=.55: tags.append("🔄 EARLY HOOK TEAM")
    if pace>0.4: tags.append("⚡ FAST PACE")
    return {"away":away,"home":home,"model_home_margin":model_margin,"home_win_prob":home_wp,"away_win_prob":1-home_wp,"model_total":total,"home_points":home_pts,"away_points":away_pts,"blowout_prob":blowout_p,"favorite":favorite,"tags":tags,"home_pass_funnel":pass_funnel_home,"away_pass_funnel":pass_funnel_away,
            "market_home_spread":market.get("market_home_spread"),"market_total":market.get("market_total"),"home_ap":h.get("ap_rank"),"away_ap":a.get("ap_rank"),"home_model_rank":h.get("model_rank"),"away_model_rank":a.get("model_rank"),
            "blowout_level":blow_profile.get("blowout_level"),"coach_hook_aggression":blow_profile.get("coach_hook_aggression"),
            "qb_starter_retention":blow_profile.get("qb_starter_retention"),"wr1_retention":blow_profile.get("wr1_retention"),"rb1_retention":blow_profile.get("rb1_retention"),
            "backup_opportunity":blow_profile.get("backup_opportunity"),"underdog_catchup_mult":blow_profile.get("underdog_catchup_mult"),"blowout_components":blow_profile.get("blowout_components",{}),"qb_upset_margin_delta":upset_delta,"qb_upset_notes":upset_notes}


def parse_player_stats(rows:list, games_played:dict)->pd.DataFrame:
    recs={}
    for r in rows or []:
        player=r.get("player") or r.get("playerName") or r.get("athlete") or r.get("athleteName")
        team=r.get("team"); cat=str(r.get("category","")).lower(); typ=str(r.get("statType") or r.get("stat_type") or r.get("stat") or "").lower(); val=sf(r.get("stat") if not isinstance(r.get("stat"),str) else r.get("stat"),0)
        # Legacy CFBD player-season rows usually carry category/statType/stat.
        if not player: continue
        key=(str(player),str(team or "")); d=recs.setdefault(key,{"player":player,"team":team})
        k=(cat+" "+typ).lower()
        mappings=[
            (("passing", "yd"),"pass_yds"),(("passing","attempt"),"pass_att"),(("passing","completion"),"pass_comp"),(("passing","td"),"pass_td"),(("passing","interception"),"pass_int"),
            (("rushing","yd"),"rush_yds"),(("rushing","attempt"),"rush_att"),(("rushing","td"),"rush_td"),
            (("receiv","yd"),"rec_yds"),(("receiv","reception"),"receptions"),(("receiv","td"),"rec_td"),
        ]
        for (a,b),name in mappings:
            if a in k and b in k: d[name]=d.get(name,0)+val
    out=[]
    for d in recs.values():
        gp=max(1,int(games_played.get(d.get("team"),1)))
        d["games"]=gp
        for k in ["pass_yds","pass_att","pass_comp","pass_td","pass_int","rush_yds","rush_att","rush_td","rec_yds","receptions","rec_td"]: d[k]=sf(d.get(k))
        out.append(d)
    return pd.DataFrame(out)


def lookup_player(df:pd.DataFrame,name:str)->dict:
    if df is None or df.empty:return {}
    n=norm_name(name)
    exact=df[df["player"].astype(str).map(norm_name)==n]
    if len(exact): return exact.iloc[0].to_dict()
    # Conservative fuzzy fallback: only prefix+surname-like normalized containment.
    hits=df[df["player"].astype(str).map(lambda x:n in norm_name(x) or norm_name(x) in n)]
    return hits.iloc[0].to_dict() if len(hits)==1 else {}


def player_projection(player:dict, market_label:str, team_ctx:dict, opp_ctx:dict, game:dict, team_name:str)->Tuple[float,float,List[str]]:
    gp=max(1,sf(player.get("games"),1)); notes=[]
    is_fav=(game.get("favorite")==team_name); blow=sf(game.get("blowout_prob"))
    margin=sf(game.get("model_home_margin")); team_is_home=(team_name==game.get("home")); team_margin=margin if team_is_home else -margin
    pass_script=1.0 + clamp(-team_margin/120,-.10,.16) # trailing teams throw more
    rush_script=1.0 + clamp(team_margin/140,-.11,.14)
    pace_adj=1.0+clamp((sf(team_ctx.get("pace"))+sf(opp_ctx.get("pace")))/140,-.06,.08)
    snap_adj=1.0
    starter_current=bool(player.get('starter_current'))
    if starter_current: notes.append("current starter confirmed")
    if blow>=.55: notes.append("v2.6 coach-aware blowout engine active")
    pass_def=sf(opp_ctx.get("def_passing")); rush_def=sf(opp_ctx.get("def_rushing")); expl_def=sf(opp_ctx.get("def_expl")); havoc=sf(opp_ctx.get("havoc"))
    pass_match=clamp(1.0 + (-pass_def)*.018 + (-expl_def)*.007 - havoc*.004, .78,1.23)
    rush_match=clamp(1.0 + (-rush_def)*.020 - havoc*.003, .78,1.24)
    # If pass defense is materially weaker than rush defense, label the pass funnel.
    if pass_match>rush_match+0.05: notes.append("pass-funnel matchup")

    pass_y=sf(player.get("pass_yds"))/gp; pass_att=sf(player.get("pass_att"))/gp; comp=sf(player.get("pass_comp"))/gp
    rush_y=sf(player.get("rush_yds"))/gp; rush_att=sf(player.get("rush_att"))/gp
    rec_y=sf(player.get("rec_yds"))/gp; recs=sf(player.get("receptions"))/gp
    pass_td=sf(player.get("pass_td"))/gp; ints=sf(player.get("pass_int"))/gp
    adv_att=sf(player.get('adv_pass_att')); adv_ypa=sf(player.get('adv_ypa')); adv_cpoe=sf(player.get('adv_cpoe')); adv_pass_epa=sf(player.get('adv_pass_epa'))
    adv_car=sf(player.get('adv_rush_car')); adv_ypc=sf(player.get('adv_ypc')); adv_rush_epa=sf(player.get('adv_rush_epa')); carry_share=clamp(sf(player.get('adv_carry_share')),0,.92)
    adv_tar=sf(player.get('adv_targets')); adv_catch=sf(player.get('adv_catch_rate')); adv_ypt=sf(player.get('adv_ypt')); adv_rec_epa=sf(player.get('adv_rec_epa')); target_share=clamp(sf(player.get('adv_target_share')),0,.58)
    air_share=clamp(sf(player.get('air_yard_share')),0,.80); qb_rush_share=clamp(sf(player.get('qb_rush_share')),0,.65); sack_rate=clamp(sf(player.get('sack_rate')),0,.30)
    drives=sf(team_ctx.get('drives_pg'),11.5); plays_drive=sf(team_ctx.get('plays_per_drive'),5.7); score_drive=sf(team_ctx.get('score_drive_rate'),.34); rz=sf(team_ctx.get('red_zone_success_rate'),.55)
    early_pass=sf(team_ctx.get('early_down_pass_rate')); early_rush=sf(team_ctx.get('early_down_rush_rate')); start_field=sf(team_ctx.get('avg_start_yard_line'),50)
    volume_drive=clamp(1+(drives-11.5)*.018+(plays_drive-5.7)*.015,.90,1.12)
    scoring_env=clamp(1+(score_drive-.34)*.18+(rz-.55)*.10+(start_field-50)*.002,.90,1.12)
    sample_source=str(player.get("sample_source") or "current").lower()
    # Opening-week opportunity correction: an active QB/skill prop indicates the
    # player has a meaningful current role, while an old tiny backup sample may not.
    # We do NOT use the sportsbook line value to set the projection; we only shrink
    # stale/small personal samples toward independent team production.
    team_pass=sf(team_ctx.get("team_pass_yds_pg")); team_att=sf(team_ctx.get("team_pass_att_pg")); team_comp=sf(team_ctx.get("team_pass_comp_pg"))
    sample_team=str(player.get('team') or '')
    current_team=str(player.get('current_team') or '')
    transferred=bool(sample_source=='prior' and current_team and sample_team and norm_name(current_team)!=norm_name(sample_team))
    if transferred and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Pass + Rush Yards"}:
        if team_pass>0: pass_y=team_pass*.90
        if team_att>0: pass_att=team_att*.90
        if team_comp>0: comp=team_comp*.90
        if sf(team_ctx.get('team_pass_td_pg'))>0: pass_td=sf(team_ctx.get('team_pass_td_pg'))*.88
        notes.append('transfer/current-role reset to new-team opportunity')
    if sample_source=="prior" and not transferred and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Pass + Rush Yards"}:
        rel=clamp(gp/(gp+7.0),.18,.72)
        if team_pass>0 and (pass_y<=0 or pass_y < team_pass*.62):
            pass_y=rel*pass_y + (1-rel)*(team_pass*.90); notes.append("role reset: prior backup sample shrunk to team QB baseline")
        if team_att>0 and (pass_att<=0 or pass_att < team_att*.62): pass_att=rel*pass_att + (1-rel)*(team_att*.90)
        if team_comp>0 and (comp<=0 or comp < team_comp*.62): comp=rel*comp + (1-rel)*(team_comp*.90)
    # NFL-app style opening-week fallback: use independent team production baselines
    # when the player has no current/prior personal sample. The prop line is NOT used
    # to manufacture the projection.
    used_team_prior=False
    if pass_y<=0 and sf(team_ctx.get("team_pass_yds_pg"))>0:
        pass_y=sf(team_ctx.get("team_pass_yds_pg"))*.92; used_team_prior=True
    if pass_att<=0 and sf(team_ctx.get("team_pass_att_pg"))>0:
        pass_att=sf(team_ctx.get("team_pass_att_pg"))*.92; used_team_prior=True
    if comp<=0 and sf(team_ctx.get("team_pass_comp_pg"))>0:
        comp=sf(team_ctx.get("team_pass_comp_pg"))*.92; used_team_prior=True
    if pass_td<=0 and sf(team_ctx.get("team_pass_td_pg"))>0:
        pass_td=sf(team_ctx.get("team_pass_td_pg"))*.88; used_team_prior=True
    if rush_y<=0 and sf(team_ctx.get("team_rush_yds_pg"))>0:
        rush_y=sf(team_ctx.get("team_rush_yds_pg"))*.34; used_team_prior=True
    if rush_att<=0 and sf(team_ctx.get("team_rush_att_pg"))>0:
        rush_att=sf(team_ctx.get("team_rush_att_pg"))*.30; used_team_prior=True
    if rec_y<=0 and sf(team_ctx.get("team_pass_yds_pg"))>0:
        rec_y=sf(team_ctx.get("team_pass_yds_pg"))*.23; used_team_prior=True
    if recs<=0 and sf(team_ctx.get("team_pass_comp_pg"))>0:
        recs=sf(team_ctx.get("team_pass_comp_pg"))*.19; used_team_prior=True
    if used_team_prior:
        notes.append("opening-week team production baseline")
    if market_label=="Passing Yards":
        if adv_att>0 and adv_ypa>0 and team_att>0:
            qb_share=clamp(adv_att/max(team_att,1),.55,1.05)
            exp_att=team_att*qb_share*pass_script*pace_adj*snap_adj
            team_ypa=team_pass/max(team_att,1) if team_att>0 else 7.0
            ypa=.58*adv_ypa+.42*team_ypa
            pressure_tax=clamp(1-sack_rate*.30-max(sf(opp_ctx.get('havoc')),0)*.004,.88,1.03)
            pass_tendency=clamp(1+(early_pass-.50)*.10,.94,1.06) if early_pass>0 else 1.0
            eff=clamp(1+adv_cpoe*.20+adv_pass_epa*.07,.92,1.09)
            proj=exp_att*ypa*eff*pass_match*pressure_tax*volume_drive*pass_tendency
            notes.append("attempt share × YPA + drive/pressure opportunity")
        else:
            base=pass_y; proj=base*pass_script*pace_adj*snap_adj*pass_match
        sd=max(34,0.20*proj)
    elif market_label=="Pass Attempts":
        proj=pass_att*pass_script*pace_adj*snap_adj; sd=max(4.5,.16*proj)
    elif market_label=="Completions":
        rate=comp/max(pass_att,1); att=pass_att*pass_script*pace_adj*snap_adj; proj=att*clamp(rate*(.985+.015*pass_match),.48,.78); sd=max(3.2,.16*proj)
    elif market_label=="Passing TDs":
        proj=max(.05,pass_td*(game.get("model_total",55)/55)*pass_match*snap_adj); sd=max(.8,math.sqrt(proj))
    elif market_label=="Interceptions":
        proj=max(.03,ints*(1+max(havoc,0)*.025)*(1+.08*max(-team_margin/14,0))); sd=max(.65,math.sqrt(proj))
    elif market_label=="Rushing Yards":
        team_rush_att=sf(team_ctx.get('team_rush_att_pg'))
        if carry_share>0 and adv_ypc>0 and team_rush_att>0:
            exp_car=team_rush_att*carry_share*rush_script*pace_adj*snap_adj
            rush_tendency=clamp(1+(early_rush-.50)*.10,.94,1.07) if early_rush>0 else 1.0
            eff=clamp(1+adv_rush_epa*.08,.92,1.08)
            proj=exp_car*adv_ypc*eff*rush_match*volume_drive*rush_tendency
            # Dual-threat QBs require a separate scramble/designed-run opportunity bump.
            if adv_att>0 and qb_rush_share>0: proj*=clamp(1+qb_rush_share*.10,1.0,1.06); notes.append("QB rushing role separated from RB workload")
            notes.append("carry share × YPC + drive opportunity")
        else: proj=rush_y*rush_script*pace_adj*snap_adj*rush_match
        sd=max(18,.34*proj)
    elif market_label=="Rush Attempts":
        proj=rush_att*rush_script*pace_adj*snap_adj; sd=max(3.5,.24*proj)
    elif market_label=="Receiving Yards":
        if target_share>0 and adv_ypt>0 and team_att>0:
            exp_targets=team_att*target_share*pass_script*pace_adj*snap_adj
            air_eff=clamp(1+(air_share-.25)*.10,.95,1.06) if air_share>0 else 1.0
            pressure_tax=clamp(1-sack_rate*.12,.95,1.0)
            eff=clamp(1+adv_rec_epa*.06,.92,1.08)
            proj=exp_targets*adv_ypt*eff*pass_match*air_eff*pressure_tax*volume_drive
            notes.append("target share × YPT + air-yard/drive opportunity")
        else: proj=rec_y*pass_script*pace_adj*snap_adj*pass_match
        sd=max(16,.36*proj)
    elif market_label=="Receptions":
        if target_share>0 and adv_catch>0 and team_att>0:
            exp_targets=team_att*target_share*pass_script*pace_adj*snap_adj
            proj=exp_targets*clamp(adv_catch,.35,.88)*clamp(.98+.02*pass_match,.90,1.08)
            notes.append("target share × catch rate advanced opportunity")
        else: proj=recs*pass_script*pace_adj*snap_adj*clamp(.98+.02*pass_match,.90,1.08)
        sd=max(1.3,.33*proj)
    elif market_label=="Pass + Rush Yards":
        py=pass_y*pass_script*pace_adj*snap_adj*pass_match; ry=rush_y*pace_adj*rush_match
        proj=py+ry; sd=max(40,.18*proj)
    elif market_label=="Rush + Rec Yards":
        proj=(rush_y*rush_script*rush_match + rec_y*pass_script*pass_match)*pace_adj*snap_adj; sd=max(20,.29*proj)
    elif market_label=="Rush + Rec TDs":
        proj=max(.02,(sf(player.get("rush_td"))+sf(player.get("rec_td")))/gp*(game.get("model_total",55)/55)*snap_adj*scoring_env); sd=max(.65,math.sqrt(proj))
    elif market_label=="Total TDs":
        proj=max(.02,(sf(player.get("pass_td"))+sf(player.get("rush_td"))+sf(player.get("rec_td")))/gp*(game.get("model_total",55)/55)*snap_adj*scoring_env); sd=max(.7,math.sqrt(proj))
    else:
        proj=0; sd=1
    # v3.0 current-role allocation: carry/target hierarchy and QB rushing are
    # applied before game-state/blowout modifiers. This uses observed opportunity,
    # never the sportsbook line, and stays bounded to avoid one-game overfitting.
    proj,sd,role_notes=role_adjust_projection(proj,sd,player,market_label)
    notes.extend(role_notes)
    # Final mean/variance adjustment comes from the dedicated game-state engine.
    # It is position/market aware: favorite QB/WR hook, RB early-volume vs late hook,
    # backup rushing opportunity, and underdog catch-up passing/targets.
    blow_mult,blow_sd,blow_notes,_ret=player_blowout_modifier(player,market_label,game,team_name,team_ctx)
    proj*=blow_mult; sd*=blow_sd; notes.extend(blow_notes)
    if proj<=0: notes.append("insufficient player sample")
    return float(max(0,proj)),float(sd),notes


def normal_cdf(x): return .5*(1+math.erf(x/math.sqrt(2)))

def prop_probability(proj,line,sd,side="Over"):
    z=(sf(proj)-sf(line))/max(sf(sd,1),.1)
    p=normal_cdf(z)
    return p if side.lower()=="over" else 1-p


def consensus_props(payload:dict)->list:
    if not isinstance(payload,dict): return []
    rows=[]
    event_id=payload.get("id"); away=payload.get("away_team"); home=payload.get("home_team")
    bucket={}
    for bm in payload.get("bookmakers",[]):
        for m in bm.get("markets",[]):
            label=ODDS_TO_LABEL.get(m.get("key"))
            if not label: continue
            for o in m.get("outcomes",[]):
                player=o.get("description") or o.get("name")
                side=o.get("name") if o.get("description") else "Over"
                line=o.get("point")
                if not player or line is None or str(side).lower() not in {"over","under"}: continue
                key=(norm_name(player),label,str(side).title())
                bucket.setdefault(key,{"player":player,"prop":label,"side":str(side).title(),"lines":[],"prices":[],"event_id":event_id,"away":away,"home":home})
                bucket[key]["lines"].append(sf(line)); bucket[key]["prices"].append(sf(o.get("price")))
    for d in bucket.values():
        d["line"]=float(np.median(d.pop("lines"))); d["price"]=float(np.median(d.pop("prices"))) if d["prices"] else None; d.pop("prices",None); rows.append(d)
    return rows


def manual_props_df(text:str)->pd.DataFrame:
    rows=[]
    for line in (text or "").splitlines():
        parts=[p.strip() for p in line.split(",")]
        if len(parts)>=4:
            rows.append({"player":parts[0],"team":parts[1],"prop":parts[2],"line":sf(parts[3]),"side":parts[4] if len(parts)>4 else "Over"})
    return pd.DataFrame(rows)


def load_optional_csv(name:str) -> pd.DataFrame:
    p=DATA_DIR/name
    if not p.exists(): return pd.DataFrame()
    try: return pd.read_csv(p)
    except Exception: return pd.DataFrame()

def player_availability(player_name:str, team:str, injuries:pd.DataFrame, depth:pd.DataFrame)->Tuple[float,List[str]]:
    factor=1.0; notes=[]; n=norm_name(player_name)
    if not injuries.empty and "player" in injuries.columns:
        h=injuries[injuries["player"].astype(str).map(norm_name)==n]
        if len(h):
            r=h.iloc[-1]; status=str(r.get("status","")).lower()
            snap=sf(r.get("expected_snap_pct"),100)/100
            if snap>0: factor*=clamp(snap,.05,1.05)
            if any(x in status for x in ["out","doubtful"]): factor*=.05; notes.append("injury/availability block")
            elif "question" in status: factor*=.88; notes.append("questionable workload tax")
            elif status: notes.append(f"availability: {status}")
    if not depth.empty and "player" in depth.columns:
        h=depth[depth["player"].astype(str).map(norm_name)==n]
        if len(h):
            order=int(sf(h.iloc[-1].get("depth_order"),1))
            if order>=3: factor*=.72; notes.append("depth-chart role tax")
            elif order==2: factor*=.88; notes.append("No. 2 depth role")
    return clamp(factor,.02,1.08),notes

def game_weather_context(away:str,home:str,manual:pd.DataFrame)->dict:
    if manual.empty:return {}
    cols=set(manual.columns)
    if not {"away","home"}.issubset(cols):return {}
    hit=manual[(manual["away"].astype(str).map(norm_name)==norm_name(away))&(manual["home"].astype(str).map(norm_name)==norm_name(home))]
    return hit.iloc[-1].to_dict() if len(hit) else {}

def grade_rows(saved:list, results_df:pd.DataFrame)->list:
    if results_df is None or results_df.empty:return []
    out=[]
    for r in saved:
        hit=results_df[(results_df["player"].astype(str).map(norm_name)==norm_name(r.get("player"))) & (results_df["prop"].astype(str)==r.get("prop"))]
        if hit.empty: continue
        actual=sf(hit.iloc[0]["actual"]); line=sf(r.get("line")); side=r.get("side","Over")
        result="PUSH" if abs(actual-line)<1e-9 else ("WIN" if (actual>line if side=="Over" else actual<line) else "LOSS")
        q=dict(r); q.update({"actual":actual,"result":result}); out.append(q)
    return out


def load_bundle(cfbd:CFBD,year:int,week:int,force=False)->dict:
    calls={
        "games":("/games",{"year":year},1800),
        "core":("/ratings/core",{"year":year},21600),
        "sp":("/ratings/sp",{"year":year},21600),
        "srs":("/ratings/srs",{"year":year},21600),
        "elo":("/ratings/elo",{"year":year,"week":week},21600),
        "teams":("/teams/fbs",{"year":year},86400),
        "rankings":("/rankings",{"year":year,"week":week},21600),
        "talent":("/talent",{"year":year},86400),
        "player_stats":("/stats/player/season",{"year":year,"startWeek":1,"endWeek":week},3600),
        "advanced":("/stats/season/advanced",{"year":year,"startWeek":1,"endWeek":week,"excludeGarbageTime":True},21600),
    }
    out={}; errors={}
    for k,(ep,params,ttl) in calls.items():
        try: out[k]=cfbd.get(ep,params,ttl=ttl,force=force)
        except Exception as e: out[k]=[]; errors[k]=str(e)
    out["errors"]=errors
    return out


def render_game_card(g:dict):
    spread_edge=None if g.get("market_home_spread") is None else g["model_home_margin"] + sf(g["market_home_spread"])
    total_edge=None if g.get("market_total") is None else g["model_total"]-sf(g["market_total"])
    tags=" ".join(f"<span class='tag'>{x}</span>" for x in g.get("tags",[]))
    st.markdown(f"""
    <div class='card'>
      <div class='small'>{g.get('away_ap') and '#'+str(g.get('away_ap'))+' ' or ''}{g['away']} @ {g.get('home_ap') and '#'+str(g.get('home_ap'))+' ' or ''}{g['home']}</div>
      <div class='metricbig'>{g['away']} {g['away_points']:.1f} — {g['home_points']:.1f} {g['home']}</div>
      <div class='small'>Model ranks: {g.get('away_model_rank','—')} / {g.get('home_model_rank','—')} · Home win <b>{g['home_win_prob']*100:.1f}%</b> · Model spread <b>{-g['model_home_margin']:+.1f}</b> · Total <b>{g['model_total']:.1f}</b></div>
      <div class='small'>Market spread: {g.get('market_home_spread','—')} · spread edge: {'—' if spread_edge is None else f'{spread_edge:+.1f}'} · market total: {g.get('market_total','—')} · total edge: {'—' if total_edge is None else f'{total_edge:+.1f}'}</div>
      <div>{tags}</div>
    </div>
    """,unsafe_allow_html=True)



def render_player_card(r:dict, ctx:dict, game:dict):
    team=str(r.get("team") or ""); opp=str(r.get("opp") or "")
    tc=get_team(ctx,team); oc=get_team(ctx,opp)
    logo=tc.get("logo") or ""; color=tc.get("color") or "#2f81f7"
    status=str(r.get("status") or "TRACK"); status_cls="playable" if status=="PLAYABLE" else "lean" if status=="LEAN" else "track"
    prob=sf(r.get("probability"))*100; proj=sf(r.get("projection")); line=sf(r.get("line")); edge=sf(r.get("edge")); side=str(r.get("side") or "Over")
    notes=str(r.get("notes") or "No extra flags"); ap=oc.get("ap_rank") or "—"; modelrk=oc.get("model_rank") or "—"
    passd=oc.get("def_passing"); rushd=oc.get("def_rushing"); expld=oc.get("def_expl"); blow=sf(game.get("blowout_prob"))*100
    logo_html=f"<img class='cfb-team-logo' src='{logo}'/>" if logo else "<div class='cfb-team-logo'></div>"
    edge_cls="good" if edge>=0 else "bad"
    st.markdown(f"""
    <div class='cfb-player-card' style='--team:{color}'>
      <div class='cfb-card-top'>{logo_html}<div><div class='cfb-player-name'>{r.get('player','')}</div><div class='cfb-player-sub'>{team} · vs {opp} · AP #{ap} / Model #{modelrk}</div></div><div class='cfb-status {status_cls}'>{status}</div></div>
      <div class='cfb-prop-title'>{side} {line:g} · {r.get('prop','')}</div>
      <div class='cfb-proj-row'><div class='cfb-box main'><div class='lab'>Projection</div><div class='val'>{proj:.1f}</div></div><div class='cfb-box'><div class='lab'>{side} Prob</div><div class='val cfb-prob'>{prob:.1f}%</div></div><div class='cfb-box'><div class='lab'>Edge</div><div class='val cfb-edge {edge_cls}'>{edge:+.1f}</div></div><div class='cfb-box'><div class='lab'>Model SD</div><div class='val'>{sf(r.get('sd')):.1f}</div></div></div>
      <div class='cfb-match-grid'><div class='cfb-mini'><div class='lab'>Opp Pass D</div><div class='val'>{'—' if passd is None else f'{sf(passd):.1f}'}</div></div><div class='cfb-mini'><div class='lab'>Opp Rush D</div><div class='val'>{'—' if rushd is None else f'{sf(rushd):.1f}'}</div></div><div class='cfb-mini'><div class='lab'>Explosive D</div><div class='val'>{'—' if expld is None else f'{sf(expld):.1f}'}</div></div><div class='cfb-mini'><div class='lab'>Blowout Risk</div><div class='val'>{blow:.0f}%</div></div></div>
      <div class='cfb-game-strip'>Game model: {game.get('away')} {sf(game.get('away_points')):.1f} — {sf(game.get('home_points')):.1f} {game.get('home')} · Total {sf(game.get('model_total')):.1f}</div>
      <div class='cfb-why'>WHY: {notes}</div>
    </div>""", unsafe_allow_html=True)

# --------------------------- APP ---------------------------
now=datetime.now()
def_week=max(1,min(16,int((now.timetuple().tm_yday-239)/7)+1))
year=st.sidebar.number_input("Season",2020,2030,now.year,1)
week=st.sidebar.number_input("Week",1,20,def_week,1)
cfbd=CFBD(secret("CFBD_API_KEY")); odds=OddsAPI(secret("ODDS_API_KEY"))
propline_key=secret("PROPLINE_API_KEY")

st.markdown(f"""<div class='hero'><h1>🏈 CFB Prop Engine</h1><p>Opponent-adjusted college football projections · rankings ≠ matchup quality · blowout/playing-time engine · player opportunity · moneyline/spread/total · live market audit</p><span class='badge'>{APP_VERSION}</span><span class='badge'>FREE SportsDataverse + NCAA + LIVE Underdog CFB lines</span></div>""",unsafe_allow_html=True)

with st.sidebar:
    st.header("CFB Controls")
    st.write("Free CFB data", "✅ SportsDataverse + NCAA")
    st.write("CFBD paid API", "✅ optional" if cfbd.ready else "⚪ not needed")
    st.write("Player lines", "✅ Auto: Underdog → PropLine" if propline_key else ("✅ Underdog Live (free)" if not odds.ready else "✅ Underdog Live + optional Odds API"))
    st.write("PropLine", "✅ connected fallback" if propline_key else "⚪ add PROPLINE_API_KEY")
    force=st.button("🔄 Refresh CFB Data",width="stretch",type="primary")
    st.caption("No paid key is required. SportsDataverse supplies schedules/player/team/advanced/FPI data; NCAA supplies ranking fallback. Paid APIs remain optional only.")

with st.spinner("Loading FREE CFB data…"):
    if cfbd.ready:
        bundle=load_bundle(cfbd,int(year),int(week),force=force)
        ctx=build_team_context(bundle)
        gp=team_games_played(bundle.get("games",[]),int(week))
        players=parse_player_stats(bundle.get("player_stats",[]),gp)
        try: game_odds=odds.game_odds(force=force) if odds.ready else []
        except Exception as e: game_odds=[]; bundle.setdefault("errors",{})["odds"]=str(e)
        market_map=implied_market(game_odds)
        data_mode="CFBD API"
    else:
        bundle,ctx,players,market_map=load_free_stack(int(year),int(week))
        data_mode="FREE SportsDataverse/NCAA"
    # v2.5: enrich both free and optional-CFBD modes with the same no-key CFB
    # drive/opportunity context. This layer never uses the sportsbook line to set a projection.
    ctx,players,opportunity_health=enrich_opportunity(int(year),int(bundle.get("resolved_week",week) if isinstance(bundle,dict) else week),ctx,players)
    players=enrich_role_depth(players)
    # v2.6 derives coach/rotation behavior from prior-season 21+ point games.
    # It measures starter concentration rather than inventing a universal substitution rule.
    ctx,blowout_health=enrich_blowout_context(int(year),ctx)
    if isinstance(bundle,dict):
        bundle.setdefault("free_health",{}).update({f"v25_{k}":v for k,v in opportunity_health.items()})
        bundle.setdefault("free_health",{}).update({f"v26_{k}":v for k,v in blowout_health.items()})
# v3.1 PropLine game-line backup. One cached bulk request fills missing spread/total
# context without replacing the existing free betting source.
if propline_key:
    try:
        pl_game_map,pl_game_debug=fetch_propline_game_markets(propline_key)
        for k,rec in pl_game_map.items():
            cur=market_map.setdefault(k,{})
            for fld in ("event_id","away","home","market_home_spread","market_total"):
                if cur.get(fld) in (None,"") and rec.get(fld) not in (None,""):
                    cur[fld]=rec.get(fld)
        if isinstance(bundle,dict): bundle["propline_game_debug"]=pl_game_debug
    except Exception as e:
        if isinstance(bundle,dict): bundle["propline_game_debug"]={"status":"ERROR","error":str(e)}
ctx=hydrate_team_branding(ctx)
ctx=ensure_branding(ctx,bundle.get("games",[]),players)
inject_nfl_cfb_css()
active_week=int(bundle.get("resolved_week",week)) if isinstance(bundle,dict) else int(week)
if active_week!=int(week):
    st.sidebar.info(f"Live source currently labels this slate as Week {active_week}; using that automatically.")
injuries_df=load_optional_csv("injuries.csv")
depth_df=load_optional_csv("depth_chart.csv")
game_context_df=load_optional_csv("game_context.csv")

# Current week games
week_games=[]
for g in bundle.get("games",[]):
    if int(sf(g.get("week"),0))!=int(active_week): continue
    away=g.get("away_team") or g.get("awayTeam"); home=g.get("home_team") or g.get("homeTeam")
    if not away or not home: continue
    market=market_map.get((norm_name(away),norm_name(home)),{})
    manual_gc=game_weather_context(away,home,game_context_df)
    pg=project_game(away,home,ctx,market,neutral=bool(g.get("neutral_site") or g.get("neutralSite") or manual_gc.get("neutral",False)))
    wind=sf(manual_gc.get("wind_mph")); precip=sf(manual_gc.get("precip_prob")); temp=sf(manual_gc.get("temp_f"),70)
    if wind>=18:
        pg["model_total"]-=2.0; pg["home_points"]-=1.0; pg["away_points"]-=1.0; pg["tags"].append("🌬️ HIGH WIND")
    if precip>=65:
        pg["model_total"]-=1.0; pg["home_points"]-=.5; pg["away_points"]-=.5; pg["tags"].append("🌧️ WEATHER RISK")
    auto_w=automatic_weather(g) if not (wind or precip or (manual_gc.get("temp_f") not in (None,""))) else {}
    pg["weather"]={"wind_mph":sf(auto_w.get("wind_mph"),wind),"precip_prob":sf(auto_w.get("precip_prob"),precip),"temp_f":sf(auto_w.get("temp_f"),temp),"source":auto_w.get("source") or ("manual" if manual_gc else "")}
    pg["game_id"]=g.get("id"); pg["start_date"]=g.get("start_date") or g.get("startDate")
    pg["away_abbreviation"]=g.get("away_abbreviation") or g.get("awayAbbreviation") or ""
    pg["home_abbreviation"]=g.get("home_abbreviation") or g.get("homeAbbreviation") or ""
    week_games.append(pg)

week_games=annotate_games(week_games)
pt_now=local_now()
slate_scope=st.radio("Slate",["Today","Tomorrow","All Week"],horizontal=True,index=0,label_visibility="collapsed",key="cfb_slate_scope")
target_date=scope_target_date(slate_scope,pt_now)
display_games=filter_games_by_scope(week_games,slate_scope,pt_now)
# SportsDataverse may lag the next calendar day even while Underdog has lines open.
# Pull the exact ESPN date and project any missing games into the same board.
if slate_scope in {"Today","Tomorrow"}:
    raw_day=day_games(slate_scope,bundle.get("games",[]),pt_now)
    have={(norm_name(g.get("away")),norm_name(g.get("home"))) for g in week_games}
    for rg in raw_day:
        away=rg.get("away_team") or rg.get("awayTeam"); home=rg.get("home_team") or rg.get("homeTeam")
        key=(norm_name(away),norm_name(home))
        if not away or not home or key in have:continue
        market=market_map.get(key,{})
        manual_gc=game_weather_context(away,home,game_context_df)
        pg=project_game(away,home,ctx,market,neutral=bool(rg.get("neutral_site") or rg.get("neutralSite") or manual_gc.get("neutral",False)))
        pg["weather"]={"wind_mph":sf(manual_gc.get("wind_mph")),"precip_prob":sf(manual_gc.get("precip_prob")),"temp_f":sf(manual_gc.get("temp_f"),70)}
        pg["game_id"]=rg.get("id");pg["start_date"]=rg.get("start_date") or rg.get("startDate")
        pg["away_abbreviation"]=rg.get("away_abbreviation") or "";pg["home_abbreviation"]=rg.get("home_abbreviation") or ""
        pg["away_espn_id"]=rg.get("away_espn_id") or "";pg["home_espn_id"]=rg.get("home_espn_id") or ""
        pg["away_logo"]=rg.get("away_logo") or "";pg["home_logo"]=rg.get("home_logo") or ""
        week_games.append(pg);have.add(key)
    week_games=annotate_games(week_games)
    display_games=filter_games_by_scope(week_games,slate_scope,pt_now)
# Final NFL-style fallback: if the official/free schedule is behind but the live book
# has tomorrow's CFB board open, build the event slate from those live event records.
if slate_scope in {"Today","Tomorrow"} and not display_games:
    try:
        boot_rows,boot_debug=fetch_underdog_cfb_props(force=force)
        st.session_state["ud_cfb_rows"]=boot_rows
        st.session_state["ud_cfb_debug"]=boot_debug
        scoped_boot=filter_props_by_scope(boot_rows,slate_scope,pt_now)
        raw_prop_games=games_from_props(scoped_boot,ctx)
        for rg in raw_prop_games:
            away=rg.get("away_team");home=rg.get("home_team")
            if not away or not home:continue
            key=(norm_name(away),norm_name(home));market=market_map.get(key,{})
            manual_gc=game_weather_context(away,home,game_context_df)
            pg=project_game(away,home,ctx,market,neutral=bool(manual_gc.get("neutral",False)))
            pg["weather"]={"wind_mph":sf(manual_gc.get("wind_mph")),"precip_prob":sf(manual_gc.get("precip_prob")),"temp_f":sf(manual_gc.get("temp_f"),70)}
            pg["game_id"]=rg.get("id");pg["start_date"]=rg.get("start_date")
            for k in ["away_abbreviation","home_abbreviation","away_espn_id","home_espn_id","away_logo","home_logo"]:pg[k]=rg.get(k) or ""
            week_games.append(pg)
        week_games=annotate_games(week_games)
        display_games=filter_games_by_scope(week_games,slate_scope,pt_now)
    except Exception as e:
        bundle.setdefault("errors",{})["live_slate_bootstrap"]=str(e)
ctx=ensure_branding(ctx,week_games,players)
slate_label=(target_date.strftime("%A, %B %-d") if target_date else f"Week {active_week}")
st.markdown(f"<div class='cfb-live-strip'><b>{slate_scope}</b> · {slate_label} · {len(display_games)} games · {pt_now.strftime('%-I:%M %p PT')}</div>",unsafe_allow_html=True)

TAB_EVENTS,TAB_PLAYERS,TAB_RANK,TAB_DATA,TAB_GRADE=st.tabs(["🏟️ Games","⚡ Player Props","Power","Data","Grade"])

with TAB_EVENTS:
    st.subheader("Moneyline · Spread · Total")
    st.caption("NFL-style CFB game board · local-day slate · model winner · spread · total")
    if not display_games:
        st.info(f"No games on {slate_label}. Switch to Tomorrow or All Week.")
    else:
        for g in sorted(display_games,key=lambda x:x.get("start_date") or ""):
            render_moneyline_nfl(g,ctx)

with TAB_RANK:
    st.subheader("AP Rank vs Model Rank")
    st.caption("This is the Ohio State-type check: a team can be highly ranked overall while still being vulnerable specifically to the pass or run.")
    rows=[]
    for t,d in ctx.items():
        rows.append({"Team":t,"AP":d.get("ap_rank"),"Model Rank":d.get("model_rank"),"SP+":d.get("sp"),"CORE":d.get("core"),"SRS":d.get("srs"),"Elo":d.get("elo"),"Pass D":d.get("def_passing"),"Rush D":d.get("def_rushing"),"Explosive D":d.get("def_expl"),"Havoc":d.get("havoc")})
    if rows:
        rdf=pd.DataFrame(rows).sort_values("Model Rank")
        st.dataframe(rdf,width="stretch",hide_index=True)
    else: st.info("Power board populates after the free CFB data stack loads.")

with TAB_PLAYERS:
    st.subheader("Player Props")
    st.caption("Live CFB lines → matchup + usage → projection → Higher/Lower probability")
    game_labels=["ALL LIVE CFB PROPS"]+[f"{g['away']} @ {g['home']}" for g in display_games]
    selected_label=st.selectbox("Game / board",game_labels,index=0)
    selected_game=None if selected_label=="ALL LIVE CFB PROPS" else display_games[[f"{g['away']} @ {g['home']}" for g in display_games].index(selected_label)]
    live_sources=(["Auto Lines","Underdog Live","PropLine Live"] if propline_key else ["Underdog Live"]) + (["Live Odds API"] if odds.ready else []) + ["Manual"]
    source=st.radio("Prop lines",live_sources,horizontal=True)
    prop_rows=[]
    if source in {"Auto Lines","Underdog Live"}:
        c1,c2=st.columns([1,2])
        with c1:
            ud_refresh=st.button("🔄 Refresh Underdog CFB",type="primary",width="stretch")
        try:
            if ud_refresh or "ud_cfb_rows" not in st.session_state:
                ud_rows,ud_debug=fetch_underdog_cfb_props(force=ud_refresh)
                st.session_state["ud_cfb_rows"]=ud_rows
                st.session_state["ud_cfb_debug"]=ud_debug
            ud_rows=st.session_state.get("ud_cfb_rows",[])
            ud_rows=filter_props_by_scope(ud_rows,slate_scope,pt_now)
            if source=="Auto Lines" and propline_key:
                td=target_date.isoformat() if target_date else None
                pl_rows,pl_debug=fetch_propline_cfb_props(propline_key,target_date=td)
                st.session_state["propline_cfb_rows"]=pl_rows
                st.session_state["propline_cfb_debug"]=pl_debug
                ud_rows=merge_line_feeds(ud_rows,pl_rows)
            ctx=ensure_branding(ctx,week_games,players,ud_rows)
            prop_rows=list(ud_rows) if selected_game is None else props_for_game(ud_rows,selected_game["away"],selected_game["home"])
            # Some Underdog CFB rows carry a school abbreviation while the free
            # schedule uses the full school name. Player lookup below canonicalizes
            # the team; do not discard those live lines just because the names differ.
            if not prop_rows and selected_game is not None:
                game_players=set()
                if players is not None and not players.empty and "team" in players.columns:
                    for tm in [selected_game["away"],selected_game["home"]]:
                        hit=players[players["team"].astype(str).map(norm_name)==norm_name(tm)]
                        game_players.update(hit["player"].astype(str).map(norm_name).tolist())
                if game_players:
                    prop_rows=[r for r in ud_rows if norm_name(r.get("player")) in game_players]
            markets=sorted({str(r.get("prop")) for r in prop_rows if r.get("prop")})
            if markets:
                preferred=[x for x in ["Passing Yards","Receiving Yards","Rushing Yards","Rush + Rec TDs"] if x in markets]
                chosen=st.multiselect("Prop market",markets,default=(preferred[:1] if preferred else markets[:1]))
                prop_rows=[r for r in prop_rows if r.get("prop") in chosen]
            with c2:
                scope="all live CFB props" if selected_game is None else "matching this game"
                st.markdown(f"<div class='cfb-live-strip'><b>LIVE BOARD CONNECTED</b> · {len(ud_rows)} CFB lines pulled · {len(prop_rows)} {scope}</div>",unsafe_allow_html=True)
            if prop_rows:
                rawdf=pd.DataFrame(prop_rows)
                rawcols=[c for c in ["player","team","matchup","prop","line","source","books","line_type","non_discounted_line","line_status","scheduled_at"] if c in rawdf.columns]
                with st.expander("📡 Live player lines",expanded=True):
                    st.dataframe(rawdf[rawcols].head(150),width="stretch",hide_index=True)
            if not prop_rows:
                st.info("Underdog did not return a matching player line for this selected game yet. Refresh when the CFB board opens/updates.")
                with st.expander("Underdog feed diagnostics"):
                    st.json(st.session_state.get("ud_cfb_debug",[]))
        except Exception as e:
            st.error(f"Underdog CFB pull failed: {e}")
    elif source=="PropLine Live":
        try:
            td=target_date.isoformat() if target_date else None
            pl_rows,pl_debug=fetch_propline_cfb_props(propline_key,target_date=td)
            st.session_state["propline_cfb_rows"]=pl_rows
            st.session_state["propline_cfb_debug"]=pl_debug
            ctx=ensure_branding(ctx,week_games,players,pl_rows)
            prop_rows=list(pl_rows) if selected_game is None else props_for_game(pl_rows,selected_game["away"],selected_game["home"])
            markets=sorted({str(r.get("prop")) for r in prop_rows if r.get("prop")})
            if markets:
                preferred=[x for x in ["Passing Yards","Receiving Yards","Rushing Yards","Passing TDs"] if x in markets]
                chosen=st.multiselect("Prop market",markets,default=(preferred[:1] if preferred else markets[:1]),key="propline_markets")
                prop_rows=[r for r in prop_rows if r.get("prop") in chosen]
            st.markdown(f"<div class='cfb-live-strip'><b>PROPLINE CONNECTED</b> · {len(pl_rows)} standard CFB lines · quota remaining {pl_debug.get('quota',{}).get('X-Daily-Remaining','—')}</div>",unsafe_allow_html=True)
            if prop_rows:
                rawdf=pd.DataFrame(prop_rows)
                rawcols=[c for c in ["player","team","matchup","prop","line","source","books","line_status","scheduled_at"] if c in rawdf.columns]
                with st.expander("📡 PropLine player lines",expanded=True): st.dataframe(rawdf[rawcols].head(150),width="stretch",hide_index=True)
            else:
                st.info("PropLine has no matching standard player lines for this slate yet.")
                with st.expander("PropLine diagnostics"): st.json(pl_debug)
        except Exception as e:
            st.error(f"PropLine CFB pull failed: {e}")
    elif selected_game and source=="Live Odds API":
        if not odds.ready: st.info("Add ODDS_API_KEY or switch to Underdog Live/Manual.")
        else:
            event=market_map.get((norm_name(selected_game["away"]),norm_name(selected_game["home"])),{})
            event_id=event.get("event_id")
            chosen=st.multiselect("Markets",list(PLAYER_MARKETS),default=["Passing Yards","Rushing Yards","Receiving Yards"])
            if st.button("Pull selected player props",type="primary"):
                try:
                    payload=odds.event_props(event_id,[PLAYER_MARKETS[x] for x in chosen],force=True)
                    st.session_state["cfb_props"] = consensus_props(payload)
                except Exception as e: st.error(str(e))
            prop_rows=st.session_state.get("cfb_props",[])
            prop_rows=[r for r in prop_rows if norm_name(r.get("away"))==norm_name(selected_game["away"]) and norm_name(r.get("home"))==norm_name(selected_game["home"])]
    elif selected_game:
        default_text="Player Name,Team,Passing Yards,275.5,Over\nPlayer Name,Team,Receiving Yards,69.5,Over"
        txt=st.text_area("One prop per line: player,team,prop,line,side",value=default_text,height=110)
        prop_rows=manual_props_df(txt).to_dict("records")

    projected=[]
    if prop_rows:
        for r in prop_rows:
            pr=lookup_player(players,r.get("player",""))
            pr_team=str(pr.get("team") or "")
            row_game=selected_game
            if row_game is None:
                # v2.7 LIVE-GAME LOCK: the sportsbook event is authoritative for the
                # matchup. Never let a player's prior school select today's game.
                # This fixes transfers such as a current Louisville player carrying
                # an Ohio State production sample into an Ohio State game card.
                ra,rh=norm_name(r.get("away")),norm_name(r.get("home"))
                if ra and rh:
                    for gg in week_games:
                        ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))
                        full_match=((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or
                                    (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"])))
                        abbr_match=(ga==ra and gh==rh)
                        if full_match or abbr_match:
                            row_game=gg; break
                # Only use historical player-team matching when the live feed truly
                # lacks an event matchup. It is a last-resort fallback, not authority.
                if row_game is None and not (ra and rh) and pr_team:
                    for gg in week_games:
                        if norm_name(pr_team) in {norm_name(gg["away"]),norm_name(gg["home"])}:
                            row_game=gg; break
                if row_game is None:
                    away=r.get("away") or "Away"; home=r.get("home") or "Home"
                    row_game=project_game(away,home,ctx,{},neutral=True)
                    row_game["weather"]={}
                    row_game["live_event_fallback"]=True
            # Authoritative current team comes from Underdog player team_id matched
            # to this game's away_team_id/home_team_id. Historical school stays only
            # as provenance for the player's production sample.
            live_team=str(r.get('team') or '')
            team=canonical_prop_team({**r,'team':live_team},row_game,pr)
            if team not in {row_game['away'],row_game['home']}:
                team=''
                for t in [row_game['away'],row_game['home']]:
                    a,b=norm_name(live_team),norm_name(t)
                    if a and (a==b or a in b or b in a): team=t; break
            opp=row_game["home"] if team==row_game["away"] else row_game["away"]
            tc=get_team(ctx,team or ""); oc=get_team(ctx,opp or "")
            model_pr=dict(pr)
            if team: model_pr['current_team']=team
            proj,sd,notes=player_projection(model_pr,r.get("prop"),tc,oc,row_game,team or "")
            avail,avail_notes=player_availability(r.get("player",""),team or "",injuries_df,depth_df)
            proj*=avail; sd=max(sd*.92, sd*math.sqrt(max(avail,.25))); notes.extend(avail_notes)
            weather=row_game.get("weather",{}) or {}; wind=sf(weather.get("wind_mph")); precip=sf(weather.get("precip_prob"))
            if r.get("prop") in {"Passing Yards","Pass Attempts","Completions","Receiving Yards","Receptions","Pass + Rush Yards"}:
                wfactor=1.0-clamp(max(wind-15,0)*.006 + max(precip-60,0)*.0015,0,.16)
                if wfactor<.995: proj*=wfactor; notes.append("weather passing tax")
            side=str(r.get("side") or "Over")
            if side.upper()=="AUTO":
                side="Over" if proj>=sf(r.get("line")) else "Under"
                notes.append("side selected from model vs live Underdog line")
            # v2.7 fixes two live-slate failure modes from Sep. 6:
            # 1) confirmed QB1 projections collapsing from stale backup history; and
            # 2) gigantic WR/RB edges receiving automatic max confidence without
            #    current opportunity evidence. Neither correction uses the prop line
            #    to manufacture a projection.
            proj,sd,qproj_notes=stabilize_projection(proj,sd,model_pr,r.get("prop"),tc,row_game)
            notes.extend(qproj_notes)
            raw_p=prop_probability(proj,r.get("line"),sd,side)
            p,pcap,qprob_notes,quality_tier=calibrate_probability(raw_p,model_pr,r.get("prop"),tc,row_game,proj,r.get("line"))
            notes.extend(qprob_notes)
            edge=proj-sf(r.get("line")); edge = edge if side=="Over" else -edge
            status=status_from_quality(p,proj,quality_tier,r.get("prop"),model_pr)
            integrity_tier,integrity_score,integrity_flags=integrity_audit(r,model_pr,team,opp,row_game,tc,r.get("prop"))
            status=enforce_integrity_status(status,p,quality_tier,integrity_tier,integrity_flags)
            if integrity_flags:
                notes.append('integrity: '+', '.join(integrity_flags))
            notes.append(f'data integrity {integrity_tier.lower()}')
            src=str(model_pr.get("sample_source") or "fallback").lower(); gp=sf(model_pr.get("games"),0)
            roster_confirmed=bool(model_pr.get('current_team')) or src=='current'
            transferred=bool(model_pr.get('current_team') and model_pr.get('team') and norm_name(model_pr.get('current_team'))!=norm_name(model_pr.get('team')))
            has_adv=any(sf(model_pr.get(k))>0 for k in ['adv_pass_att','adv_rush_car','adv_targets'])
            if transferred: notes.append('transfer/current-role uncertainty')
            if roster_confirmed: notes.append('current roster confirmed')
            if has_adv: notes.append('2026 advanced usage available')
            notes.append(f'projection quality {quality_tier.lower()}')
            _bm,_bsd,_bn,starter_retention=player_blowout_modifier(model_pr,r.get("prop"),row_game,team or "",tc)
            q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(dict.fromkeys(notes)),
               "blowout_level":row_game.get("blowout_level","LOW"),"blowout_prob":row_game.get("blowout_prob",0),"starter_retention":starter_retention,"backup_opportunity":row_game.get("backup_opportunity",0),
               "quality_tier":quality_tier,"probability_cap":pcap,"live_game_locked":bool(r.get("away") and r.get("home")),
               "integrity_tier":integrity_tier,"integrity_score":integrity_score,"integrity_flags":" | ".join(integrity_flags)}
            projected.append(q)
        pdf=pd.DataFrame(projected)
        show=["player","team","prop","side","line","projection","edge","probability","status","quality_tier","integrity_tier","integrity_flags","notes"]
        if not pdf.empty:
            ranked=sorted(projected,key=lambda x:sf(x.get("probability")),reverse=True)
            good_ranked=[x for x in ranked if sf(x.get("projection"))>0]
            render_rows=(good_ranked or ranked)[:30]
            if len(ranked)>30:
                st.caption(f"Showing the top {len(render_rows)} model cards for speed · all {len(ranked)} rows remain in the compact table below.")
            FAST_TAB,CARD_TAB=st.tabs(["⚡ Fast Row","🪪 Player Cards"])
            with FAST_TAB:
                render_fast_rows(render_rows,ctx,limit=60)
            with CARD_TAB:
                cols=st.columns(2)
                for i,rr in enumerate(render_rows):
                    with cols[i%2]: render_player_nfl(rr,ctx,rr.get("_game") or row_game,rank=i+1)
            with st.expander("📋 Compact projection table",expanded=False):
                pdf["probability"]=(pdf["probability"]*100).round(1)
                for c in ["line","projection","edge"]: pdf[c]=pd.to_numeric(pdf[c],errors="coerce").round(2)
                st.dataframe(pdf[show].sort_values("probability",ascending=False),width="stretch",hide_index=True)
            if st.button("Save this projected board"):
                path=DATA_DIR/"saved_prop_board.json"
                path.write_text(json.dumps([{k:v for k,v in x.items() if k!="_game"} for x in projected],indent=2,default=str)); st.success(f"Saved {len(projected)} props for grading.")
        matched=sum(1 for r in projected if sf(r.get("projection"))>0)
        st.caption(f"Model joined {matched}/{len(projected)} selected live lines to usable player production.")
        missing=[r.get("player") for r in projected if r.get("projection",0)<=0]
        if missing: st.warning("Live line loaded but no usable projection sample for: "+", ".join(map(str,missing[:12])))

with TAB_DATA:
    st.subheader("Data Readiness")
    brand_health=logo_coverage(ctx,week_games)
    st.success(f"Active source: {data_mode} · Active Week: {active_week} · Games: {len(week_games)} · Players: {len(players) if players is not None else 0} · Team logos: {brand_health['logos']}/{brand_health['teams']}")
    if brand_health.get("missing"):
        st.caption("Missing logo aliases: "+", ".join(brand_health["missing"][:12]))
    checks=[]
    if str(data_mode).startswith('FREE'):
        fh=bundle.get('free_health',{}) or {}
        # Show the real no-key datasets actually feeding the model. The legacy
        # CFBD-shaped bundle intentionally keeps several placeholder lists empty,
        # which previously made healthy free data look like Rows=0.
        free_layers=[
            ('schedule/results',fh.get('schedules',len(bundle.get('games',[]))),'game schedule/results'),
            ('team context',len(ctx),'team identity + derived matchup context'),
            ('player production',len(players) if players is not None else 0,'QB/RB/WR current + prior + roster bank'),
            ('advanced passing',fh.get('adv_passing',0),'QB usage/efficiency'),
            ('advanced rushing',fh.get('adv_rushing',0),'carry share/efficiency'),
            ('advanced receiving',fh.get('adv_receiving',0),'targets/air yards/efficiency'),
            ('situational',fh.get('adv_situational',0),'down/distance/red-zone context'),
            ('team box',fh.get('team_box',0),'plays/turnovers/possession/efficiency'),
            ('game rosters',fh.get('game_rosters',0),'starter/current-game role'),
            ('current rosters',fh.get('rosters',0),'current-team identity'),
            ('power index',fh.get('power_index',0),'team strength/rating context'),
            ('betting',fh.get('betting',0),'spread + total context'),
            ('drives',fh.get('v25_drives',fh.get('drives',0)),'drive/pace/scoring opportunity'),
        ]
        for name,rows,role in free_layers:
            checks.append({'Layer':name,'Rows':int(rows or 0),'Ready':bool(rows),'Role':role})
    else:
        for k in ["games","teams","sp","core","srs","elo","rankings","talent","player_stats","advanced"]:
            v=bundle.get(k,[]); checks.append({"Layer":k,"Rows":len(v) if isinstance(v,list) else 0,"Ready":bool(v),"Role":{
                "games":"schedule/results/game counts","teams":"FBS identity/logos/colors/conference","sp":"offense/defense/pass/rush/explosive/havoc/pace","core":"opponent-relative team efficiency","srs":"schedule-adjusted power","elo":"team strength","rankings":"AP/CFP context","talent":"roster talent gap/blowout context","player_stats":"QB/RB/WR season production/usage","advanced":"advanced efficiency context"}[k]})
    st.dataframe(pd.DataFrame(checks),width="stretch",hide_index=True)
    st.markdown("**Game-week context adapters**")
    st.dataframe(pd.DataFrame([
        {"Layer":"injuries.csv","Rows":len(injuries_df),"Use":"status + expected snap % workload gate"},
        {"Layer":"depth_chart.csv","Rows":len(depth_df),"Use":"starter/backup role adjustment"},
        {"Layer":"game_context.csv","Rows":len(game_context_df),"Use":"wind/rain/neutral-site weather context"},
    ]),width="stretch",hide_index=True)
    if bundle.get("free_health"):
        st.markdown("**Free-source rows loaded**")
        st.dataframe(pd.DataFrame([{"Dataset":k,"Rows":v,"Ready":v>0} for k,v in bundle["free_health"].items()]),width="stretch",hide_index=True)
    if bundle.get("errors"):
        st.warning("Some sources did not load. The rest of the app stays live and reports missing layers instead of inventing data.")
        st.json(bundle["errors"])
    st.markdown("**Current architecture**")
    st.code("SportsDataverse/NCAA + current rosters + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog event lock → opportunity/hook/pressure/explosive engine → QB volume floor + role-quality calibration → data-integrity gate → Higher/Lower probability + edge → market-by-market grading + miss audit",language="text")
    st.caption("Injuries/depth charts are intentionally a separate adapter layer. CFB availability reporting is inconsistent, so the app does not pretend missing injury data means healthy.")

with TAB_GRADE:
    st.subheader("Save + Grade")
    saved_path=DATA_DIR/"saved_prop_board.json"; hist_path=DATA_DIR/"graded_history.csv"
    saved=json.loads(saved_path.read_text()) if saved_path.exists() else []
    st.write(f"Saved props: **{len(saved)}**")
    template="player,prop,actual\nPlayer Name,Passing Yards,302\nPlayer Name,Receiving Yards,88\n"
    st.download_button("Download results template",template,"cfb_results_template.csv","text/csv")
    up=st.file_uploader("Upload results CSV",type=["csv"])
    if up is not None and saved:
        rdf=pd.read_csv(up)
        if set(["player","prop","actual"]).issubset(rdf.columns):
            graded=grade_rows(saved,rdf)
            if graded:
                gdf=pd.DataFrame(graded)
                wins=(gdf.result=="WIN").sum(); losses=(gdf.result=="LOSS").sum(); pushes=(gdf.result=="PUSH").sum()
                st.metric("Record",f"{wins}-{losses}"+(f"-{pushes}" if pushes else ""))
                st.dataframe(gdf[[c for c in ["player","prop","side","line","projection","probability","status","quality_tier","integrity_tier","actual","result"] if c in gdf.columns]],width="stretch",hide_index=True)
                st.markdown("**Market performance**")
                ms=market_grade_summary(gdf)
                if not ms.empty: st.dataframe(ms,width="stretch",hide_index=True)
                cga,cgb,cgc=st.columns(3)
                with cga:
                    st.markdown("**By status**"); ss=segment_grade_summary(gdf,'status')
                    if not ss.empty: st.dataframe(ss,width="stretch",hide_index=True)
                with cgb:
                    st.markdown("**By projection quality**"); qs=segment_grade_summary(gdf,'quality_tier')
                    if not qs.empty: st.dataframe(qs,width="stretch",hide_index=True)
                with cgc:
                    st.markdown("**By data integrity**"); ins=segment_grade_summary(gdf,'integrity_tier')
                    if not ins.empty: st.dataframe(ins,width="stretch",hide_index=True)
                misses=miss_audit(gdf)
                if not misses.empty:
                    with st.expander(f"❌ Loss audit ({len(misses)})",expanded=True): st.dataframe(misses,width="stretch",hide_index=True)
                if st.button("Append to graded history"):
                    old=pd.read_csv(hist_path) if hist_path.exists() else pd.DataFrame()
                    pd.concat([old,gdf],ignore_index=True).to_csv(hist_path,index=False); st.success("Graded history updated.")
        else: st.error("CSV needs player, prop, actual columns.")
    if hist_path.exists():
        h=pd.read_csv(hist_path); st.caption(f"Historical graded rows: {len(h)}")
        if len(h):
            hm=market_grade_summary(h)
            if not hm.empty:
                st.markdown("**Historical market win rates**"); st.dataframe(hm,width="stretch",hide_index=True)
            st.dataframe(h.tail(100),width="stretch",hide_index=True)

st.caption("Model note: projections are estimates, not guarantees. Early-season CFB samples are noisy; the app exposes data readiness and avoids manufacturing missing inputs.")
