from __future__ import annotations

import math, re
from typing import Dict, Tuple

import pandas as pd
import free_data_v15 as base


def _norm(x):
    return re.sub(r'[^a-z0-9]', '', str(x or '').lower())


def _id(x):
    s=str(x or '').strip()
    return s[:-2] if s.endswith('.0') else s


def _num(x, default=0.0):
    try:
        v=float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _logistic(x):
    x=_clamp(float(x), -20.0, 20.0)
    return 1.0/(1.0+math.exp(-x))


def _team_alias(ctx:Dict[str,dict]):
    out={}
    for k,d in (ctx or {}).items():
        if not isinstance(d,dict):
            continue
        full=str(d.get('canonical_name') or d.get('display_name') or k)
        for v in (k,full,d.get('abbreviation')):
            if v:
                out[_norm(v)]=k
    return out


def _team_id_alias(ctx:Dict[str,dict]):
    out={}
    for k,d in (ctx or {}).items():
        if not isinstance(d,dict):
            continue
        eid=_id(d.get('espn_id'))
        if eid:
            out[eid]=k
    return out


def _load(dataset, year, stem=None):
    try:
        return base._parquet(dataset, int(year), stem or dataset)
    except Exception:
        return pd.DataFrame()


def _schedule_blowouts(schedule:pd.DataFrame, ctx:Dict[str,dict]):
    if schedule is None or schedule.empty:
        return {}
    gid=base._col(schedule,'id','game_id','event_id','espn_id')
    home=base._col(schedule,'home_team','home_display_name','home_team_name')
    away=base._col(schedule,'away_team','away_display_name','away_team_name')
    home_id=base._col(schedule,'home_id','home_team_id')
    away_id=base._col(schedule,'away_id','away_team_id')
    hs=base._col(schedule,'home_score','home_points','home_team_score')
    aws=base._col(schedule,'away_score','away_points','away_team_score')
    if not all([gid,home,away,hs,aws]):
        return {}
    amap=_team_alias(ctx); idmap=_team_id_alias(ctx); out={}
    for _,r in schedule.iterrows():
        try:
            hp=float(r.get(hs)); ap=float(r.get(aws))
        except Exception:
            continue
        if not (math.isfinite(hp) and math.isfinite(ap)):
            continue
        margin=hp-ap
        if abs(margin)<21:
            continue
        hid=_id(r.get(home_id)) if home_id else ''
        aid=_id(r.get(away_id)) if away_id else ''
        hn=idmap.get(hid) or amap.get(_norm(r.get(home)),str(r.get(home) or ''))
        an=idmap.get(aid) or amap.get(_norm(r.get(away)),str(r.get(away) or ''))
        winner=hn if margin>0 else an
        loser=an if margin>0 else hn
        winner_id=hid if margin>0 else aid
        loser_id=aid if margin>0 else hid
        out[_id(r.get(gid))]={'winner':winner,'loser':loser,'winner_id':winner_id,'loser_id':loser_id,'margin':abs(margin)}
    return out


def _pass_attempt_series(sub:pd.DataFrame):
    out=pd.Series(0.0,index=sub.index,dtype=float)
    cat=base._col(sub,'category')
    cp=base._col(sub,'completions/passingAttempts','completionAttempts')
    stat1=base._col(sub,'stat_1')
    passing_mask=(sub[cat].astype(str).str.lower()=='passing') if cat else pd.Series(True,index=sub.index)
    for i in sub.index[passing_mask]:
        raw=sub.at[i,cp] if cp and pd.notna(sub.at[i,cp]) else (sub.at[i,stat1] if stat1 else '')
        m=re.search(r'(\d+)\s*[/\-]\s*(\d+)',str(raw or ''))
        if m:
            out.at[i]=float(m.group(2))
    return out


def _historical_usage(year:int, ctx:Dict[str,dict]):
    """Coach/rotation proxy from prior-season 21+ point games.

    Uses actual player-box concentration: lead QB attempt share, RB1 carry share,
    WR1 reception share, plus losing-team pass rate. Team identity is joined by ESPN
    team_id, which is stable across the schedule and player-box files.
    """
    prev=max(2020,int(year)-1)
    schedule=_load('schedules',prev,'cfb_schedule')
    pb=_load('player_box',prev,'player_box')
    games=_schedule_blowouts(schedule,ctx)
    if pb is None or pb.empty or not games:
        return {}, {'historical_blowout_games':len(games),'historical_player_box':len(pb) if pb is not None else 0}
    gid=base._col(pb,'game_id','id','event_id')
    teamc=base._col(pb,'team_id')
    namec=base._col(pb,'athlete_name','athlete_display_name','player_name','player','athlete')
    if not gid or not teamc or not namec:
        return {}, {'historical_blowout_games':len(games),'historical_player_box':len(pb)}
    rushc=base._col(pb,'rushingAttempts','rushing_attempts','rushing_carries','carries')
    recc=base._col(pb,'receptions','receiving_receptions')
    idmap=_team_id_alias(ctx); amap=_team_alias(ctx)
    use=pb[pb[gid].map(_id).isin(set(games))].copy()
    rows=[]
    for (game_id, rawteam),sub in use.groupby([gid,teamc]):
        gm=games.get(_id(game_id))
        if not gm:
            continue
        tid=_id(rawteam)
        if tid==gm.get('winner_id'):
            side='winner'; team=gm['winner']
        elif tid==gm.get('loser_id'):
            side='loser'; team=gm['loser']
        else:
            team=idmap.get(tid,''); side=''
        if not side or not team:
            continue
        pass_s=_pass_attempt_series(sub).clip(lower=0)
        pa=float(pass_s.sum()); qbs=float(pass_s.max()/pa) if pa>0 else 0.0
        rush_s=pd.to_numeric(sub[rushc],errors='coerce').fillna(0).clip(lower=0) if rushc else pd.Series(0.0,index=sub.index)
        ra=float(rush_s.sum()); rbs=float(rush_s.max()/ra) if ra>0 else 0.0
        rec_s=pd.to_numeric(sub[recc],errors='coerce').fillna(0).clip(lower=0) if recc else pd.Series(0.0,index=sub.index)
        rec=float(rec_s.sum()); wrs=float(rec_s.max()/rec) if rec>0 else 0.0
        pass_rate=pa/max(pa+ra,1.0)
        # Keep only teams that resolve back to the active team context; FCS-only rows
        # are useful for opponent history but not for coach-specific current projections.
        key=team if team in ctx else amap.get(_norm(team))
        if not key:
            continue
        rows.append({'team':key,'side':side,'margin':gm['margin'],'qb_share':qbs,'rb_share':rbs,'wr_share':wrs,'pass_rate':pass_rate})
    if not rows:
        return {}, {'historical_blowout_games':len(games),'historical_player_box':len(pb),'historical_rows':0}
    df=pd.DataFrame(rows); out={}
    for team,sub in df.groupby('team'):
        w=sub[sub.side=='winner']; l=sub[sub.side=='loser']
        qb=float(w.qb_share[w.qb_share>0].mean()) if len(w) and (w.qb_share>0).any() else .82
        rb=float(w.rb_share[w.rb_share>0].mean()) if len(w) and (w.rb_share>0).any() else .52
        wr=float(w.wr_share[w.wr_share>0].mean()) if len(w) and (w.wr_share>0).any() else .34
        gp=float(l.pass_rate[l.pass_rate>0].mean()) if len(l) and (l.pass_rate>0).any() else .62
        hook=_clamp((.90-qb)/.30,0.0,1.0)
        out[team]={
            'coach_blowout_samples':int(len(w)),
            'coach_qb_retention_hist':_clamp(qb,.50,.98),
            'coach_rb1_share_hist':_clamp(rb,.25,.85),
            'coach_wr1_share_hist':_clamp(wr,.18,.70),
            'coach_hook_aggression':hook,
            'garbage_pass_rate_hist':_clamp(gp,.42,.82),
        }
    return out, {'historical_blowout_games':len(games),'historical_player_box':len(pb),'historical_rows':len(rows),'historical_teams':len(out)}


def enrich_blowout_context(year:int, ctx:Dict[str,dict]) -> Tuple[Dict[str,dict],dict]:
    hist,health=_historical_usage(int(year),ctx)
    for team,vals in hist.items():
        if team in ctx:
            ctx[team].update(vals)
    return ctx,health


def game_blowout_profile(game:dict, home_ctx:dict, away_ctx:dict) -> dict:
    margin=abs(_num(game.get('model_home_margin')))
    fav=str(game.get('favorite') or (game.get('home') if _num(game.get('model_home_margin'))>=0 else game.get('away')))
    home=str(game.get('home') or ''); away=str(game.get('away') or '')
    fctx=home_ctx if fav==home else away_ctx
    dctx=away_ctx if fav==home else home_ctx
    power_gap=abs(_num(home_ctx.get('power_z'))-_num(away_ctx.get('power_z')))
    talent_gap=abs(_num(home_ctx.get('talent'))-_num(away_ctx.get('talent')))
    expl_gap=max(0.0,_num(fctx.get('off_expl'))-_num(dctx.get('def_expl')))
    dog_three=_clamp(_num(dctx.get('three_out_rate')),.0,.8)
    dog_score=_clamp(_num(dctx.get('score_drive_rate')),.0,.8)
    dog_passdown=_num(dctx.get('passing_down_epa'))
    dog_off=_num(dctx.get('off_rating'))
    turnover_gap=max(0.0,_num(dctx.get('turnovers_pg'))-_num(fctx.get('turnovers_pg')))
    samples=int(_num(fctx.get('coach_blowout_samples')))
    hist_hook=_num(fctx.get('coach_hook_aggression'),.35)
    # Shrink coach behavior toward league-average when prior blowout sample is tiny.
    hist_weight=_clamp(samples/5.0,0,1)
    hook=_clamp(.35*(1-hist_weight)+hist_hook*hist_weight,0,1)
    x=(margin-15.0)/5.4 + .32*power_gap + min(talent_gap/900.0,.65) + .18*max(expl_gap,0) + .75*dog_three - .60*dog_score - .10*dog_passdown - .04*dog_off + .22*turnover_gap
    p=_clamp(_logistic(x),.05,.96)
    level='LOW' if p<.35 else ('MODERATE' if p<.55 else ('HIGH' if p<.75 else 'EXTREME'))
    hist_qb=_clamp(_num(fctx.get('coach_qb_retention_hist'),.82),.50,.98)
    hist_qb=.82*(1-hist_weight)+hist_qb*hist_weight
    qb_ret=_clamp((1.0-p*(.08+.20*hook))*(.90+.10*hist_qb/.82),.58,.98)
    wr_ret=_clamp(1.0-p*(.08+.20*hook),.64,.99)
    rb_ret=_clamp(1.0-p*(.04+.13*hook),.72,1.00)
    backup=_clamp((1.0-qb_ret)*(.75+.25*hook),0,.42)
    catchup=_clamp(1.0+p*(.08+.10*_clamp(_num(dctx.get('garbage_pass_rate_hist'),.62)-.55,0,.25)),1.0,1.18)
    return {
        'blowout_prob':p,'blowout_level':level,'favorite':fav,'underdog':away if fav==home else home,
        'coach_hook_aggression':hook,'coach_blowout_samples':samples,'qb_starter_retention':qb_ret,'wr1_retention':wr_ret,'rb1_retention':rb_ret,
        'backup_opportunity':backup,'underdog_catchup_mult':catchup,
        'blowout_components':{'margin':margin,'power_gap':power_gap,'talent_gap':talent_gap,'explosive_gap':expl_gap,'dog_three_out':dog_three,'dog_score_drive':dog_score,'turnover_gap':turnover_gap},
    }


def player_blowout_modifier(player:dict, market:str, game:dict, team_name:str, team_ctx:dict) -> Tuple[float,float,list,float]:
    p=_clamp(_num(game.get('blowout_prob')),0,1)
    level=str(game.get('blowout_level') or ('HIGH' if p>=.55 else 'LOW'))
    fav=str(game.get('favorite') or '')
    is_fav=_norm(team_name)==_norm(fav)
    starter=bool(player.get('starter_current'))
    hook=_clamp(_num(game.get('coach_hook_aggression'),_num(team_ctx.get('coach_hook_aggression'),.35)),0,1)
    qb_ret=_clamp(_num(game.get('qb_starter_retention'),1-p*(.10+.24*hook)),.58,.99)
    wr_ret=_clamp(_num(game.get('wr1_retention'),1-p*(.08+.20*hook)),.64,1.0)
    rb_ret=_clamp(_num(game.get('rb1_retention'),1-p*(.04+.13*hook)),.72,1.02)
    backup=_clamp(_num(game.get('backup_opportunity'),1-qb_ret),0,.45)
    catch=_clamp(_num(game.get('underdog_catchup_mult'),1+p*.10),1,1.18)
    notes=[]; mult=1.0; retention=1.0
    qb_pass={'Passing Yards','Pass Attempts','Completions','Pass + Rush Yards'}
    qb_td={'Passing TDs','Interceptions'}
    wr={'Receiving Yards','Receptions'}
    rb={'Rushing Yards','Rush Attempts'}
    combo={'Rush + Rec Yards'}
    td={'Rush + Rec TDs','Total TDs'}
    if is_fav:
        if market in qb_pass:
            retention=qb_ret; mult*=qb_ret; notes.append(f'{level.lower()} blowout QB hook')
        elif market in wr:
            retention=wr_ret; mult*=wr_ret; notes.append(f'{level.lower()} blowout WR1 retention')
        elif market in rb:
            if starter:
                retention=rb_ret
                early=1.0+min(p,.70)*.05
                mult*=rb_ret*early
                notes.append('favorite RB early-volume / late-hook blend')
            else:
                retention=1.0+backup*.55; mult*=retention; notes.append('backup rushing opportunity from blowout')
        elif market in combo:
            retention=(rb_ret+wr_ret)/2; mult*=retention; notes.append('blowout skill-position retention')
        elif market in qb_td:
            retention=_clamp(.55+.45*qb_ret,.78,1); mult*=retention; notes.append('QB scoring window vs hook risk')
        elif market in td:
            retention=_clamp(.94+.08*p-.05*hook,.88,1.06); mult*=retention; notes.append('favorite red-zone boost with hook cap')
    else:
        if market in {'Pass Attempts','Completions'}:
            mult*=catch; notes.append('underdog garbage-time pass volume')
        elif market in {'Passing Yards','Pass + Rush Yards'}:
            mult*=1.0+(catch-1.0)*.60; notes.append('underdog catch-up passing volume')
        elif market in wr:
            mult*=1.0+(catch-1.0)*.72; notes.append('garbage-time target boost')
        elif market in rb:
            mult*=_clamp(1.0-.12*p,.86,1.0); notes.append('negative-script rushing tax')
        elif market in combo:
            mult*=_clamp(1.0-.04*p,.92,1.02); notes.append('mixed catch-up script')
    sd_mult=1.0+.10*p+.08*hook*p
    if p>=.55:
        notes.append(f'blowout risk {level}')
    return float(_clamp(mult,.55,1.30)),float(_clamp(sd_mult,1.0,1.22)),notes,float(retention)
