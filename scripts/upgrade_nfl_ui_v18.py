from pathlib import Path
p=Path('app.py'); s=p.read_text()

imp='from cfb_nfl_ui_v18 import hydrate_team_branding, inject_nfl_cfb_css, render_moneyline_nfl, render_player_nfl, render_fast_rows\n'
anchor='from underdog_cfb_v15 import fetch_underdog_cfb_props, props_for_game\n'
if imp not in s:
    s=s.replace(anchor,anchor+imp,1)

s=s.replace('APP_VERSION = "CFB Prop Engine v1.7 — NFL-STYLE LIVE PLAYER BOARD"','APP_VERSION = "CFB Prop Engine v1.8 — NFL-STYLE MONEYLINE + FAST ROWS"')

# Brand both paid and free team contexts from ESPN public team metadata.
old='''    else:\n        bundle,ctx,players,market_map=load_free_stack(int(year),int(week))\n        data_mode="FREE SportsDataverse/NCAA"\nactive_week='''
new='''    else:\n        bundle,ctx,players,market_map=load_free_stack(int(year),int(week))\n        data_mode="FREE SportsDataverse/NCAA"\nctx=hydrate_team_branding(ctx)\ninject_nfl_cfb_css()\nactive_week='''
if old in s:s=s.replace(old,new,1)

s=s.replace('            render_game_card(g)','            render_moneyline_nfl(g,ctx)',1)

old_cards='''            cols=st.columns(2)\n            for i,rr in enumerate(render_rows):\n                with cols[i%2]: render_player_card(rr,ctx,rr.get("_game") or row_game)\n            with st.expander("📋 Compact projection table",expanded=False):'''
new_cards='''            FAST_TAB,CARD_TAB=st.tabs(["⚡ Fast Row","🪪 Player Cards"])\n            with FAST_TAB:\n                render_fast_rows(render_rows,ctx,limit=60)\n            with CARD_TAB:\n                cols=st.columns(2)\n                for i,rr in enumerate(render_rows):\n                    with cols[i%2]: render_player_nfl(rr,ctx,rr.get("_game") or row_game,rank=i+1)\n            with st.expander("📋 Compact projection table",expanded=False):'''
if old_cards not in s:
    raise SystemExit('player render block not found')
s=s.replace(old_cards,new_cards,1)

p.write_text(s)
