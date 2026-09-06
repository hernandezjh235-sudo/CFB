from pathlib import Path
p=Path('app.py'); s=p.read_text()
s=s.replace('APP_VERSION = "CFB Prop Engine v1.6 — LIVE CFB BOARD + CURRENT SLATE"','APP_VERSION = "CFB Prop Engine v1.7 — NFL-STYLE LIVE PLAYER BOARD"')

# Add compact board CSS for immediate live-line visibility.
css='''\n<style>\n.cfb-live-strip{background:#0a1621;border:1px solid #21415d;border-radius:14px;padding:10px 12px;margin:8px 0 12px;font-size:12px;color:#b9cada}.cfb-live-strip b{color:#65f28a}.cfb-raw-card{background:#0b141d;border:1px solid #203141;border-radius:14px;padding:10px 12px;margin:7px 0}.cfb-raw-name{font-weight:900;font-size:15px}.cfb-raw-sub{font-size:10px;color:#8fa4b8}.cfb-raw-line{font-size:20px;font-weight:950;margin-top:3px}\n</style>\n'''
anchor='''def secret(name: str, default: str = "") -> str:'''
if css not in s: s=s.replace(anchor,css+'\n'+anchor,1)

# Default to a single market like the NFL fast board, avoiding rendering 100+ cards on mobile at once.
s=s.replace('''                default_markets=[x for x in ["Passing Yards","Rushing Yards","Receiving Yards","Rush + Rec TDs"] if x in markets]\n                chosen=st.multiselect("Underdog CFB markets",markets,default=default_markets or markets[:4])''','''                preferred=[x for x in ["Passing Yards","Receiving Yards","Rushing Yards","Rush + Rec TDs"] if x in markets]\n                chosen=st.multiselect("Prop market",markets,default=(preferred[:1] if preferred else markets[:1]))''',1)

# Surface live feed counts before model work so user never sees an apparently empty tab while projections compute.
old='''            with c2:\n                scope="all live CFB props" if selected_game is None else "matching this game"\n                st.caption(f"Underdog live board: {len(ud_rows)} CFB lines pulled · {len(prop_rows)} {scope}")'''
new='''            with c2:\n                scope="all live CFB props" if selected_game is None else "matching this game"\n                st.markdown(f"<div class='cfb-live-strip'><b>LIVE BOARD CONNECTED</b> · {len(ud_rows)} CFB lines pulled · {len(prop_rows)} {scope}</div>",unsafe_allow_html=True)\n            if prop_rows:\n                rawdf=pd.DataFrame(prop_rows)\n                rawcols=[c for c in ["player","team","matchup","prop","line","line_status","scheduled_at"] if c in rawdf.columns]\n                with st.expander("📡 Live player lines",expanded=True):\n                    st.dataframe(rawdf[rawcols].head(150),width="stretch",hide_index=True)'''
if old not in s: raise SystemExit('live caption block not found')
s=s.replace(old,new,1)

# Improve model-game resolution using the player bank BEFORE falling back to placeholder teams.
old2='''        for r in prop_rows:\n            row_game=selected_game\n            if row_game is None:\n                ra,rh=norm_name(r.get("away")),norm_name(r.get("home"))\n                for gg in week_games:\n                    ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))\n                    full_match=(ra and rh and ((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"]))))\n                    abbr_match=(ra and rh and ga==ra and gh==rh)\n                    if full_match or abbr_match:\n                        row_game=gg; break\n                if row_game is None:\n                    # Build a neutral placeholder game so the live line still appears instead of blanking the board.\n                    away=r.get("away") or "Away"; home=r.get("home") or "Home"\n                    row_game=project_game(away,home,ctx,{},neutral=True)\n                    row_game["weather"]={}\n            pr=lookup_player(players,r.get("player",""))'''
new2='''        for r in prop_rows:\n            pr=lookup_player(players,r.get("player",""))\n            pr_team=str(pr.get("team") or "")\n            row_game=selected_game\n            if row_game is None:\n                ra,rh=norm_name(r.get("away")),norm_name(r.get("home"))\n                for gg in week_games:\n                    ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))\n                    full_match=(ra and rh and ((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"]))))\n                    abbr_match=(ra and rh and ga==ra and gh==rh)\n                    player_team_match=(pr_team and norm_name(pr_team) in {norm_name(gg["away"]),norm_name(gg["home"])})\n                    if full_match or abbr_match or player_team_match:\n                        row_game=gg; break\n                if row_game is None:\n                    away=r.get("away") or "Away"; home=r.get("home") or "Home"\n                    row_game=project_game(away,home,ctx,{},neutral=True)\n                    row_game["weather"]={}'''
if old2 not in s: raise SystemExit('projection resolution block not found')
s=s.replace(old2,new2,1)

# Prevent a massive 100+ card DOM on iPhone; show the strongest 30 cards and preserve the full compact table.
old3='''            ranked=sorted(projected,key=lambda x:sf(x.get("probability")),reverse=True)\n            cols=st.columns(2)\n            for i,rr in enumerate(ranked):\n                with cols[i%2]: render_player_card(rr,ctx,rr.get("_game") or row_game)'''
new3='''            ranked=sorted(projected,key=lambda x:sf(x.get("probability")),reverse=True)\n            good_ranked=[x for x in ranked if sf(x.get("projection"))>0]\n            render_rows=(good_ranked or ranked)[:30]\n            if len(ranked)>30:\n                st.caption(f"Showing the top {len(render_rows)} model cards for speed · all {len(ranked)} rows remain in the compact table below.")\n            cols=st.columns(2)\n            for i,rr in enumerate(render_rows):\n                with cols[i%2]: render_player_card(rr,ctx,rr.get("_game") or row_game)'''
if old3 not in s: raise SystemExit('render block not found')
s=s.replace(old3,new3,1)

# Visible join diagnostics for the live board.
needle='''        missing=[r.get("player") for r in projected if r.get("projection",0)<=0]\n        if missing: st.warning("No usable player-season sample for: "+", ".join(map(str,missing[:12])))'''
repl='''        matched=sum(1 for r in projected if sf(r.get("projection"))>0)\n        st.caption(f"Model joined {matched}/{len(projected)} selected live lines to usable player production.")\n        missing=[r.get("player") for r in projected if r.get("projection",0)<=0]\n        if missing: st.warning("Live line loaded but no usable projection sample for: "+", ".join(map(str,missing[:12])))'''
if needle not in s: raise SystemExit('missing block not found')
s=s.replace(needle,repl,1)

p.write_text(s)
