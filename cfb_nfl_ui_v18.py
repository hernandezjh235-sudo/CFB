from __future__ import annotations

import html, math, re
from functools import lru_cache
from typing import Dict, List

import requests
import streamlit as st

ESPN_TEAMS='https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams'

def _norm(x): return re.sub(r'[^a-z0-9]','',str(x or '').lower())
def _num(x,d=0.0):
    try:
        v=float(x); return v if math.isfinite(v) else d
    except Exception:return d

def _pct(x): return 100*_num(x)
def _fmt(x,n=1):
    try:return f'{float(x):.{n}f}'
    except Exception:return '—'

def _hex(c,default='#2f81f7'):
    c=str(c or '').strip().lstrip('#')
    return f'#{c}' if len(c) in {3,6} else default

@lru_cache(maxsize=2)
def espn_team_branding()->Dict[str,dict]:
    out={}
    try:
        r=requests.get(ESPN_TEAMS,params={'limit':500},timeout=(4,15),headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        r.raise_for_status(); j=r.json()
        sports=j.get('sports') or []
        leagues=(sports[0].get('leagues') or []) if sports else []
        teams=(leagues[0].get('teams') or []) if leagues else []
        for wrap in teams:
            t=wrap.get('team') if isinstance(wrap,dict) else None
            if not isinstance(t,dict):continue
            names={t.get('displayName'),t.get('shortDisplayName'),t.get('location'),t.get('name'),t.get('abbreviation')}
            logos=t.get('logos') or []
            logo=''
            for z in logos:
                if isinstance(z,dict) and z.get('href'): logo=z['href']; break
            info={'logo':logo,'color':_hex(t.get('color')),'alternate_color':_hex(t.get('alternateColor'),'#8fa4b8'),'abbreviation':t.get('abbreviation') or '', 'espn_id':str(t.get('id') or '')}
            for n in names:
                if n: out[_norm(n)]=info
    except Exception:
        return {}
    return out

def hydrate_team_branding(ctx:Dict[str,dict])->Dict[str,dict]:
    brands=espn_team_branding()
    if not brands:return ctx
    for team,d in list((ctx or {}).items()):
        key=_norm(team); info=brands.get(key)
        if not info:
            # Conservative containment fallback for names like "Duke Blue Devils" vs "Duke".
            hits=[v for k,v in brands.items() if len(k)>=4 and (k in key or key in k)]
            info=hits[0] if len(hits)==1 else None
        if info:
            if not d.get('logo'):d['logo']=info.get('logo','')
            if not d.get('color'):d['color']=info.get('color','#2f81f7')
            d.setdefault('alternate_color',info.get('alternate_color','#8fa4b8'))
            d.setdefault('abbreviation',info.get('abbreviation',''))
            d.setdefault('espn_id',info.get('espn_id',''))
    return ctx

def _team(ctx,name):
    if name in ctx:return ctx[name]
    n=_norm(name)
    for k,v in (ctx or {}).items():
        if _norm(k)==n:return v
    return {}

def _logo(ctx,name): return str(_team(ctx,name).get('logo') or '')
def _color(ctx,name): return str(_team(ctx,name).get('color') or '#2f81f7')
def _abbr(ctx,name): return str(_team(ctx,name).get('abbreviation') or name)[:10]

def inject_nfl_cfb_css():
    st.markdown('''<style>
.cfb18-board{display:grid;gap:12px}.cfb18-ml{--away:#2f81f7;--home:#e9c34f;--winner:#e9c34f;background:linear-gradient(145deg,#07111b,#050a10);border:1px solid #24364a;border-left:4px solid var(--winner);border-radius:20px;overflow:hidden;box-shadow:0 14px 38px rgba(0,0,0,.24)}
.cfb18-top{padding:9px 12px;border-bottom:1px solid #17283a;color:#91a6bb;font-size:10px;font-weight:800;display:flex;justify-content:space-between;gap:8px}.cfb18-mlgrid{display:grid;grid-template-columns:1fr 1.18fr 1fr;align-items:center;gap:8px;padding:14px}.cfb18-team{text-align:center}.cfb18-team img{width:62px;height:62px;object-fit:contain;filter:drop-shadow(0 0 10px rgba(255,255,255,.08))}.cfb18-teamname{font-size:16px;font-weight:950;margin-top:4px}.cfb18-points{font-size:24px;font-weight:1000}.cfb18-prob{font-size:10px;color:#93a7ba}.cfb18-win{text-align:center}.cfb18-winkicker{font-size:8px;color:#e9c34f;font-weight:950;letter-spacing:.14em}.cfb18-win img{width:70px;height:70px;object-fit:contain;padding:5px;border-radius:16px;background:radial-gradient(circle,rgba(233,195,79,.18),rgba(8,15,24,.3));border:1px solid rgba(233,195,79,.5)}.cfb18-winname{font-size:19px;font-weight:1000;color:#f1d167}.cfb18-winprob{font-size:30px;font-weight:1000}.cfb18-mlmetrics{display:grid;grid-template-columns:repeat(6,1fr);gap:6px;padding:0 12px 12px}.cfb18-mini{background:#09131d;border:1px solid #1b2d3f;border-radius:10px;padding:7px;text-align:center}.cfb18-lab{font-size:7px;color:#7f93a7;text-transform:uppercase;font-weight:900}.cfb18-val{font-size:12px;font-weight:950;margin-top:2px}.cfb18-tags{padding:0 12px 12px;font-size:9px;color:#9fb0c1}
.cfb18-card{--team:#2f81f7;background:radial-gradient(circle at 0 0,color-mix(in srgb,var(--team) 23%,transparent),transparent 32%),linear-gradient(145deg,#07111b,#050a10);border:1px solid color-mix(in srgb,var(--team) 55%,#24364a);border-left:4px solid var(--team);border-radius:18px;padding:12px;margin:8px 0}.cfb18-ident{display:grid;grid-template-columns:30px 48px minmax(0,1fr) auto;gap:8px;align-items:center}.cfb18-rank{width:28px;height:28px;border-radius:9px;background:#142132;border:1px solid #2c4056;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:950}.cfb18-logo{width:46px;height:46px;object-fit:contain}.cfb18-name{font-size:18px;font-weight:1000;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cfb18-sub{font-size:9px;color:#8ea2b5;text-transform:uppercase;font-weight:800}.cfb18-status{font-size:9px;font-weight:950;border:1px solid #2c4056;border-radius:999px;padding:5px 8px}.cfb18-market{display:grid;grid-template-columns:1.25fr repeat(4,.72fr);gap:6px;margin-top:9px}.cfb18-main,.cfb18-stat{background:#08121c;border:1px solid #192c3e;border-radius:10px;padding:7px;text-align:center}.cfb18-main .cfb18-val{font-size:20px}.cfb18-probval{color:#64ed91}.cfb18-why{border-top:1px solid #17283a;margin-top:8px;padding-top:7px;color:#a3b4c4;font-size:9px;line-height:1.35}
.cfb18-fast{display:grid;gap:7px}.cfb18-row{--team:#2f81f7;display:grid;grid-template-columns:40px minmax(120px,1.4fr) minmax(105px,1fr) 70px 75px 75px 70px;gap:7px;align-items:center;background:#08121b;border:1px solid #1b2d3d;border-left:3px solid var(--team);border-radius:12px;padding:8px 9px}.cfb18-row img{width:36px;height:36px;object-fit:contain}.cfb18-rowname{font-size:13px;font-weight:950}.cfb18-rowsub{font-size:8px;color:#869bad}.cfb18-cell{text-align:center}.cfb18-cell b{display:block;font-size:12px}.cfb18-cell span{font-size:7px;color:#7e92a5;text-transform:uppercase;font-weight:900}.cfb18-side-over{color:#55e991!important}.cfb18-side-under{color:#ff6f7d!important}.cfb18-logo-wrap{width:36px;height:36px;display:flex;align-items:center;justify-content:center}.cfb18-logo-fallback{width:30px;height:30px;border-radius:50%;background:#142131;border:1px solid #2a3d50;display:flex;align-items:center;justify-content:center;font-size:8px;font-weight:900;color:#9cb0c3}
@media(max-width:620px){.cfb18-mlgrid{grid-template-columns:1fr .92fr 1fr;padding:10px 7px}.cfb18-team img{width:46px;height:46px}.cfb18-win img{width:52px;height:52px}.cfb18-teamname{font-size:12px}.cfb18-points{font-size:19px}.cfb18-winprob{font-size:24px}.cfb18-mlmetrics{grid-template-columns:repeat(2,1fr)}.cfb18-ident{grid-template-columns:26px 40px minmax(0,1fr) auto}.cfb18-logo{width:38px;height:38px}.cfb18-name{font-size:15px}.cfb18-market{grid-template-columns:1.2fr 1fr;}.cfb18-row{grid-template-columns:34px minmax(105px,1.5fr) 88px 58px 62px}.cfb18-row .hide-mobile{display:none}.cfb18-row img{width:30px;height:30px}.cfb18-cell b{font-size:11px}}
</style>''',unsafe_allow_html=True)

def render_moneyline_nfl(g:dict,ctx:Dict[str,dict]):
    away=str(g.get('away') or ''); home=str(g.get('home') or ''); fav=str(g.get('favorite') or (home if _num(g.get('home_win_prob'))>=.5 else away))
    al=_logo(ctx,away); hl=_logo(ctx,home); fl=_logo(ctx,fav)
    ac=_color(ctx,away); hc=_color(ctx,home); fc=_color(ctx,fav)
    awp=_pct(g.get('away_win_prob')); hwp=_pct(g.get('home_win_prob')); fwp=max(awp,hwp)
    tags=' • '.join(str(x) for x in (g.get('tags') or []))
    spread_edge='—' if g.get('market_home_spread') is None else f"{_num(g.get('model_home_margin'))+_num(g.get('market_home_spread')):+.1f}"
    total_edge='—' if g.get('market_total') is None else f"{_num(g.get('model_total'))-_num(g.get('market_total')):+.1f}"
    def im(src,name): return f"<img src='{html.escape(src,quote=True)}' alt='{html.escape(name)} logo' loading='lazy' onerror=\"this.style.display='none'\">" if src else ''
    st.markdown(f'''<section class="cfb18-ml" style="--away:{ac};--home:{hc};--winner:{fc}"><div class="cfb18-top"><span>{html.escape(away)} @ {html.escape(home)}</span><span>CFB MONEYLINE · MODEL</span></div><div class="cfb18-mlgrid"><div class="cfb18-team">{im(al,away)}<div class="cfb18-teamname">{html.escape(_abbr(ctx,away))}</div><div class="cfb18-points">{_fmt(g.get('away_points'))}</div><div class="cfb18-prob">{awp:.1f}% WIN</div></div><div class="cfb18-win"><div class="cfb18-winkicker">★ MODEL WINNER ★</div>{im(fl,fav)}<div class="cfb18-winname">{html.escape(fav)}</div><div class="cfb18-winprob">{fwp:.1f}%</div><div class="cfb18-prob">Projected margin {_fmt(abs(_num(g.get('model_home_margin'))))}</div></div><div class="cfb18-team">{im(hl,home)}<div class="cfb18-teamname">{html.escape(_abbr(ctx,home))}</div><div class="cfb18-points">{_fmt(g.get('home_points'))}</div><div class="cfb18-prob">{hwp:.1f}% WIN</div></div></div><div class="cfb18-mlmetrics"><div class="cfb18-mini"><div class="cfb18-lab">Model Spread</div><div class="cfb18-val">{(-_num(g.get('model_home_margin'))):+.1f}</div></div><div class="cfb18-mini"><div class="cfb18-lab">Model Total</div><div class="cfb18-val">{_fmt(g.get('model_total'))}</div></div><div class="cfb18-mini"><div class="cfb18-lab">Spread Edge</div><div class="cfb18-val">{spread_edge}</div></div><div class="cfb18-mini"><div class="cfb18-lab">Total Edge</div><div class="cfb18-val">{total_edge}</div></div><div class="cfb18-mini"><div class="cfb18-lab">Blowout</div><div class="cfb18-val">{html.escape(str(g.get('blowout_level') or 'LOW'))} {_pct(g.get('blowout_prob')):.0f}%</div></div><div class="cfb18-mini"><div class="cfb18-lab">Hook Risk</div><div class="cfb18-val">{_pct(g.get('coach_hook_aggression')):.0f}%</div></div></div><div class="cfb18-tags">{html.escape(tags)}</div></section>''',unsafe_allow_html=True)

def render_player_nfl(r:dict,ctx:Dict[str,dict],game:dict,rank:int=1):
    team=str(r.get('team') or ''); opp=str(r.get('opp') or ''); logo=_logo(ctx,team); color=_color(ctx,team); side=str(r.get('side') or 'Over'); status=str(r.get('status') or 'TRACK')
    logo_html=f"<img class='cfb18-logo' src='{html.escape(logo,quote=True)}' alt='{html.escape(team)} logo' loading='lazy' onerror=\"this.style.display='none'\">" if logo else '<div></div>'
    notes=html.escape(str(r.get('notes') or 'No extra flags'))
    st.markdown(f'''<section class="cfb18-card" style="--team:{color}"><div class="cfb18-ident"><div class="cfb18-rank">#{rank}</div>{logo_html}<div><div class="cfb18-name">{html.escape(str(r.get('player') or ''))}</div><div class="cfb18-sub">{html.escape(team)} VS {html.escape(opp)} · {html.escape(str(r.get('matchup') or game.get('away','')+' @ '+game.get('home','')))}</div></div><div class="cfb18-status">{html.escape(status)}</div></div><div class="cfb18-market"><div class="cfb18-main"><div class="cfb18-lab">{html.escape(str(r.get('prop') or 'PROP'))}</div><div class="cfb18-val {'cfb18-side-over' if side.lower()=='over' else 'cfb18-side-under'}">{html.escape(side.upper())} {_fmt(r.get('line'))}</div></div><div class="cfb18-stat"><div class="cfb18-lab">Projection</div><div class="cfb18-val">{_fmt(r.get('projection'))}</div></div><div class="cfb18-stat"><div class="cfb18-lab">Edge</div><div class="cfb18-val">{_num(r.get('edge')):+.1f}</div></div><div class="cfb18-stat"><div class="cfb18-lab">Likely</div><div class="cfb18-val cfb18-probval">{_pct(r.get('probability')):.1f}%</div></div><div class="cfb18-stat"><div class="cfb18-lab">Model SD</div><div class="cfb18-val">{_fmt(r.get('sd'))}</div></div></div><div class="cfb18-why"><b>GAME:</b> {html.escape(str(game.get('away') or ''))} {_fmt(game.get('away_points'))} — {_fmt(game.get('home_points'))} {html.escape(str(game.get('home') or ''))} · Total {_fmt(game.get('model_total'))}<br><b>BLOWOUT:</b> {html.escape(str(r.get('blowout_level') or game.get('blowout_level') or 'LOW'))} {_pct(r.get('blowout_prob',game.get('blowout_prob'))):.0f}% · Starter retention {_pct(r.get('starter_retention',1)):.0f}% · Backup opp {_pct(r.get('backup_opportunity',game.get('backup_opportunity'))):.0f}%<br><b>WHY:</b> {notes}</div></section>''',unsafe_allow_html=True)

def render_fast_rows(rows:List[dict],ctx:Dict[str,dict],limit:int=60):
    if not rows:
        st.info('No projected player rows in this view.'); return
    bits=['<div class="cfb18-fast">']
    for i,r in enumerate(rows[:limit],1):
        team=str(r.get('team') or ''); logo=_logo(ctx,team); color=_color(ctx,team); opp=str(r.get('opp') or '')
        abbr=_abbr(ctx,team); side=str(r.get('side') or 'Over'); side_cls='cfb18-side-over' if side.lower()=='over' else 'cfb18-side-under'
        lg=(f"<div class='cfb18-logo-wrap'><img src='{html.escape(logo,quote=True)}' alt='{html.escape(team)} logo' loading='lazy' onerror=\"this.style.display='none'\"></div>" if logo else f"<div class='cfb18-logo-wrap'><div class='cfb18-logo-fallback'>{html.escape(abbr[:4])}</div></div>")
        bits.append(f'''<div class="cfb18-row" style="--team:{color}">{lg}<div><div class="cfb18-rowname">#{i} {html.escape(str(r.get('player') or ''))}</div><div class="cfb18-rowsub">{html.escape(team)} VS {html.escape(opp)} · {html.escape(str(r.get('blowout_level') or 'LOW'))} BLOWOUT</div></div><div class="cfb18-cell"><span>Prop</span><b>{html.escape(str(r.get('prop') or ''))}</b></div><div class="cfb18-cell"><span>Line</span><b class="{side_cls}">{html.escape(side.upper())} {_fmt(r.get('line'))}</b></div><div class="cfb18-cell"><span>Proj</span><b>{_fmt(r.get('projection'))}</b></div><div class="cfb18-cell hide-mobile"><span>Edge</span><b>{_num(r.get('edge')):+.1f}</b></div><div class="cfb18-cell hide-mobile"><span>Likely</span><b>{_pct(r.get('probability')):.0f}%</b></div></div>''')
    bits.append('</div>'); st.markdown(''.join(bits),unsafe_allow_html=True)
