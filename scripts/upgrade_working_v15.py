from pathlib import Path
p=Path('app.py'); s=p.read_text()
s=s.replace('from free_data import load_free_stack','from free_data_v15 import load_free_stack')
s=s.replace('from underdog_cfb import fetch_underdog_cfb_props, props_for_game','from underdog_cfb_v15 import fetch_underdog_cfb_props, props_for_game')
s=s.replace('APP_VERSION = "CFB Prop Engine v1.4 — LIVE UNDERDOG CFB + ELITE PLAYER CARDS"','APP_VERSION = "CFB Prop Engine v1.5 — WORKING LIVE CFB BOARD"')
# Correct week calculation for the late-August CFB start. Sep 5, 2026 => Week 2.
s=s.replace('def_week=max(1,min(16,int((now.timetuple().tm_yday-230)/7)+1))','def_week=max(1,min(16,int((now.timetuple().tm_yday-239)/7)+1))')
# Remove stale paid-API wording and deprecation noise in touched UI.
s=s.replace('st.write("Odds paid API", "✅ optional" if odds.ready else "⚪ not needed — enter player lines manually")','st.write("Player lines", "✅ Underdog Live (free)" if not odds.ready else "✅ Underdog Live + optional Odds API")')
s=s.replace('Power board populates after CFBD data loads.','Power board populates after the free CFB data stack loads.')
s=s.replace('use_container_width=True','width="stretch"')
# Load the Underdog board independently of the selected schedule game so schedule name/week mismatch cannot blank Players.
old='''    game_labels=[f"{g['away']} @ {g['home']}" for g in week_games]\n    selected_label=st.selectbox("Game",game_labels) if game_labels else None\n    selected_game=week_games[game_labels.index(selected_label)] if selected_label in game_labels else None\n    live_sources=["Underdog Live"] + (["Live Odds API"] if odds.ready else []) + ["Manual"]\n    source=st.radio("Prop lines",live_sources,horizontal=True)\n    prop_rows=[]\n    if selected_game and source=="Underdog Live":'''
new='''    game_labels=["ALL LIVE CFB PROPS"]+[f"{g['away']} @ {g['home']}" for g in week_games]\n    selected_label=st.selectbox("Game / board",game_labels,index=0)\n    selected_game=None if selected_label=="ALL LIVE CFB PROPS" else week_games[[f"{g['away']} @ {g['home']}" for g in week_games].index(selected_label)]\n    live_sources=["Underdog Live"] + (["Live Odds API"] if odds.ready else []) + ["Manual"]\n    source=st.radio("Prop lines",live_sources,horizontal=True)\n    prop_rows=[]\n    if source=="Underdog Live":'''
if old not in s: raise SystemExit('player header block not found')
s=s.replace(old,new,1)
# Make Underdog filtering optional: ALL uses full board, selected game uses game filter.
s=s.replace('''            ud_rows=st.session_state.get("ud_cfb_rows",[])\n            prop_rows=props_for_game(ud_rows,selected_game["away"],selected_game["home"])''','''            ud_rows=st.session_state.get("ud_cfb_rows",[])\n            prop_rows=list(ud_rows) if selected_game is None else props_for_game(ud_rows,selected_game["away"],selected_game["home"])''',1)
# Only execute player-bank selected-game fallback when a game is selected.
s=s.replace('''            if not prop_rows:\n                game_players=set()''','''            if not prop_rows and selected_game is not None:\n                game_players=set()''',1)
# Better caption for all-board mode.
s=s.replace('''                st.caption(f"Underdog live board: {len(ud_rows)} CFB lines pulled · {len(prop_rows)} matching this game")''','''                scope="all live CFB props" if selected_game is None else "matching this game"\n                st.caption(f"Underdog live board: {len(ud_rows)} CFB lines pulled · {len(prop_rows)} {scope}")''',1)
# Project ALL-board props by finding their game from live line metadata; skip only when no matchup can be resolved.
old2='''    projected=[]\n    if selected_game and prop_rows:\n        for r in prop_rows:\n            pr=lookup_player(players,r.get("player",""))'''
new2='''    projected=[]\n    if prop_rows:\n        for r in prop_rows:\n            row_game=selected_game\n            if row_game is None:\n                ra,rh=norm_name(r.get("away")),norm_name(r.get("home"))\n                for gg in week_games:\n                    if (ra and rh and ((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"])))):\n                        row_game=gg; break\n                if row_game is None:\n                    # Build a neutral placeholder game so the live line still appears instead of blanking the board.\n                    away=r.get("away") or "Away"; home=r.get("home") or "Home"\n                    row_game=project_game(away,home,ctx,{},neutral=True)\n                    row_game["weather"]={}\n            pr=lookup_player(players,r.get("player",""))'''
if old2 not in s: raise SystemExit('projection start block not found')
s=s.replace(old2,new2,1)
# Change all per-row selected_game references in the projection/render block to row_game, but only in slice before TAB_DATA.
start=s.index('    projected=[]',s.index('with TAB_PLAYERS:')); end=s.index('\nwith TAB_DATA:',start); block=s[start:end]; block=block.replace('selected_game["away"]','row_game["away"]').replace('selected_game["home"]','row_game["home"]').replace('selected_game.get("weather",{})','row_game.get("weather",{})').replace('player_projection(pr,r.get("prop"),tc,oc,selected_game,team or "")','player_projection(pr,r.get("prop"),tc,oc,row_game,team or "")').replace('render_player_card(rr,ctx,selected_game)','render_player_card(rr,ctx,rr.get("_game") or row_game)')
# Store game on each projected row so sorted cards keep correct matchup.
block=block.replace('q={**r,"team":team,"opp":opp,','q={**r,"_game":row_game,"team":team,"opp":opp,')
s=s[:start]+block+s[end:]
# Avoid JSON serialization problems from embedded _game when saving/showing.
s=s.replace('path.write_text(json.dumps(projected,indent=2,default=str))','path.write_text(json.dumps([{k:v for k,v in x.items() if k!="_game"} for x in projected],indent=2,default=str))')
# Data-health line that makes actual live state visible.
s=s.replace('st.success(f"Active source: {data_mode}")','st.success(f"Active source: {data_mode} · Games: {len(week_games)} · Players: {len(players) if players is not None else 0}")')
p.write_text(s)
