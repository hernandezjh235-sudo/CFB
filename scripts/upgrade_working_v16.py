from pathlib import Path
p=Path('app.py'); s=p.read_text()
s=s.replace('from free_data_v15 import load_free_stack','from free_data_v16 import load_free_stack')
s=s.replace('APP_VERSION = "CFB Prop Engine v1.5 — WORKING LIVE CFB BOARD"','APP_VERSION = "CFB Prop Engine v1.6 — LIVE CFB BOARD + CURRENT SLATE"')
# Resolve the true live week from the source itself. Free feed currently reports current 2026 slate as week 1.
anchor='''injuries_df=load_optional_csv("injuries.csv")\ndepth_df=load_optional_csv("depth_chart.csv")\ngame_context_df=load_optional_csv("game_context.csv")'''
repl='''active_week=int(bundle.get("resolved_week",week)) if isinstance(bundle,dict) else int(week)\nif active_week!=int(week):\n    st.sidebar.info(f"Live source currently labels this slate as Week {active_week}; using that automatically.")\ninjuries_df=load_optional_csv("injuries.csv")\ndepth_df=load_optional_csv("depth_chart.csv")\ngame_context_df=load_optional_csv("game_context.csv")'''
if anchor not in s: raise SystemExit('load anchor missing')
s=s.replace(anchor,repl,1)
s=s.replace('if int(sf(g.get("week"),0))!=int(week): continue','if int(sf(g.get("week"),0))!=int(active_week): continue',1)
# Carry abbreviations into projected game objects for Underdog matching.
s=s.replace('''    pg["game_id"]=g.get("id"); pg["start_date"]=g.get("start_date") or g.get("startDate")\n    week_games.append(pg)''','''    pg["game_id"]=g.get("id"); pg["start_date"]=g.get("start_date") or g.get("startDate")\n    pg["away_abbreviation"]=g.get("away_abbreviation") or g.get("awayAbbreviation") or ""\n    pg["home_abbreviation"]=g.get("home_abbreviation") or g.get("homeAbbreviation") or ""\n    week_games.append(pg)''',1)
# Match live Underdog abbreviations as well as full school names.
old='''                for gg in week_games:\n                    if (ra and rh and ((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"])))):\n                        row_game=gg; break'''
new='''                for gg in week_games:\n                    ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))\n                    full_match=(ra and rh and ((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"]))))\n                    abbr_match=(ra and rh and ga==ra and gh==rh)\n                    if full_match or abbr_match:\n                        row_game=gg; break'''
if old not in s: raise SystemExit('row game matcher missing')
s=s.replace(old,new,1)
# Make live status explicit.
s=s.replace('st.success(f"Active source: {data_mode} · Games: {len(week_games)} · Players: {len(players) if players is not None else 0}")','st.success(f"Active source: {data_mode} · Active Week: {active_week} · Games: {len(week_games)} · Players: {len(players) if players is not None else 0}")')
p.write_text(s)
