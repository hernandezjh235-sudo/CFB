from pathlib import Path

app=Path('app.py')
s=app.read_text()
s=s.replace('CFB Prop Engine v3.4 — PROPLINE ONLY LIVE LINES','CFB Prop Engine v3.5 — PROJECTION JOIN + LOGO REPAIR')
s=s.replace('FREE SportsDataverse + NCAA + LIVE Underdog CFB lines','FREE SportsDataverse + NCAA + PropLine live CFB lines')
s=s.replace('"✅ Auto: Underdog → PropLine" if propline_key else ("✅ Underdog Live (free)" if not odds.ready else "✅ Underdog Live + optional Odds API")','"✅ PropLine Live" if propline_key else ("⚪ add PROPLINE_API_KEY" if not odds.ready else "✅ optional Odds API")')
s=s.replace('SportsDataverse/NCAA + current rosters + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog event lock → opportunity/hook/pressure/explosive engine','SportsDataverse/NCAA + current rosters + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + PropLine event lock → opportunity/hook/pressure/explosive engine')
app.write_text(s)

ui=Path('cfb_nfl_ui_v18.py')
u=ui.read_text()
old="""def _team(ctx,name):
    if name in ctx:return ctx[name]
    n=_norm(name)
    for k,v in (ctx or {}).items():
        if _norm(k)==n:return v
    return {}
"""
new="""def _team(ctx,name):
    if name in ctx:return ctx[name]
    n=_norm(name)
    for k,v in (ctx or {}).items():
        if _norm(k)==n:return v
    # Runtime fallback: PropLine/ESPN can use a display-name variant that is not
    # present in the model context key. Resolve branding directly instead of
    # rendering a blank logo. This changes presentation only, never projections.
    brands=espn_team_branding()
    info=brands.get(n)
    if not info and n:
        hits=[v for k,v in brands.items() if len(k)>=4 and (k in n or n in k)]
        info=hits[0] if len(hits)==1 else None
    return info or {}
"""
if old not in u: raise SystemExit('UI _team block not found')
u=u.replace(old,new)
ui.write_text(u)
print('v3.5 projection/logo repair applied')