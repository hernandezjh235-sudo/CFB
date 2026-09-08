from __future__ import annotations

import math, re
from typing import Tuple, List


def _num(x,d=0.0):
    try:
        v=float(x); return v if math.isfinite(v) else d
    except Exception:return d

def _clamp(x,lo,hi): return max(lo,min(hi,x))
def _norm(x): return re.sub(r'[^a-z0-9]','',str(x or '').lower())

PASS_MARKETS={'Passing Yards','Pass Attempts','Completions','Passing TDs','Pass + Rush Yards'}
REC_MARKETS={'Receiving Yards','Receptions'}
RUSH_MARKETS={'Rushing Yards','Rush Attempts'}


def projection_quality(player:dict, market:str, team_ctx:dict, game:dict) -> Tuple[float,float,List[str],str]:
    """Return reliability multiplier, probability cap, notes and quality tier.

    This layer never uses the prop line to manufacture a projection. It evaluates
    whether the role/opportunity inputs underneath the projection are trustworthy.
    """
    src=str(player.get('sample_source') or 'fallback').lower()
    gp=_num(player.get('games'))
    current_team=str(player.get('current_team') or '')
    sample_team=str(player.get('team') or '')
    transferred=bool(current_team and sample_team and _norm(current_team)!=_norm(sample_team))
    starter=bool(player.get('starter_current'))
    adv_pass=_num(player.get('adv_pass_att'))
    adv_tar=_num(player.get('adv_targets'))
    adv_car=_num(player.get('adv_rush_car'))
    carry_rank=int(_num(player.get('carry_role_rank')))
    target_rank=int(_num(player.get('target_role_rank')))
    carry_share=_num(player.get('adv_carry_share'))
    target_share=_num(player.get('adv_target_share'))
    role_depth=_num(player.get('role_depth_conf'))
    notes=[]

    if market in PASS_MARKETS:
        role=1.0 if adv_pass>=15 else (.90 if starter else (.78 if src=='current' else .66))
    elif market in REC_MARKETS:
        role=1.0 if (adv_tar>=4 and target_rank in (1,2,3)) else (.88 if adv_tar>0 else (.76 if src=='current' and gp>=2 else .58))
        if (target_rank>=4 or (adv_tar<4 and target_share<.08)) and target_share<.10: role*=.82; notes.append('depth target role')
        elif target_rank in (1,2) and target_share>=.15: role=min(1.0,role+.04)
    elif market in RUSH_MARKETS:
        role=1.0 if (adv_car>=6 and (carry_rank in (1,2) or adv_pass>=10)) else (.88 if adv_car>0 else (.76 if src=='current' and gp>=2 else .62))
        if (carry_rank>=3 or (adv_car<6 and carry_share<.14)) and carry_share<.16 and adv_pass<10: role*=.82; notes.append('committee/depth carry role')
        elif carry_rank==1 and carry_share>=.28: role=min(1.0,role+.04)
    else:
        role=.82 if src=='current' else .70
    if role_depth>0: role=.82*role+.18*role_depth

    if transferred and not ((market in PASS_MARKETS and adv_pass>0) or (market in REC_MARKETS and adv_tar>0) or (market in RUSH_MARKETS and adv_car>0)):
        role*=.72; notes.append('transfer role not yet supported by current usage')
    if src in {'roster','fallback'}:
        role*=.72; notes.append('roster-only role evidence')
    if gp<=1 and src=='current': role*=.90

    # Competitive games should not inherit broad blowout uncertainty. The dedicated
    # blowout engine still handles true high-risk games, but close projected games
    # retain normal starter opportunity.
    margin=abs(_num(game.get('model_home_margin')))
    if margin<=10 and _num(game.get('blowout_prob'))<.45:
        role=min(1.0,role+.05)

    rel=_clamp(.48+.50*role,.56,.98)
    pcap=_clamp(.54+.30*role,.56,.86)
    if gp<=1 and src=='current' and market in REC_MARKETS|RUSH_MARKETS:
        pcap=min(pcap,.74); notes.append('one-game role confidence cap')
    tier='HIGH' if role>=.88 else ('MEDIUM' if role>=.70 else 'LOW')
    if tier=='LOW': notes.append('role certainty low')
    return rel,pcap,notes,tier


def stabilize_projection(proj:float, sd:float, player:dict, market:str, team_ctx:dict, game:dict) -> Tuple[float,float,List[str]]:
    """Apply independent opportunity floors only where current QB role is credible.

    Floors are derived from team production/attempt opportunity, never from the
    sportsbook player line. This prevents stale backup samples from collapsing a
    confirmed QB1 projection while leaving uncertain WR/RB roles untouched.
    """
    p=max(0.0,_num(proj)); s=max(.1,_num(sd,1)); notes=[]
    src=str(player.get('sample_source') or 'fallback').lower()
    starter=bool(player.get('starter_current'))
    adv_pass=_num(player.get('adv_pass_att'))
    current_team=bool(player.get('current_team'))
    margin=abs(_num(game.get('model_home_margin')))
    competitive=margin<=10 and _num(game.get('blowout_prob'))<.45
    credible_qb=(adv_pass>=15 or starter or (current_team and src in {'current','prior'}))

    if credible_qb and market=='Passing Yards':
        team_y=_num(team_ctx.get('team_pass_yds_pg'))
        team_att=_num(team_ctx.get('team_pass_att_pg'))
        if team_y>0 and team_att>0:
            floor=team_y*(.80 if competitive else .68)
            if p<floor:
                # Partial correction rather than hard replacement protects matchup signal.
                p=.35*p+.65*floor
                s=max(s,.22*p,36.0)
                notes.append('QB1 team-volume floor')
    elif credible_qb and market=='Pass Attempts':
        team_att=_num(team_ctx.get('team_pass_att_pg'))
        if team_att>0:
            floor=team_att*(.84 if competitive else .72)
            if p<floor:
                p=.35*p+.65*floor; s=max(s,4.8); notes.append('QB1 attempt floor')
    elif credible_qb and market=='Completions':
        team_comp=_num(team_ctx.get('team_pass_comp_pg'))
        if team_comp>0:
            floor=team_comp*(.82 if competitive else .70)
            if p<floor:
                p=.35*p+.65*floor; s=max(s,3.4); notes.append('QB1 completion floor')
    return float(p),float(s),notes


def calibrate_probability(raw_p:float, player:dict, market:str, team_ctx:dict, game:dict,
                          proj:float, line:float) -> Tuple[float,float,List[str],str]:
    rel,pcap,notes,tier=projection_quality(player,market,team_ctx,game)
    p=.5+(_num(raw_p,.5)-.5)*rel
    # Huge model-vs-line gaps with weak role evidence are a data-quality warning,
    # not automatic confidence. Keep the model direction but suppress status.
    ln=abs(_num(line)); ratio=(abs(_num(proj))/ln) if ln>0 else 1.0
    if tier=='LOW' and (ratio<.45 or ratio>1.75):
        pcap=min(pcap,.56); notes.append('extreme edge suppressed until role is verified')
    elif tier=='MEDIUM' and (ratio<.35 or ratio>2.0):
        pcap=min(pcap,.59); notes.append('edge capped by role uncertainty')
    p=_clamp(p,1-pcap,pcap)
    return float(p),float(pcap),notes,tier


def status_from_quality(p:float, proj:float, tier:str, market:str, player:dict) -> str:
    if proj<=0:return 'TRACK'
    # Receiving/rushing props need actual current opportunity before becoming PLAYABLE.
    if tier=='LOW':return 'TRACK'
    if market in REC_MARKETS and _num(player.get('adv_targets'))<=0 and str(player.get('sample_source') or '').lower()!='current':
        return 'TRACK'
    if market in REC_MARKETS and ((int(_num(player.get('target_role_rank')))>=4 and _num(player.get('adv_target_share'))<.10) or (_num(player.get('adv_targets'))<4 and _num(player.get('adv_target_share'))<.08)):
        return 'TRACK'
    if market in RUSH_MARKETS and _num(player.get('adv_rush_car'))<=0 and str(player.get('sample_source') or '').lower()!='current':
        return 'TRACK'
    if market in RUSH_MARKETS and (((int(_num(player.get('carry_role_rank')))>=3 and _num(player.get('adv_carry_share'))<.16) or (_num(player.get('adv_rush_car'))<6 and _num(player.get('adv_carry_share'))<.14)) and _num(player.get('adv_pass_att'))<10):
        return 'TRACK'
    return 'PLAYABLE' if p>=.60 and tier=='HIGH' else ('LEAN' if p>=.56 else 'TRACK')
