from pathlib import Path
p=Path("app.py")
s=p.read_text()
s=s.replace("CFB Prop Engine v3.9 — TRUE WEEK + PLAYER DATA LOCK","CFB Prop Engine v4.0 — LIVE EVENT AUTHORITATIVE")

# Do not rely on empty official week schedule for live board. Reconcile the actual
# PropLine events first, then use those events as the game's identity everywhere.
old="""        raw_prop_games=games_from_props(scoped_boot,ctx)
        for rg in raw_prop_games:
"""
new="""        raw_prop_games=reconcile_prop_games(scoped_boot,ctx)
        for rg in raw_prop_games:
"""
s=s.replace(old,new)

# Preserve authoritative logos/ids instead of rebuilding and losing them.
old="""            pg=project_game(away,home,ctx,market,neutral=bool(manual_gc.get("neutral",False)))
            pg["weather"]={"wind_mph":sf(manual_gc.get("wind_mph")),"precip_prob":sf(manual_gc.get("precip_prob")),"temp_f":sf(manual_gc.get("temp_f"),70)}
            pg["game_id"]=rg.get("id");pg["start_date"]=rg.get("start_date")
            for k in ["away_abbreviation","home_abbreviation","away_espn_id","home_espn_id","away_logo","home_logo"]:pg[k]=rg.get(k) or ""
"""
new="""            pg=project_game(away,home,ctx,market,neutral=bool(manual_gc.get("neutral",False)))
            pg["weather"]={"wind_mph":sf(manual_gc.get("wind_mph")),"precip_prob":sf(manual_gc.get("precip_prob")),"temp_f":sf(manual_gc.get("temp_f"),70)}
            pg["game_id"]=rg.get("game_id") or rg.get("id");pg["start_date"]=rg.get("start_date")
            for k in ["away_abbreviation","home_abbreviation","away_espn_id","home_espn_id","away_logo","home_logo"]:
                pg[k]=rg.get(k) or ""
            # ESPN reconciled event wins for identity and branding.
            pg["event_source"]=rg.get("source") or "PropLine"
"""
s=s.replace(old,new)

# Critical bug: projected player row matching was still doing exact/substring only.
# Reuse reconciled event id first, then canonical team matching.
old="""                if ra and rh:
                    for gg in week_games:
                        ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))
                        full_match=((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or
                                    (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"])))
                        abbr_match=(ga==ra and gh==rh)
                        if full_match or abbr_match:
                            row_game=gg; break
"""
new="""                if ra and rh:
                    rid=str(r.get("event_id") or r.get("game_id") or "")
                    for gg in week_games:
                        gid=str(gg.get("prop_event_id") or gg.get("game_id") or gg.get("id") or "")
                        ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))
                        full_match=((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or
                                    (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"])))
                        abbr_match=(ga==ra and gh==rh)
                        event_match=bool(rid and gid and rid==gid)
                        if event_match or full_match or abbr_match:
                            row_game=gg; break
"""
s=s.replace(old,new)

# Never silently render a zero projection as a real pick.
needle="""            status=status_from_quality(p,proj,quality_tier,r.get("prop"),model_pr)
"""
repl="""            status=status_from_quality(p,proj,quality_tier,r.get("prop"),model_pr)
            if not model_pr or proj<=0:
                p=.50
                quality_tier="UNRESOLVED"
                status="NO PLAY"
                notes.append("player production join unresolved — projection withheld")
"""
s=s.replace(needle,repl)

p.write_text(s)
compile(s,"app.py","exec")
print("v4.0 live-event authoritative patch ready")

# trigger
