from pathlib import Path

p=Path('app.py')
s=p.read_text()

# imports/version
anchor='from cfb_role_v30 import enrich_role_depth, role_adjust_projection, qb_upset_margin_delta\n'
imp=anchor+'from propline_cfb_v31 import fetch_propline_cfb_props, fetch_propline_game_markets, merge_line_feeds\n'
if 'from propline_cfb_v31 import' not in s:
    if anchor not in s: raise SystemExit('import anchor missing')
    s=s.replace(anchor,imp)
s=s.replace('APP_VERSION = "CFB Prop Engine v3.0 — ROLE DEPTH + QB RUSH + UPSET PATH"','APP_VERSION = "CFB Prop Engine v3.1 — ROLE DEPTH + QB UPSET + PROPLINE FALLBACK"')

# provider key next to existing optional APIs
old='cfbd=CFBD(secret("CFBD_API_KEY")); odds=OddsAPI(secret("ODDS_API_KEY"))\n'
new=old+'propline_key=secret("PROPLINE_API_KEY")\n'
if 'propline_key=secret("PROPLINE_API_KEY")' not in s:
    if old not in s: raise SystemExit('provider-key anchor missing')
    s=s.replace(old,new)

# sidebar status
old='    st.write("Player lines", "✅ Underdog Live (free)" if not odds.ready else "✅ Underdog Live + optional Odds API")\n'
new='    st.write("Player lines", "✅ Auto: Underdog → PropLine" if propline_key else ("✅ Underdog Live (free)" if not odds.ready else "✅ Underdog Live + optional Odds API"))\n    st.write("PropLine", "✅ connected fallback" if propline_key else "⚪ add PROPLINE_API_KEY")\n'
if old in s:
    s=s.replace(old,new)

# PropLine game-line backup: fill only missing spread/total records; never overwrite a working primary market.
anchor='ctx=hydrate_team_branding(ctx)\n'
block='''# v3.1 PropLine game-line backup. One cached bulk request fills missing spread/total\n# context without replacing the existing free betting source.\nif propline_key:\n    try:\n        pl_game_map,pl_game_debug=fetch_propline_game_markets(propline_key)\n        for k,rec in pl_game_map.items():\n            cur=market_map.setdefault(k,{})\n            for fld in ("event_id","away","home","market_home_spread","market_total"):\n                if cur.get(fld) in (None,"") and rec.get(fld) not in (None,""):\n                    cur[fld]=rec.get(fld)\n        if isinstance(bundle,dict): bundle["propline_game_debug"]=pl_game_debug\n    except Exception as e:\n        if isinstance(bundle,dict): bundle["propline_game_debug"]={"status":"ERROR","error":str(e)}\n'''
if 'pl_game_map,pl_game_debug=fetch_propline_game_markets' not in s:
    if anchor not in s: raise SystemExit('branding anchor missing')
    s=s.replace(anchor,block+anchor)

# Sources: Auto is default when PropLine key exists, plus explicit provider controls.
old='live_sources=["Underdog Live"] + (["Live Odds API"] if odds.ready else []) + ["Manual"]\n'
new='live_sources=(["Auto Lines","Underdog Live","PropLine Live"] if propline_key else ["Underdog Live"]) + (["Live Odds API"] if odds.ready else []) + ["Manual"]\n'
if old not in s: raise SystemExit('live_sources anchor missing')
s=s.replace(old,new)
s=s.replace('    if source=="Underdog Live":\n','    if source in {"Auto Lines","Underdog Live"}:\n',1)

# Merge PropLine into the automatic board after Underdog fetch, with Underdog first.
old='''            ud_rows=st.session_state.get("ud_cfb_rows",[])\n            ud_rows=filter_props_by_scope(ud_rows,slate_scope,pt_now)\n            ctx=ensure_branding(ctx,week_games,players,ud_rows)\n'''
new='''            ud_rows=st.session_state.get("ud_cfb_rows",[])\n            ud_rows=filter_props_by_scope(ud_rows,slate_scope,pt_now)\n            if source=="Auto Lines" and propline_key:\n                td=target_date.isoformat() if target_date else None\n                pl_rows,pl_debug=fetch_propline_cfb_props(propline_key,target_date=td)\n                st.session_state["propline_cfb_rows"]=pl_rows\n                st.session_state["propline_cfb_debug"]=pl_debug\n                ud_rows=merge_line_feeds(ud_rows,pl_rows)\n            ctx=ensure_branding(ctx,week_games,players,ud_rows)\n'''
if old not in s: raise SystemExit('underdog rows anchor missing')
s=s.replace(old,new,1)

# Make live diagnostics/source table explicit.
s=s.replace('["player","team","matchup","prop","line","line_type","non_discounted_line","line_status","scheduled_at"]','["player","team","matchup","prop","line","source","books","line_type","non_discounted_line","line_status","scheduled_at"]')
s=s.replace('st.markdown(f"<div class=\'cfb-live-strip\'><b>LIVE BOARD CONNECTED</b> · {len(ud_rows)} CFB lines pulled · {len(prop_rows)} {scope}</div>",unsafe_allow_html=True)', 'st.markdown(f"<div class=\'cfb-live-strip\'><b>LIVE BOARD CONNECTED</b> · {len(ud_rows)} CFB lines pulled · {len(prop_rows)} {scope}</div>",unsafe_allow_html=True)')

# Explicit PropLine-only branch before optional Odds API branch.
needle='    elif selected_game and source=="Live Odds API":\n'
plbranch='''    elif source=="PropLine Live":\n        try:\n            td=target_date.isoformat() if target_date else None\n            pl_rows,pl_debug=fetch_propline_cfb_props(propline_key,target_date=td)\n            st.session_state["propline_cfb_rows"]=pl_rows\n            st.session_state["propline_cfb_debug"]=pl_debug\n            ctx=ensure_branding(ctx,week_games,players,pl_rows)\n            prop_rows=list(pl_rows) if selected_game is None else props_for_game(pl_rows,selected_game["away"],selected_game["home"])\n            markets=sorted({str(r.get("prop")) for r in prop_rows if r.get("prop")})\n            if markets:\n                preferred=[x for x in ["Passing Yards","Receiving Yards","Rushing Yards","Passing TDs"] if x in markets]\n                chosen=st.multiselect("Prop market",markets,default=(preferred[:1] if preferred else markets[:1]),key="propline_markets")\n                prop_rows=[r for r in prop_rows if r.get("prop") in chosen]\n            st.markdown(f"<div class='cfb-live-strip'><b>PROPLINE CONNECTED</b> · {len(pl_rows)} standard CFB lines · quota remaining {pl_debug.get('quota',{}).get('X-Daily-Remaining','—')}</div>",unsafe_allow_html=True)\n            if prop_rows:\n                rawdf=pd.DataFrame(prop_rows)\n                rawcols=[c for c in ["player","team","matchup","prop","line","source","books","line_status","scheduled_at"] if c in rawdf.columns]\n                with st.expander("📡 PropLine player lines",expanded=True): st.dataframe(rawdf[rawcols].head(150),width="stretch",hide_index=True)\n            else:\n                st.info("PropLine has no matching standard player lines for this slate yet.")\n                with st.expander("PropLine diagnostics"): st.json(pl_debug)\n        except Exception as e:\n            st.error(f"PropLine CFB pull failed: {e}")\n'''
if 'elif source=="PropLine Live":' not in s:
    if needle not in s: raise SystemExit('Odds API branch anchor missing')
    s=s.replace(needle,plbranch+needle,1)

p.write_text(s)

# .env.example: placeholder only; NEVER publish the user's real key.
e=Path('.env.example')
es=e.read_text() if e.exists() else ''
if 'PROPLINE_API_KEY=' not in es:
    es += '\n# Optional free PropLine fallback for CFB sportsbook/player lines (keep secret in Railway)\nPROPLINE_API_KEY=\n'
e.write_text(es)
print('CFB v3.1 PropLine integration applied')
