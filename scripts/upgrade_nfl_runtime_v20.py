from pathlib import Path
p=Path('app.py');s=p.read_text()

s=s.replace('from cfb_runtime_v19 import annotate_games, ensure_branding, filter_games_by_scope, filter_props_by_scope, local_now, scope_target_date, logo_coverage',
'''from cfb_runtime_v20 import (annotate_games, ensure_branding, filter_games_by_scope, filter_props_by_scope,
    local_now, scope_target_date, logo_coverage, day_games, canonical_prop_team, prop_rows_date_label)''')
s=s.replace('APP_VERSION = "CFB Prop Engine v1.9 — DAY-AWARE + LOGO-LOCKED FAST BOARD"','APP_VERSION = "CFB Prop Engine v2.0 — NFL-STYLE AUTO SLATE + PLAYER BASELINES"')

# Add opening-week/team fallback baselines so a live line never becomes a fake 0 projection.
old='''    pass_y=sf(player.get("pass_yds"))/gp; pass_att=sf(player.get("pass_att"))/gp; comp=sf(player.get("pass_comp"))/gp
    rush_y=sf(player.get("rush_yds"))/gp; rush_att=sf(player.get("rush_att"))/gp
    rec_y=sf(player.get("rec_yds"))/gp; recs=sf(player.get("receptions"))/gp
    pass_td=sf(player.get("pass_td"))/gp; ints=sf(player.get("pass_int"))/gp
'''
new='''    pass_y=sf(player.get("pass_yds"))/gp; pass_att=sf(player.get("pass_att"))/gp; comp=sf(player.get("pass_comp"))/gp
    rush_y=sf(player.get("rush_yds"))/gp; rush_att=sf(player.get("rush_att"))/gp
    rec_y=sf(player.get("rec_yds"))/gp; recs=sf(player.get("receptions"))/gp
    pass_td=sf(player.get("pass_td"))/gp; ints=sf(player.get("pass_int"))/gp
    # NFL-app style opening-week fallback: use independent team production baselines
    # when the player has no current/prior personal sample. The prop line is NOT used
    # to manufacture the projection.
    used_team_prior=False
    if pass_y<=0 and sf(team_ctx.get("team_pass_yds_pg"))>0:
        pass_y=sf(team_ctx.get("team_pass_yds_pg"))*.92; used_team_prior=True
    if pass_att<=0 and sf(team_ctx.get("team_pass_att_pg"))>0:
        pass_att=sf(team_ctx.get("team_pass_att_pg"))*.92; used_team_prior=True
    if comp<=0 and sf(team_ctx.get("team_pass_comp_pg"))>0:
        comp=sf(team_ctx.get("team_pass_comp_pg"))*.92; used_team_prior=True
    if pass_td<=0 and sf(team_ctx.get("team_pass_td_pg"))>0:
        pass_td=sf(team_ctx.get("team_pass_td_pg"))*.88; used_team_prior=True
    if rush_y<=0 and sf(team_ctx.get("team_rush_yds_pg"))>0:
        rush_y=sf(team_ctx.get("team_rush_yds_pg"))*.34; used_team_prior=True
    if rush_att<=0 and sf(team_ctx.get("team_rush_att_pg"))>0:
        rush_att=sf(team_ctx.get("team_rush_att_pg"))*.30; used_team_prior=True
    if rec_y<=0 and sf(team_ctx.get("team_pass_yds_pg"))>0:
        rec_y=sf(team_ctx.get("team_pass_yds_pg"))*.23; used_team_prior=True
    if recs<=0 and sf(team_ctx.get("team_pass_comp_pg"))>0:
        recs=sf(team_ctx.get("team_pass_comp_pg"))*.19; used_team_prior=True
    if used_team_prior:
        notes.append("opening-week team production baseline")
'''
if old not in s:raise SystemExit('projection base block not found')
s=s.replace(old,new,1)

# After day filter, supplement with exact ESPN calendar-date games just like NFL schedule handling.
old='''display_games=filter_games_by_scope(week_games,slate_scope,pt_now)
slate_label=(target_date.strftime("%A, %B %-d") if target_date else f"Week {active_week}")
st.markdown(f"<div class='cfb-live-strip'><b>{slate_scope}</b> · {slate_label} · {len(display_games)} games · {pt_now.strftime('%-I:%M %p PT')}</div>",unsafe_allow_html=True)
'''
new='''display_games=filter_games_by_scope(week_games,slate_scope,pt_now)
# SportsDataverse may lag the next calendar day even while Underdog has lines open.
# Pull the exact ESPN date and project any missing games into the same board.
if slate_scope in {"Today","Tomorrow"}:
    raw_day=day_games(slate_scope,bundle.get("games",[]),pt_now)
    have={(norm_name(g.get("away")),norm_name(g.get("home"))) for g in week_games}
    for rg in raw_day:
        away=rg.get("away_team") or rg.get("awayTeam"); home=rg.get("home_team") or rg.get("homeTeam")
        key=(norm_name(away),norm_name(home))
        if not away or not home or key in have:continue
        market=market_map.get(key,{})
        manual_gc=game_weather_context(away,home,game_context_df)
        pg=project_game(away,home,ctx,market,neutral=bool(rg.get("neutral_site") or rg.get("neutralSite") or manual_gc.get("neutral",False)))
        pg["weather"]={"wind_mph":sf(manual_gc.get("wind_mph")),"precip_prob":sf(manual_gc.get("precip_prob")),"temp_f":sf(manual_gc.get("temp_f"),70)}
        pg["game_id"]=rg.get("id");pg["start_date"]=rg.get("start_date") or rg.get("startDate")
        pg["away_abbreviation"]=rg.get("away_abbreviation") or "";pg["home_abbreviation"]=rg.get("home_abbreviation") or ""
        pg["away_espn_id"]=rg.get("away_espn_id") or "";pg["home_espn_id"]=rg.get("home_espn_id") or ""
        pg["away_logo"]=rg.get("away_logo") or "";pg["home_logo"]=rg.get("home_logo") or ""
        week_games.append(pg);have.add(key)
    week_games=annotate_games(week_games)
    display_games=filter_games_by_scope(week_games,slate_scope,pt_now)
ctx=ensure_branding(ctx,week_games,players)
slate_label=(target_date.strftime("%A, %B %-d") if target_date else f"Week {active_week}")
st.markdown(f"<div class='cfb-live-strip'><b>{slate_scope}</b> · {slate_label} · {len(display_games)} games · {pt_now.strftime('%-I:%M %p PT')}</div>",unsafe_allow_html=True)
'''
if old not in s:raise SystemExit('day display block not found')
s=s.replace(old,new,1)

# Once live lines arrive, hydrate their abbreviations/logos against the active game slate.
old='''            ud_rows=st.session_state.get("ud_cfb_rows",[])
            ud_rows=filter_props_by_scope(ud_rows,slate_scope,pt_now)
            prop_rows=list(ud_rows) if selected_game is None else props_for_game(ud_rows,selected_game["away"],selected_game["home"])
'''
new='''            ud_rows=st.session_state.get("ud_cfb_rows",[])
            ud_rows=filter_props_by_scope(ud_rows,slate_scope,pt_now)
            ctx=ensure_branding(ctx,week_games,players,ud_rows)
            prop_rows=list(ud_rows) if selected_game is None else props_for_game(ud_rows,selected_game["away"],selected_game["home"])
'''
if old not in s:raise SystemExit('ud rows block not found')
s=s.replace(old,new,1)

# Replace the abbreviation/team resolution with the shared NFL-style canonical resolver.
old='''            # Infer team from player bank if bookmaker omitted it.
            team=r.get("team") or pr.get("team")
            if team not in {row_game["away"],row_game["home"]}:
                # Prefer the model player-bank school when Underdog uses an abbreviation.
                pr_team=pr.get("team")
                if pr_team in {row_game["away"],row_game["home"]}:
                    team=pr_team
                else:
                    for t in [row_game["away"],row_game["home"]]:
                        if norm_name(team)==norm_name(t) or norm_name(team) in norm_name(t) or norm_name(t) in norm_name(team):
                            team=t; break
'''
new='''            # Resolve Underdog abbreviations to the full school used by the model/game board.
            team=canonical_prop_team(r,row_game,pr)
'''
if old not in s:raise SystemExit('team resolver block not found')
s=s.replace(old,new,1)

# Critical bug: q previously kept side=AUTO even after the model selected Over/Under.
s=s.replace('''q={**r,"_game":row_game,"team":team,"opp":opp,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(notes)}''',
'''q={**r,"_game":row_game,"team":team,"opp":opp,"side":side,"projection":proj,"sd":sd,"probability":p,"edge":edge,"status":status,"notes":" · ".join(notes)}''',1)

p.write_text(s)
