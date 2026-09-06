from pathlib import Path

app=Path('app.py')
s=app.read_text()

s=s.replace("from cfb_opportunity_v25 import enrich_opportunity, automatic_weather\n", "from cfb_opportunity_v25 import enrich_opportunity, automatic_weather\nfrom cfb_blowout_v26 import enrich_blowout_context, game_blowout_profile, player_blowout_modifier\n")
s=s.replace('APP_VERSION = "CFB Prop Engine v2.4.1 — NFL-STYLE LIVE TEAM + COMPLETE OPPORTUNITY"', 'APP_VERSION = "CFB Prop Engine v2.6 — COACH-AWARE BLOWOUT + COMPLETE OPPORTUNITY"')

old='''    ctx,players,opportunity_health=enrich_opportunity(int(year),int(bundle.get("resolved_week",week) if isinstance(bundle,dict) else week),ctx,players)\n    if isinstance(bundle,dict):\n        bundle.setdefault("free_health",{}).update({f"v25_{k}":v for k,v in opportunity_health.items()})\n'''
new='''    ctx,players,opportunity_health=enrich_opportunity(int(year),int(bundle.get("resolved_week",week) if isinstance(bundle,dict) else week),ctx,players)\n    # v2.6 derives coach/rotation behavior from prior-season 21+ point games.\n    # It measures starter concentration rather than inventing a universal substitution rule.\n    ctx,blowout_health=enrich_blowout_context(int(year),ctx)\n    if isinstance(bundle,dict):\n        bundle.setdefault("free_health",{}).update({f"v25_{k}":v for k,v in opportunity_health.items()})\n        bundle.setdefault("free_health",{}).update({f"v26_{k}":v for k,v in blowout_health.items()})\n'''
assert old in s, 'opportunity enrichment block not found'
s=s.replace(old,new,1)

old='''    talent_gap=(sf(h.get("talent"))-sf(a.get("talent")))\n    blowout_p=logistic((abs(model_margin)-17)/5.5 + min(abs(talent_gap)/500,1.2))\n    favorite=home if model_margin>=0 else away\n    tags=[]\n'''
new='''    talent_gap=(sf(h.get("talent"))-sf(a.get("talent")))\n    favorite=home if model_margin>=0 else away\n    # Dedicated CFB blowout engine: projected margin + power/talent gap + explosive\n    # mismatch + underdog drive sustainability + turnover risk + historical coach hook.\n    blow_profile=game_blowout_profile({"away":away,"home":home,"model_home_margin":model_margin,"model_total":total,"favorite":favorite},h,a)\n    blowout_p=sf(blow_profile.get("blowout_prob"))\n    tags=[]\n'''
assert old in s, 'project_game blowout block not found'
s=s.replace(old,new,1)

old='''    if total>=61: tags.append("🔥 SHOOTOUT")\n    if abs(model_margin)>=21: tags.append("⚠️ BLOWOUT RISK")\n    if pace>0.4: tags.append("⚡ FAST PACE")\n'''
new='''    if total>=61: tags.append("🔥 SHOOTOUT")\n    if blow_profile.get("blowout_level") in {"HIGH","EXTREME"}: tags.append(f"⚠️ {blow_profile.get('blowout_level')} BLOWOUT")\n    if sf(blow_profile.get("coach_hook_aggression"))>=.55: tags.append("🔄 EARLY HOOK TEAM")\n    if pace>0.4: tags.append("⚡ FAST PACE")\n'''
assert old in s, 'project_game tag block not found'
s=s.replace(old,new,1)

old='''            "market_home_spread":market.get("market_home_spread"),"market_total":market.get("market_total"),"home_ap":h.get("ap_rank"),"away_ap":a.get("ap_rank"),"home_model_rank":h.get("model_rank"),"away_model_rank":a.get("model_rank")}\n'''
new='''            "market_home_spread":market.get("market_home_spread"),"market_total":market.get("market_total"),"home_ap":h.get("ap_rank"),"away_ap":a.get("ap_rank"),"home_model_rank":h.get("model_rank"),"away_model_rank":a.get("model_rank"),\n            "blowout_level":blow_profile.get("blowout_level"),"coach_hook_aggression":blow_profile.get("coach_hook_aggression"),\n            "qb_starter_retention":blow_profile.get("qb_starter_retention"),"wr1_retention":blow_profile.get("wr1_retention"),"rb1_retention":blow_profile.get("rb1_retention"),\n            "backup_opportunity":blow_profile.get("backup_opportunity"),"underdog_catchup_mult":blow_profile.get("underdog_catchup_mult"),"blowout_components":blow_profile.get("blowout_components",{})}\n'''
assert old in s, 'project_game return block not found'
s=s.replace(old,new,1)

# Remove the two older generic hook taxes so v2.6 is the single source of blowout playing-time adjustments.
old='''    snap_adj=1.0\n    if is_fav and blow>.55:\n        snap_adj=1.0-(blow-.55)*.24\n        notes.append("blowout playing-time tax")\n    elif not is_fav and blow>.60:\n        notes.append("underdog catch-up volume")\n    # CFB starters get pulled much earlier than NFL starters. Use actual QB1 share and\n    # current roster starter status to make the hook tax role-aware.\n    qb1_share=clamp(sf(team_ctx.get('qb1_attempt_share')),0,1)\n    starter_current=bool(player.get('starter_current'))\n    if is_fav and blow>.52 and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Receiving Yards","Receptions","Pass + Rush Yards"}:\n        hook=(blow-.52)*(.32 if qb1_share<.86 else .24)\n        snap_adj*=clamp(1-hook,.76,1.0); notes.append("CFB starter hook/share adjustment")\n    if starter_current: notes.append("current starter confirmed")\n'''
new='''    snap_adj=1.0\n    starter_current=bool(player.get('starter_current'))\n    if starter_current: notes.append("current starter confirmed")\n    if blow>=.55: notes.append("v2.6 coach-aware blowout engine active")\n'''
assert old in s, 'legacy hook block not found'
s=s.replace(old,new,1)

old='''    else:\n        proj=0; sd=1\n    if proj<=0: notes.append("insufficient player sample")\n    return float(max(0,proj)),float(sd),notes\n'''
new='''    else:\n        proj=0; sd=1\n    # Final mean/variance adjustment comes from the dedicated game-state engine.\n    # It is position/market aware: favorite QB/WR hook, RB early-volume vs late hook,\n    # backup rushing opportunity, and underdog catch-up passing/targets.\n    blow_mult,blow_sd,blow_notes,_ret=player_blowout_modifier(player,market_label,game,team_name,team_ctx)\n    proj*=blow_mult; sd*=blow_sd; notes.extend(blow_notes)\n    if proj<=0: notes.append("insufficient player sample")\n    return float(max(0,proj)),float(sd),notes\n'''
assert old in s, 'player projection return block not found'
s=s.replace(old,new,1)

old='''            q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(dict.fromkeys(notes))}\n'''
new='''            _bm,_bsd,_bn,starter_retention=player_blowout_modifier(model_pr,r.get("prop"),row_game,team or "",tc)\n            q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(dict.fromkeys(notes)),\n               "blowout_level":row_game.get("blowout_level","LOW"),"blowout_prob":row_game.get("blowout_prob",0),"starter_retention":starter_retention,"backup_opportunity":row_game.get("backup_opportunity",0)}\n'''
assert old in s, 'projected row block not found'
s=s.replace(old,new,1)

app.write_text(s)

ui=Path('cfb_nfl_ui_v18.py')
u=ui.read_text()
# Moneyline: surface blowout severity and coach hook beside spread/total.
old='''<div class="cfb18-mini"><div class="cfb18-lab">Total Edge</div><div class="cfb18-val">{total_edge}</div></div></div><div class="cfb18-tags">{html.escape(tags)}</div></section>'''
new='''<div class="cfb18-mini"><div class="cfb18-lab">Total Edge</div><div class="cfb18-val">{total_edge}</div></div><div class="cfb18-mini"><div class="cfb18-lab">Blowout</div><div class="cfb18-val">{html.escape(str(g.get('blowout_level') or 'LOW'))} {_pct(g.get('blowout_prob')):.0f}%</div></div><div class="cfb18-mini"><div class="cfb18-lab">Hook Risk</div><div class="cfb18-val">{_pct(g.get('coach_hook_aggression')):.0f}%</div></div></div><div class="cfb18-tags">{html.escape(tags)}</div></section>'''
assert old in u, 'moneyline metrics block not found'
u=u.replace(old,new,1)
# Desktop metric grid can fit 6; mobile rule already collapses to 2.
u=u.replace('grid-template-columns:repeat(4,1fr);gap:6px;padding:0 12px 12px', 'grid-template-columns:repeat(6,1fr);gap:6px;padding:0 12px 12px',1)
old='''<div class="cfb18-why"><b>GAME:</b> {html.escape(str(game.get('away') or ''))} {_fmt(game.get('away_points'))} — {_fmt(game.get('home_points'))} {html.escape(str(game.get('home') or ''))} · Total {_fmt(game.get('model_total'))}<br><b>WHY:</b> {notes}</div></section>'''
new='''<div class="cfb18-why"><b>GAME:</b> {html.escape(str(game.get('away') or ''))} {_fmt(game.get('away_points'))} — {_fmt(game.get('home_points'))} {html.escape(str(game.get('home') or ''))} · Total {_fmt(game.get('model_total'))}<br><b>BLOWOUT:</b> {html.escape(str(r.get('blowout_level') or game.get('blowout_level') or 'LOW'))} {_pct(r.get('blowout_prob',game.get('blowout_prob'))):.0f}% · Starter retention {_pct(r.get('starter_retention',1)):.0f}% · Backup opp {_pct(r.get('backup_opportunity',game.get('backup_opportunity'))):.0f}%<br><b>WHY:</b> {notes}</div></section>'''
assert old in u, 'player why block not found'
u=u.replace(old,new,1)
# Fast rows keep the layout compact but expose the risk in the subline.
old='''<div class="cfb18-rowsub">{html.escape(team)} VS {html.escape(opp)}</div>'''
new='''<div class="cfb18-rowsub">{html.escape(team)} VS {html.escape(opp)} · {html.escape(str(r.get('blowout_level') or 'LOW'))} BLOWOUT</div>'''
assert old in u, 'fast row subline not found'
u=u.replace(old,new,1)
ui.write_text(u)
print('v2.6 blowout upgrade applied')
