from pathlib import Path

p=Path('app.py')
s=p.read_text()

old_imp='from cfb_nfl_ui_v18 import hydrate_team_branding, inject_nfl_cfb_css, render_moneyline_nfl, render_player_nfl, render_fast_rows\n'
new_imp=old_imp+'from cfb_runtime_v19 import annotate_games, ensure_branding, filter_games_by_scope, filter_props_by_scope, local_now, scope_target_date, logo_coverage\n'
if 'from cfb_runtime_v19 import ' not in s:
    if old_imp not in s:
        raise SystemExit('v18 ui import not found')
    s=s.replace(old_imp,new_imp,1)

s=s.replace('APP_VERSION = "CFB Prop Engine v1.8 — NFL-STYLE MONEYLINE + FAST ROWS"','APP_VERSION = "CFB Prop Engine v1.9 — DAY-AWARE + LOGO-LOCKED FAST BOARD"')

old='''ctx=hydrate_team_branding(ctx)\ninject_nfl_cfb_css()\nactive_week='''
new='''ctx=hydrate_team_branding(ctx)\nctx=ensure_branding(ctx,bundle.get("games",[]),players)\ninject_nfl_cfb_css()\nactive_week='''
if old not in s:
    raise SystemExit('branding anchor not found')
s=s.replace(old,new,1)

# Add local day awareness and a compact slate switch immediately after game construction.
anchor='''    week_games.append(pg)\n\nTAB_EVENTS,TAB_PLAYERS,TAB_RANK,TAB_DATA,TAB_GRADE=st.tabs(["Events","Players","Power Board","Data Health","Save + Grade"])'''
replacement='''    week_games.append(pg)\n\nweek_games=annotate_games(week_games)\npt_now=local_now()\nslate_scope=st.radio("Slate",["Today","Tomorrow","All Week"],horizontal=True,index=0,label_visibility="collapsed",key="cfb_slate_scope")\ntarget_date=scope_target_date(slate_scope,pt_now)\ndisplay_games=filter_games_by_scope(week_games,slate_scope,pt_now)\nslate_label=(target_date.strftime("%A, %B %-d") if target_date else f"Week {active_week}")\nst.markdown(f"<div class='cfb-live-strip'><b>{slate_scope}</b> · {slate_label} · {len(display_games)} games · {pt_now.strftime('%-I:%M %p PT')}</div>",unsafe_allow_html=True)\n\nTAB_EVENTS,TAB_PLAYERS,TAB_RANK,TAB_DATA,TAB_GRADE=st.tabs(["🏟️ Games","⚡ Player Props","Power","Data","Grade"])'''
if anchor not in s:
    raise SystemExit('tab anchor not found')
s=s.replace(anchor,replacement,1)

# Events should show only the chosen local day, grouped cleanly.
s=s.replace('''    if not week_games: st.info("No games loaded for this week yet. Try Refresh or a different week.")\n    else:\n        for g in sorted(week_games,key=lambda x:x.get("start_date") or ""):\n            render_moneyline_nfl(g,ctx)''','''    if not display_games:\n        st.info(f"No games on {slate_label}. Switch to Tomorrow or All Week.")\n    else:\n        for g in sorted(display_games,key=lambda x:x.get("start_date") or ""):\n            render_moneyline_nfl(g,ctx)''',1)

# Player game selector follows the same day scope.
old_game='''    game_labels=["ALL LIVE CFB PROPS"]+[f"{g['away']} @ {g['home']}" for g in week_games]\n    selected_label=st.selectbox("Game / board",game_labels,index=0)\n    selected_game=None if selected_label=="ALL LIVE CFB PROPS" else week_games[[f"{g['away']} @ {g['home']}" for g in week_games].index(selected_label)]'''
new_game='''    game_labels=["ALL LIVE CFB PROPS"]+[f"{g['away']} @ {g['home']}" for g in display_games]\n    selected_label=st.selectbox("Game / board",game_labels,index=0)\n    selected_game=None if selected_label=="ALL LIVE CFB PROPS" else display_games[[f"{g['away']} @ {g['home']}" for g in display_games].index(selected_label)]'''
if old_game not in s:
    raise SystemExit('player game selector anchor not found')
s=s.replace(old_game,new_game,1)

# Filter Underdog rows to Today/Tomorrow before market filtering, but preserve All Week.
old_ud='''            ud_rows=st.session_state.get("ud_cfb_rows",[])\n            prop_rows=list(ud_rows) if selected_game is None else props_for_game(ud_rows,selected_game["away"],selected_game["home"])'''
new_ud='''            ud_rows=st.session_state.get("ud_cfb_rows",[])\n            ud_rows=filter_props_by_scope(ud_rows,slate_scope,pt_now)\n            prop_rows=list(ud_rows) if selected_game is None else props_for_game(ud_rows,selected_game["away"],selected_game["home"])'''
if old_ud not in s:
    raise SystemExit('underdog rows anchor not found')
s=s.replace(old_ud,new_ud,1)

# Keep the default screen cleaner: shorter explanations.
s=s.replace('st.caption("Moneyline blends SP+, CORE, SRS, Elo, talent and home field. AP rank is displayed as context only. Totals use offense/defense quality, pace and explosiveness, with market lines only as a small stabilizer/audit.")','st.caption("NFL-style CFB game board · local-day slate · model winner · spread · total")')
s=s.replace('st.caption("Opportunity first: expected attempts/carries/receptions are adjusted by game script, pace, opponent unit strength, explosive/havoc matchup and CFB blowout playing-time risk.")','st.caption("Live CFB lines → matchup + usage → projection → Higher/Lower probability")')

# Add hidden-in-Data QA so logo/data completeness is measurable without cluttering the main board.
health_anchor='''    st.success(f"Active source: {data_mode} · Active Week: {active_week} · Games: {len(week_games)} · Players: {len(players) if players is not None else 0}")'''
health_new='''    brand_health=logo_coverage(ctx,week_games)\n    st.success(f"Active source: {data_mode} · Active Week: {active_week} · Games: {len(week_games)} · Players: {len(players) if players is not None else 0} · Team logos: {brand_health['logos']}/{brand_health['teams']}")\n    if brand_health.get("missing"):\n        st.caption("Missing logo aliases: "+", ".join(brand_health["missing"][:12]))'''
if health_anchor in s:
    s=s.replace(health_anchor,health_new,1)

p.write_text(s)
