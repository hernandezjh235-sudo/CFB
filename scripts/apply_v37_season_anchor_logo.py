from pathlib import Path

app=Path('app.py')
s=app.read_text()
s=s.replace('CFB Prop Engine v3.6 — ZERO-PROJECTION + LOGO FALLBACK','CFB Prop Engine v3.7 — SEASON ANCHOR + LOGO RESTORE')

old_lookup='''def lookup_player(df:pd.DataFrame,name:str)->dict:
    if df is None or df.empty:return {}
    n=norm_name(name)
    exact=df[df["player"].astype(str).map(norm_name)==n]
    if len(exact): return exact.iloc[0].to_dict()
    # Conservative fuzzy fallback: only prefix+surname-like normalized containment.
    hits=df[df["player"].astype(str).map(lambda x:n in norm_name(x) or norm_name(x) in n)]
    return hits.iloc[0].to_dict() if len(hits)==1 else {}
'''
new_lookup='''def _player_match_key(name:str)->str:
    # Sportsbooks frequently add/remove suffixes (Jr., Sr., II/III/IV/V).
    # Strip suffixes for JOINING only; preserve the displayed player name.
    x=re.sub(r"\\([^)]*\\)"," ",str(name or ""))
    x=re.sub(r"\\b(jr|sr|ii|iii|iv|v)\\.?\\b"," ",x,flags=re.I)
    return norm_name(x)

def lookup_player(df:pd.DataFrame,name:str)->dict:
    if df is None or df.empty:return {}
    n=norm_name(name)
    exact=df[df["player"].astype(str).map(norm_name)==n]
    if len(exact): return exact.iloc[0].to_dict()
    mk=_player_match_key(name)
    canon=df[df["player"].astype(str).map(_player_match_key)==mk]
    if len(canon)==1:return canon.iloc[0].to_dict()
    # Conservative fuzzy fallback after canonical suffix cleanup.
    hits=df[df["player"].astype(str).map(lambda x: mk in _player_match_key(x) or _player_match_key(x) in mk)]
    return hits.iloc[0].to_dict() if len(hits)==1 else {}
'''
if old_lookup not in s: raise SystemExit('lookup block not found')
s=s.replace(old_lookup,new_lookup)

old_final='''    blow_mult,blow_sd,blow_notes,_ret=player_blowout_modifier(player,market_label,game,team_name,team_ctx)
    proj*=blow_mult; sd*=blow_sd; notes.extend(blow_notes)
    if proj<=0: notes.append("insufficient player sample")
    return float(max(0,proj)),float(sd),notes
'''
new_final='''    blow_mult,blow_sd,blow_notes,_ret=player_blowout_modifier(player,market_label,game,team_name,team_ctx)
    proj*=blow_mult; sd*=blow_sd; notes.extend(blow_notes)

    # v3.7 CURRENT-SEASON ANCHOR.
    # A healthy current QB with real 2026 production must not collapse to half of
    # his observed passing baseline because several matchup/hook multipliers stack.
    # This is deliberately independent of the sportsbook prop line.
    if market_label=="Passing Yards" and sample_source=="current" and gp>=1 and pass_y>0:
        level=str(game.get("blowout_level") or "LOW").upper()
        # Keep opponent adjustment meaningful but prevent tiny early-season EPA
        # samples from cutting an established QB baseline by 20%+ on their own.
        matchup_anchor=pass_y*clamp(pass_match,.90,1.12)*clamp(pass_script,.94,1.08)*clamp(pace_adj,.96,1.05)
        retention={"LOW":.88,"MODERATE":.82,"HIGH":.75,"EXTREME":.68}.get(level,.84)
        # Market spread is validation only: a competitive external spread prevents
        # an internally noisy blowout estimate from applying a severe QB hook.
        mspread=game.get("market_home_spread")
        if mspread not in (None,""):
            am=abs(sf(mspread))
            if am<=6.5: retention=max(retention,.90)
            elif am<=10.0: retention=max(retention,.84)
        floor=matchup_anchor*retention
        ceiling=pass_y*1.24
        if proj<floor:
            proj=floor
            notes.append("current-season QB volume floor")
        proj=min(proj,ceiling)
        sd=max(sd, max(30.0,proj*.18))

    if proj<=0: notes.append("insufficient player sample")
    return float(max(0,proj)),float(sd),notes
'''
if old_final not in s: raise SystemExit('final projection block not found')
s=s.replace(old_final,new_final)

# Team-role fallback is useful but should never masquerade as 84% certainty.
old_prob='''            p,pcap,qprob_notes,quality_tier=calibrate_probability(raw_p,model_pr,r.get("prop"),tc,row_game,proj,r.get("line"))
            notes.extend(qprob_notes)
'''
new_prob='''            p,pcap,qprob_notes,quality_tier=calibrate_probability(raw_p,model_pr,r.get("prop"),tc,row_game,proj,r.get("line"))
            if str(model_pr.get("sample_source") or "")=="team_role_fallback":
                p=clamp(p,.36,.64)
                pcap=min(sf(pcap,1.0),.64)
                quality_tier="LOW"
                qprob_notes.append("team-role fallback confidence capped at 64%")
            notes.extend(qprob_notes)
'''
if old_prob not in s: raise SystemExit('probability block not found')
s=s.replace(old_prob,new_prob)
app.write_text(s)

ui=Path('cfb_nfl_ui_v18.py')
u=ui.read_text()
u=u.replace("r=requests.get(ESPN_TEAMS,params={'limit':500},timeout=(4,15),headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})",
            "r=requests.get(ESPN_TEAMS,params={'limit':1000,'groups':'80'},timeout=(4,15),headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})")

# If ESPN branding is missing from ctx, recover directly from the live game's
# ESPN IDs. This avoids abbreviation circles when the schedule already knows ID.
old_game_logo="""al=str(g.get('away_logo') or _logo(ctx,away)); hl=str(g.get('home_logo') or _logo(ctx,home)); fl=(al if fav==away else hl) or _logo(ctx,fav)"""
new_game_logo="""aid=str(g.get('away_espn_id') or ''); hid=str(g.get('home_espn_id') or '')
    al=str(g.get('away_logo') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{aid}.png' if aid else '') or _logo(ctx,away))
    hl=str(g.get('home_logo') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{hid}.png' if hid else '') or _logo(ctx,home))
    fl=(al if fav==away else hl) or _logo(ctx,fav)"""
if old_game_logo in u:u=u.replace(old_game_logo,new_game_logo)

old_player="""game=game or {}; logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _norm(team)==_norm(game.get('away')) else str(game.get('home_logo') or '') if _norm(team)==_norm(game.get('home')) else ''); color=_color(ctx,team);"""
new_player="""game=game or {}; _isaway=_norm(team)==_norm(game.get('away')); _ishome=_norm(team)==_norm(game.get('home')); _eid=str(game.get('away_espn_id') or '') if _isaway else str(game.get('home_espn_id') or '') if _ishome else ''; logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _isaway else str(game.get('home_logo') or '') if _ishome else '') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{_eid}.png' if _eid else ''); color=_color(ctx,team);"""
if old_player in u:u=u.replace(old_player,new_player)

old_fast="""game=r.get('_game') or {}; logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _norm(team)==_norm(game.get('away')) else str(game.get('home_logo') or '') if _norm(team)==_norm(game.get('home')) else ''); color=_color(ctx,team)"""
new_fast="""game=r.get('_game') or {}; _isaway=_norm(team)==_norm(game.get('away')); _ishome=_norm(team)==_norm(game.get('home')); _eid=str(game.get('away_espn_id') or '') if _isaway else str(game.get('home_espn_id') or '') if _ishome else ''; logo=_logo(ctx,team) or (str(game.get('away_logo') or '') if _isaway else str(game.get('home_logo') or '') if _ishome else '') or (f'https://a.espncdn.com/i/teamlogos/ncaa/500/{_eid}.png' if _eid else ''); color=_color(ctx,team)"""
if old_fast in u:u=u.replace(old_fast,new_fast)
ui.write_text(u)
print('v3.7 season anchor + logo restore applied')
