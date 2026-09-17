from pathlib import Path

app=Path('app.py')
s=app.read_text()
s=s.replace('CFB Prop Engine v3.5 — PROJECTION JOIN + LOGO REPAIR','CFB Prop Engine v3.6 — ZERO-PROJECTION + LOGO FALLBACK')
old='''            model_pr=dict(pr)\n            if team: model_pr['current_team']=team\n            proj,sd,notes=player_projection(model_pr,r.get("prop"),tc,oc,row_game,team or "")\n'''
new='''            model_pr=dict(pr)\n            if team: model_pr['current_team']=team\n            # v3.6: a live QB prop can arrive before the free player-season tables\n            # contain that player's current row. Build an independent TEAM-based QB\n            # opportunity prior instead of emitting a fake 0.0. The sportsbook line\n            # is never used to create this projection. Low-confidence calibration\n            # downstream still prevents this fallback from being treated like a full sample.\n            market_label=str(r.get("prop") or "")\n            if not model_pr and market_label in {"Passing Yards","Pass Attempts","Completions","Passing TDs","Pass + Rush Yards"}:\n                team_pts=sf(row_game.get('home_points') if team==row_game.get('home') else row_game.get('away_points'),24.0)\n                tpass=sf(tc.get('team_pass_yds_pg')); tatt=sf(tc.get('team_pass_att_pg')); tcomp=sf(tc.get('team_pass_comp_pg')); ttd=sf(tc.get('team_pass_td_pg'))\n                if tpass<=0: tpass=clamp(185.0 + 2.15*team_pts,195.0,285.0)\n                if tatt<=0: tatt=clamp(25.0 + .24*team_pts,27.0,38.0)\n                if tcomp<=0: tcomp=tatt*clamp(.61 + (team_pts-24.0)*.002,.56,.69)\n                if ttd<=0: ttd=clamp(.45 + team_pts/20.0,.8,2.4)\n                model_pr={\n                    'player':r.get('player'),'team':team,'current_team':team,'games':1,\n                    'pass_yds':tpass,'pass_att':tatt,'pass_comp':tcomp,'pass_td':ttd,\n                    'rush_yds':0.0,'rush_att':0.0,'sample_source':'team_role_fallback',\n                    'starter_current':True,'role_depth_conf':.42\n                }\n            proj,sd,notes=player_projection(model_pr,market_label,tc,oc,row_game,team or "")\n            if str(model_pr.get('sample_source') or '')=='team_role_fallback':\n                notes.insert(0,'team QB opportunity fallback — player sample pending')\n                sd=max(sd, max(24.0, proj*.18))\n'''
if old not in s: raise SystemExit('projection insertion point not found')
s=s.replace(old,new)
app.write_text(s)

ui=Path('cfb_nfl_ui_v18.py')
u=ui.read_text()
u=u.replace("al=_logo(ctx,away); hl=_logo(ctx,home); fl=_logo(ctx,fav)","al=str(g.get('away_logo') or _logo(ctx,away)); hl=str(g.get('home_logo') or _logo(ctx,home)); fl=(al if fav==away else hl) or _logo(ctx,fav)")
u=u.replace("team=str(r.get('team') or ''); opp=str(r.get('opp') or ''); logo=_logo(ctx,team); color=_color(ctx,team); side=str(r.get('side') or 'Over'); status=str(r.get('status') or 'TRACK')","team=str(r.get('team') or ''); opp=str(r.get('opp') or ''); game=game or {}; logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _norm(team)==_norm(game.get('away')) else str(game.get('home_logo') or '') if _norm(team)==_norm(game.get('home')) else ''); color=_color(ctx,team); side=str(r.get('side') or 'Over'); status=str(r.get('status') or 'TRACK')")
# Fast-row cards carry their game object on each projected row.
old_fast="logo=_logo(ctx,team); color=_color(ctx,team)"
new_fast="game=r.get('_game') or {}; logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _norm(team)==_norm(game.get('away')) else str(game.get('home_logo') or '') if _norm(team)==_norm(game.get('home')) else ''); color=_color(ctx,team)"
if old_fast in u: u=u.replace(old_fast,new_fast)
ui.write_text(u)
print('v3.6 repair applied')