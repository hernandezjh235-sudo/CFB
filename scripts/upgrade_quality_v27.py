from pathlib import Path

p=Path('app.py')
s=p.read_text()

s=s.replace(
"from cfb_blowout_v26 import enrich_blowout_context, game_blowout_profile, player_blowout_modifier",
"from cfb_blowout_v26 import enrich_blowout_context, game_blowout_profile, player_blowout_modifier\nfrom cfb_quality_v27 import stabilize_projection, calibrate_probability, status_from_quality")

s=s.replace(
'APP_VERSION = "CFB Prop Engine v2.6 — COACH-AWARE BLOWOUT OPPORTUNITY"',
'APP_VERSION = "CFB Prop Engine v2.7 — LIVE-GAME LOCK + QB VOLUME + QUALITY CALIBRATION"')
s=s.replace(
'APP_VERSION = "CFB Prop Engine v2.4.1 — NFL-STYLE LIVE TEAM + COMPLETE OPPORTUNITY"',
'APP_VERSION = "CFB Prop Engine v2.7 — LIVE-GAME LOCK + QB VOLUME + QUALITY CALIBRATION"')

old='''            row_game=selected_game
            if row_game is None:
                ra,rh=norm_name(r.get("away")),norm_name(r.get("home"))
                for gg in week_games:
                    ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))
                    full_match=(ra and rh and ((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"]))))
                    abbr_match=(ra and rh and ga==ra and gh==rh)
                    player_team_match=(pr_team and norm_name(pr_team) in {norm_name(gg["away"]),norm_name(gg["home"])})
                    if full_match or abbr_match or player_team_match:
                        row_game=gg; break
                if row_game is None:
                    away=r.get("away") or "Away"; home=r.get("home") or "Home"
                    row_game=project_game(away,home,ctx,{},neutral=True)
                    row_game["weather"]={}
'''
new='''            row_game=selected_game
            if row_game is None:
                # v2.7 LIVE-GAME LOCK: the sportsbook event is authoritative for the
                # matchup. Never let a player's prior school select today's game.
                # This fixes transfers such as a current Louisville player carrying
                # an Ohio State production sample into an Ohio State game card.
                ra,rh=norm_name(r.get("away")),norm_name(r.get("home"))
                if ra and rh:
                    for gg in week_games:
                        ga=norm_name(gg.get("away_abbreviation")); gh=norm_name(gg.get("home_abbreviation"))
                        full_match=((norm_name(gg["away"])==ra and norm_name(gg["home"])==rh) or
                                    (ra in norm_name(gg["away"]) and rh in norm_name(gg["home"])))
                        abbr_match=(ga==ra and gh==rh)
                        if full_match or abbr_match:
                            row_game=gg; break
                # Only use historical player-team matching when the live feed truly
                # lacks an event matchup. It is a last-resort fallback, not authority.
                if row_game is None and not (ra and rh) and pr_team:
                    for gg in week_games:
                        if norm_name(pr_team) in {norm_name(gg["away"]),norm_name(gg["home"])}:
                            row_game=gg; break
                if row_game is None:
                    away=r.get("away") or "Away"; home=r.get("home") or "Home"
                    row_game=project_game(away,home,ctx,{},neutral=True)
                    row_game["weather"]={}
                    row_game["live_event_fallback"]=True
'''
if old not in s:
    raise SystemExit('row_game block not found')
s=s.replace(old,new)

old2='''            p=prop_probability(proj,r.get("line"),sd,side)
            # Reliability calibration. Early CFB samples and prior-season role changes
            # should never print fake 98-100% certainty. Keep direction/edge intact
            # while widening uncertainty until current-season opportunity is proven.
            src=str(model_pr.get("sample_source") or "fallback").lower(); gp=sf(model_pr.get("games"),0)
            roster_confirmed=bool(model_pr.get('current_team')) or src=='current'
            transferred=bool(model_pr.get('current_team') and model_pr.get('team') and norm_name(model_pr.get('current_team'))!=norm_name(model_pr.get('team')))
            has_adv=any(sf(model_pr.get(k))>0 for k in ['adv_pass_att','adv_rush_car','adv_targets'])
            if src=="current": pcap=.74 if gp<=1 else (.82 if gp<=3 else .88)
            elif src=="prior": pcap=.72 if roster_confirmed else .64
            elif src=="roster": pcap=.62
            else: pcap=.62
            if has_adv and roster_confirmed: pcap=min(.84,pcap+.03)
            if transferred: pcap=min(pcap,.68)
            if not roster_confirmed: pcap=min(pcap,.64)
            p=min(max(p,1-pcap),pcap)
            edge=proj-sf(r.get("line")); edge = edge if side=="Over" else -edge
            status="PLAYABLE" if p>=.60 and proj>0 else "LEAN" if p>=.56 and proj>0 else "TRACK"
            if src in {'roster','fallback'} and not has_adv: status='TRACK'
            if transferred: notes.append('transfer/current-role uncertainty')
            if roster_confirmed: notes.append('current roster confirmed')
            if has_adv: notes.append('2026 advanced usage available')
'''
new2='''            # v2.7 fixes two live-slate failure modes from Sep. 6:
            # 1) confirmed QB1 projections collapsing from stale backup history; and
            # 2) gigantic WR/RB edges receiving automatic max confidence without
            #    current opportunity evidence. Neither correction uses the prop line
            #    to manufacture a projection.
            proj,sd,qproj_notes=stabilize_projection(proj,sd,model_pr,r.get("prop"),tc,row_game)
            notes.extend(qproj_notes)
            raw_p=prop_probability(proj,r.get("line"),sd,side)
            p,pcap,qprob_notes,quality_tier=calibrate_probability(raw_p,model_pr,r.get("prop"),tc,row_game,proj,r.get("line"))
            notes.extend(qprob_notes)
            edge=proj-sf(r.get("line")); edge = edge if side=="Over" else -edge
            status=status_from_quality(p,proj,quality_tier,r.get("prop"),model_pr)
            src=str(model_pr.get("sample_source") or "fallback").lower(); gp=sf(model_pr.get("games"),0)
            roster_confirmed=bool(model_pr.get('current_team')) or src=='current'
            transferred=bool(model_pr.get('current_team') and model_pr.get('team') and norm_name(model_pr.get('current_team'))!=norm_name(model_pr.get('team')))
            has_adv=any(sf(model_pr.get(k))>0 for k in ['adv_pass_att','adv_rush_car','adv_targets'])
            if transferred: notes.append('transfer/current-role uncertainty')
            if roster_confirmed: notes.append('current roster confirmed')
            if has_adv: notes.append('2026 advanced usage available')
            notes.append(f'projection quality {quality_tier.lower()}')
'''
if old2 not in s:
    raise SystemExit('probability block not found')
s=s.replace(old2,new2)

old3='''               "blowout_level":row_game.get("blowout_level","LOW"),"blowout_prob":row_game.get("blowout_prob",0),"starter_retention":starter_retention,"backup_opportunity":row_game.get("backup_opportunity",0)}'''
new3='''               "blowout_level":row_game.get("blowout_level","LOW"),"blowout_prob":row_game.get("blowout_prob",0),"starter_retention":starter_retention,"backup_opportunity":row_game.get("backup_opportunity",0),
               "quality_tier":quality_tier,"probability_cap":pcap,"live_game_locked":bool(r.get("away") and r.get("home"))}'''
if old3 not in s:
    raise SystemExit('q dict block not found')
s=s.replace(old3,new3)

# Make Data Readiness reflect the live quality controls instead of only legacy empty bundle lists.
s=s.replace(
'st.code("SportsDataverse/NCAA + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog live lines → CFB opportunity/hook/pressure/explosive engine → projection → Higher/Lower probability + edge → save/grade",language="text")',
'st.code("SportsDataverse/NCAA + current rosters + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog event lock → opportunity/hook/pressure/explosive engine → QB volume floor + role-quality calibration → Higher/Lower probability + edge → save/grade",language="text")')

p.write_text(s)
print('v2.7 quality upgrade applied')
