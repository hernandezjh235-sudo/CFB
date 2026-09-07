from __future__ import annotations

import math, re
from typing import Dict, List, Tuple

import pandas as pd


def _norm(x): return re.sub(r'[^a-z0-9]','',str(x or '').lower())
def _num(x,d=0.0):
    try:
        v=float(x); return v if math.isfinite(v) else d
    except Exception:return d

def _clamp(x,lo,hi): return max(lo,min(hi,x))

PASS={'Passing Yards','Pass Attempts','Completions','Passing TDs','Interceptions','Pass + Rush Yards'}
REC={'Receiving Yards','Receptions'}
RUSH={'Rushing Yards','Rush Attempts'}


def integrity_audit(live_row:dict, player:dict, team:str, opp:str, game:dict, team_ctx:dict, market:str) -> Tuple[str,float,List[str]]:
    """Independent pre-pick data-integrity gate.

    It never changes the projection direction. It measures whether the matchup,
    player identity, current role and game environment are sufficiently resolved to
    trust the projection/status.
    """
    flags=[]; score=1.0
    away=str(game.get('away') or ''); home=str(game.get('home') or '')
    ra=str(live_row.get('away') or ''); rh=str(live_row.get('home') or '')

    # Event lock: live book away/home must agree with the modeled game when present.
    if ra and rh:
        event_ok=(_norm(ra)==_norm(away) and _norm(rh)==_norm(home)) or \
                 (_norm(ra) in _norm(away) and _norm(rh) in _norm(home)) or \
                 (_norm(away) in _norm(ra) and _norm(home) in _norm(rh))
        if not event_ok:
            flags.append('LIVE EVENT MISMATCH'); score-=.45
    else:
        flags.append('NO LIVE EVENT LOCK'); score-=.16

    if not team or _norm(team) not in {_norm(away),_norm(home)}:
        flags.append('TEAM UNRESOLVED'); score-=.35
    if not opp or _norm(opp) not in {_norm(away),_norm(home)}:
        flags.append('OPPONENT UNRESOLVED'); score-=.18

    src=str(player.get('sample_source') or 'fallback').lower(); gp=_num(player.get('games'))
    current_team=str(player.get('current_team') or '')
    sample_team=str(player.get('team') or '')
    transferred=bool(current_team and sample_team and _norm(current_team)!=_norm(sample_team))
    if src in {'roster','fallback'}:
        flags.append('ROSTER-ONLY SAMPLE'); score-=.24
    elif src=='prior':
        score-=.08
    if transferred:
        flags.append('TRANSFER ROLE'); score-=.10
    if gp<=1 and src=='current':
        flags.append('ONE-GAME SAMPLE'); score-=.08

    adv_pass=_num(player.get('adv_pass_att')); adv_tar=_num(player.get('adv_targets')); adv_car=_num(player.get('adv_rush_car'))
    starter=bool(player.get('starter_current'))
    if market in PASS and adv_pass<=0 and not starter:
        flags.append('QB ROLE UNVERIFIED'); score-=.22
    if market in REC and adv_tar<=0:
        flags.append('TARGET ROLE UNVERIFIED'); score-=.25
    if market in RUSH and adv_car<=0:
        flags.append('CARRY ROLE UNVERIFIED'); score-=.23

    # Spread/total are validation context, not a target for the player projection.
    if game.get('market_total') is None:
        flags.append('NO MARKET TOTAL'); score-=.04
    if game.get('market_home_spread') is None:
        flags.append('NO MARKET SPREAD'); score-=.04

    # Current injury/depth adapters are intentionally explicit: missing does not mean healthy.
    score=_clamp(score,0,1)
    tier='HIGH' if score>=.82 else ('MEDIUM' if score>=.64 else 'LOW')
    return tier,float(score),flags


def enforce_integrity_status(status:str, probability:float, quality_tier:str, integrity_tier:str, flags:List[str]) -> str:
    """Prevent uncertain identity/role rows from becoming official-looking plays."""
    hard={'LIVE EVENT MISMATCH','TEAM UNRESOLVED','OPPONENT UNRESOLVED'}
    if any(f in hard for f in flags): return 'TRACK'
    if integrity_tier=='LOW': return 'TRACK'
    if quality_tier=='LOW': return 'TRACK'
    if integrity_tier=='MEDIUM' and status=='PLAYABLE': return 'LEAN'
    return status


def market_grade_summary(df:pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or 'result' not in df.columns:return pd.DataFrame()
    d=df[df['result'].isin(['WIN','LOSS','PUSH'])].copy()
    if d.empty:return pd.DataFrame()
    rows=[]
    for market,g in d.groupby('prop',dropna=False):
        w=int((g.result=='WIN').sum()); l=int((g.result=='LOSS').sum()); p=int((g.result=='PUSH').sum())
        n=w+l; rows.append({'Market':market,'W':w,'L':l,'Push':p,'Win %':round(100*w/n,1) if n else None,'N':n})
    return pd.DataFrame(rows).sort_values(['N','Win %'],ascending=[False,False])


def segment_grade_summary(df:pd.DataFrame, column:str) -> pd.DataFrame:
    if df is None or df.empty or column not in df.columns or 'result' not in df.columns:return pd.DataFrame()
    d=df[df['result'].isin(['WIN','LOSS'])].copy()
    if d.empty:return pd.DataFrame()
    rows=[]
    for val,g in d.groupby(column,dropna=False):
        w=int((g.result=='WIN').sum()); l=int((g.result=='LOSS').sum()); n=w+l
        rows.append({column:str(val),'W':w,'L':l,'Win %':round(100*w/n,1) if n else None,'N':n})
    return pd.DataFrame(rows).sort_values(['N','Win %'],ascending=[False,False])


def miss_audit(df:pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or 'result' not in df.columns:return pd.DataFrame()
    d=df[df.result=='LOSS'].copy()
    if d.empty:return pd.DataFrame()
    cols=[c for c in ['player','prop','side','line','projection','actual','probability','status','quality_tier','integrity_tier','integrity_flags','notes'] if c in d.columns]
    return d[cols].sort_values('probability',ascending=False) if 'probability' in d.columns else d[cols]
