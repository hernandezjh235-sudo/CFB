from __future__ import annotations

import math, re
import pandas as pd


def _n(x): return re.sub(r'[^a-z0-9]','',str(x or '').lower())
def _f(x,d=0.0):
    try:
        v=float(x); return v if math.isfinite(v) else d
    except Exception:return d
def _clamp(x,lo,hi): return max(lo,min(hi,float(x)))


def enrich_role_depth(players: pd.DataFrame) -> pd.DataFrame:
    """Add current-team role hierarchy from actual advanced opportunity.

    This does not use prop lines. It ranks current carry/target/air-yard involvement
    within each team so the projection knows RB1/RB2/WR1-type roles instead of
    treating every rostered player as an equal workload candidate.
    """
    if players is None or players.empty:
        return players
    p=players.copy()
    for c,default in [('role_team',''),('carry_role_rank',0),('target_role_rank',0),('air_role_rank',0),
                      ('rush_role_label','UNVERIFIED'),('target_role_label','UNVERIFIED'),('role_depth_conf',0.0)]:
        if c not in p.columns:p[c]=default
    p['role_team']=p.apply(lambda r:str(r.get('current_team') or r.get('team') or ''),axis=1)
    p['_team_key']=p['role_team'].map(_n)
    p['_car']=pd.to_numeric(p.get('adv_rush_car',0),errors='coerce').fillna(0)
    p['_tar']=pd.to_numeric(p.get('adv_targets',0),errors='coerce').fillna(0)
    p['_air']=pd.to_numeric(p.get('air_yard_share',0),errors='coerce').fillna(0)
    p['_cshare']=pd.to_numeric(p.get('adv_carry_share',0),errors='coerce').fillna(0)
    p['_tshare']=pd.to_numeric(p.get('adv_target_share',0),errors='coerce').fillna(0)

    for _,idx in p.groupby('_team_key').groups.items():
        ix=list(idx)
        if not ix: continue
        # Dense ranks only among players with observed opportunity.
        car=p.loc[ix,'_car']; tar=p.loc[ix,'_tar']; air=p.loc[ix,'_air']
        car_rank=car.rank(method='dense',ascending=False).astype(int)
        tar_rank=tar.rank(method='dense',ascending=False).astype(int)
        air_rank=air.rank(method='dense',ascending=False).astype(int)
        for j in ix:
            if p.at[j,'_car']>0:p.at[j,'carry_role_rank']=int(car_rank.loc[j])
            if p.at[j,'_tar']>0:p.at[j,'target_role_rank']=int(tar_rank.loc[j])
            if p.at[j,'_air']>0:p.at[j,'air_role_rank']=int(air_rank.loc[j])
            cr=int(p.at[j,'carry_role_rank']); tr=int(p.at[j,'target_role_rank'])
            cs=_f(p.at[j,'_cshare']); ts=_f(p.at[j,'_tshare'])
            if cr==1 and cs>=.28: rlab='RB1/LEAD'
            elif cr in (1,2) and cs>=.14: rlab='ROTATION'
            elif cr>0: rlab='DEPTH'
            else: rlab='UNVERIFIED'
            if tr==1 and ts>=.20: tlab='WR1/TARGET LEAD'
            elif tr in (1,2,3) and ts>=.10: tlab='PRIMARY ROTATION'
            elif tr>0: tlab='DEPTH TARGET'
            else: tlab='UNVERIFIED'
            p.at[j,'rush_role_label']=rlab; p.at[j,'target_role_label']=tlab
            evidence=max(min(_f(p.at[j,'_car'])/12,1),min(_f(p.at[j,'_tar'])/8,1),min(cs/.30,1),min(ts/.22,1))
            if bool(p.at[j,'starter_current']) if 'starter_current' in p.columns else False: evidence=max(evidence,.75)
            p.at[j,'role_depth_conf']=_clamp(evidence,0,1)
    return p.drop(columns=['_team_key','_car','_tar','_air','_cshare','_tshare'],errors='ignore')


def role_adjust_projection(proj:float, sd:float, player:dict, market:str):
    """Market-specific role allocation correction.

    We only make bounded changes. One game may move role expectations, but cannot
    fully replace the matchup/efficiency model.
    """
    p=max(0.0,_f(proj)); s=max(.1,_f(sd,1)); notes=[]
    pos=str(player.get('position') or player.get('position_abbreviation') or '').upper()
    pass_att=_f(player.get('adv_pass_att')); car=_f(player.get('adv_rush_car')); tar=_f(player.get('adv_targets'))
    cshare=_clamp(_f(player.get('adv_carry_share')),0,1); tshare=_clamp(_f(player.get('adv_target_share')),0,1)
    cr=int(_f(player.get('carry_role_rank'))); tr=int(_f(player.get('target_role_rank')))
    role_conf=_clamp(_f(player.get('role_depth_conf')),0,1)
    qb=(pos=='QB' or pass_att>=10)

    if market in {'Rushing Yards','Rush Attempts'}:
        if qb:
            # A QB with observed designed/scramble work must not be projected from
            # an RB-style team baseline. This is a conservative dual-threat floor.
            qshare=_clamp(_f(player.get('qb_rush_share')),0,.50)
            if car>=3 or qshare>=.05:
                floor_y=car*max(_f(player.get('adv_ypc'),4.5),2.0)*.55
                if market=='Rushing Yards' and floor_y>p:
                    p=.60*p+.40*floor_y; notes.append('QB current-rush opportunity floor')
                notes.append('QB rush role verified')
        else:
            if cr==1 and cshare>=.28:
                p*=1.04; notes.append('lead-back share confirmed')
            elif cr>=3 and cshare<.16:
                p*=.88; s*=1.08; notes.append('depth/committee carry tax')
            elif cr==0:
                s*=1.12; notes.append('carry hierarchy unverified')
    elif market in {'Receiving Yards','Receptions'}:
        if tr==1 and tshare>=.20:
            p*=1.05; notes.append('target leader role confirmed')
        elif tr in (2,3) and tshare>=.10:
            p*=1.01; notes.append('primary target rotation confirmed')
        elif tr>=4 and tshare<.10:
            p*=.88; s*=1.10; notes.append('depth target-share tax')
        elif tr==0:
            s*=1.14; notes.append('target hierarchy unverified')
    # Early-season role uncertainty widens variance instead of manufacturing mean.
    if role_conf<.45 and market in {'Rushing Yards','Rush Attempts','Receiving Yards','Receptions'}:
        s*=1.10
    return float(max(0,p)),float(s),notes


def qb_upset_margin_delta(home_ctx:dict, away_ctx:dict) -> tuple[float,list[str]]:
    """Return a bounded home-margin adjustment for explosive QB/pass-game ceiling.

    A talented favorite can still lose when the opponent owns a major passing
    efficiency/explosive mismatch. This is deliberately capped so it cannot replace
    the core power model or simply chase one result.
    """
    def attack(off, deff):
        ypa=_f(off.get('team_ypa_adv')) or (_f(off.get('team_pass_yds_pg'))/max(_f(off.get('team_pass_att_pg')),1))
        score=_f(off.get('score_drive_rate'),.34)
        epa=_f(off.get('passing_down_epa'))
        sack=_f(off.get('sack_rate_allowed'))
        adot=_f(off.get('team_adot'))
        opp_pass=_f(deff.get('def_passing'))
        opp_expl=_f(deff.get('def_expl'))
        # Positive = more dangerous passing/upset ceiling.
        return (ypa-7.0)*.85 + (score-.34)*7.0 + epa*1.4 + (adot-8.0)*.08 - sack*4.0 + (-opp_pass)*.14 + (-opp_expl)*.06
    hs=attack(home_ctx,away_ctx); as_=attack(away_ctx,home_ctx)
    delta=_clamp((hs-as_)*.70,-4.25,4.25)
    notes=[]
    if delta>=1.5:notes.append('home explosive-QB ceiling boost')
    elif delta<=-1.5:notes.append('away explosive-QB upset path')
    return float(delta),notes
