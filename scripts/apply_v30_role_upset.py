from pathlib import Path

# ---- app.py integration ----
p=Path('app.py')
s=p.read_text()
imp="from cfb_integrity_v28 import integrity_audit, enforce_integrity_status, market_grade_summary, segment_grade_summary, miss_audit\n"
add=imp+"from cfb_role_v30 import enrich_role_depth, role_adjust_projection, qb_upset_margin_delta\n"
if 'from cfb_role_v30 import' not in s:
    if imp not in s: raise SystemExit('import anchor missing')
    s=s.replace(imp,add)
s=s.replace('APP_VERSION = "CFB Prop Engine v2.9 — PROP PARSER CLEAN + TRUE DATA READINESS"','APP_VERSION = "CFB Prop Engine v3.0 — ROLE DEPTH + QB RUSH + UPSET PATH"')

# Current role hierarchy immediately after opportunity enrichment.
anchor="ctx,players,opportunity_health=enrich_opportunity(int(year),int(bundle.get(\"resolved_week\",week) if isinstance(bundle,dict) else week),ctx,players)\n"
if 'players=enrich_role_depth(players)' not in s:
    if anchor not in s: raise SystemExit('opportunity anchor missing')
    s=s.replace(anchor,anchor+"    players=enrich_role_depth(players)\n")

# Moneyline: add bounded explosive-QB upset path before market stabilization.
old="""    model_margin=.44*sp_gap+.22*srs_gap+.16*core_gap+.08*elo_gap+.10*power_gap+hfa
    # Market is a low-weight audit/stabilizer, never the driver.
"""
new="""    model_margin=.44*sp_gap+.22*srs_gap+.16*core_gap+.08*elo_gap+.10*power_gap+hfa
    # v3.0: bounded explosive-QB upset path. Team power still anchors the game,
    # but a major passing-efficiency/explosive mismatch can materially narrow or
    # widen the margin instead of being buried by roster/power ratings.
    upset_delta,upset_notes=qb_upset_margin_delta(h,a)
    model_margin+=upset_delta
    # Market is a low-weight audit/stabilizer, never the driver.
"""
if old not in s: raise SystemExit('margin anchor missing')
s=s.replace(old,new)
# Surface upset flags and diagnostics in returned game object.
s=s.replace('    tags=[]\n    pass_funnel_home',"    tags=list(upset_notes)\n    if abs(upset_delta)>=2.5: tags.append('⚡ QB UPSET PATH')\n    pass_funnel_home")
s=s.replace('"blowout_components":blow_profile.get("blowout_components",{})}', '"blowout_components":blow_profile.get("blowout_components",{}),"qb_upset_margin_delta":upset_delta,"qb_upset_notes":upset_notes}')

# Role/depth adjustment goes after raw market projection, before blowout modifier.
anchor2="""    # Final mean/variance adjustment comes from the dedicated game-state engine.
    # It is position/market aware: favorite QB/WR hook, RB early-volume vs late hook,
"""
insert="""    # v3.0 current-role allocation: carry/target hierarchy and QB rushing are
    # applied before game-state/blowout modifiers. This uses observed opportunity,
    # never the sportsbook line, and stays bounded to avoid one-game overfitting.
    proj,sd,role_notes=role_adjust_projection(proj,sd,player,market_label)
    notes.extend(role_notes)
    # Final mean/variance adjustment comes from the dedicated game-state engine.
    # It is position/market aware: favorite QB/WR hook, RB early-volume vs late hook,
"""
if 'role_adjust_projection(proj,sd,player,market_label)' not in s:
    if anchor2 not in s: raise SystemExit('role insertion anchor missing')
    s=s.replace(anchor2,insert)
p.write_text(s)

# ---- quality calibration: role rank + one-game cap ----
p=Path('cfb_quality_v27.py')
q=p.read_text()
q=q.replace("    adv_car=_num(player.get('adv_rush_car'))\n    notes=[]\n", "    adv_car=_num(player.get('adv_rush_car'))\n    carry_rank=int(_num(player.get('carry_role_rank')))\n    target_rank=int(_num(player.get('target_role_rank')))\n    carry_share=_num(player.get('adv_carry_share'))\n    target_share=_num(player.get('adv_target_share'))\n    role_depth=_num(player.get('role_depth_conf'))\n    notes=[]\n")
oldrole="""    if market in PASS_MARKETS:
        role=1.0 if adv_pass>=15 else (.90 if starter else (.78 if src=='current' else .66))
    elif market in REC_MARKETS:
        role=1.0 if adv_tar>=4 else (.88 if adv_tar>0 else (.76 if src=='current' and gp>=2 else .58))
    elif market in RUSH_MARKETS:
        role=1.0 if adv_car>=6 else (.88 if adv_car>0 else (.76 if src=='current' and gp>=2 else .62))
    else:
        role=.82 if src=='current' else .70
"""
newrole="""    if market in PASS_MARKETS:
        role=1.0 if adv_pass>=15 else (.90 if starter else (.78 if src=='current' else .66))
    elif market in REC_MARKETS:
        role=1.0 if (adv_tar>=4 and target_rank in (1,2,3)) else (.88 if adv_tar>0 else (.76 if src=='current' and gp>=2 else .58))
        if target_rank>=4 and target_share<.10: role*=.82; notes.append('depth target role')
        elif target_rank in (1,2) and target_share>=.15: role=min(1.0,role+.04)
    elif market in RUSH_MARKETS:
        role=1.0 if (adv_car>=6 and (carry_rank in (1,2) or adv_pass>=10)) else (.88 if adv_car>0 else (.76 if src=='current' and gp>=2 else .62))
        if carry_rank>=3 and carry_share<.16 and adv_pass<10: role*=.82; notes.append('committee/depth carry role')
        elif carry_rank==1 and carry_share>=.28: role=min(1.0,role+.04)
    else:
        role=.82 if src=='current' else .70
    if role_depth>0: role=.82*role+.18*role_depth
"""
if oldrole not in q: raise SystemExit('quality role block missing')
q=q.replace(oldrole,newrole)
# One-game current sample cannot produce 80%+ confidence on role props.
q=q.replace("    pcap=_clamp(.54+.30*role,.56,.86)\n    tier='HIGH' if role>=.88 else ('MEDIUM' if role>=.70 else 'LOW')\n", "    pcap=_clamp(.54+.30*role,.56,.86)\n    if gp<=1 and src=='current' and market in REC_MARKETS|RUSH_MARKETS:\n        pcap=min(pcap,.74); notes.append('one-game role confidence cap')\n    tier='HIGH' if role>=.88 else ('MEDIUM' if role>=.70 else 'LOW')\n")
# PLAYABLE requires actual top-rotation role for rush/rec when ranks are known.
q=q.replace("    if market in REC_MARKETS and _num(player.get('adv_targets'))<=0 and str(player.get('sample_source') or '').lower()!='current':\n        return 'TRACK'\n    if market in RUSH_MARKETS and _num(player.get('adv_rush_car'))<=0 and str(player.get('sample_source') or '').lower()!='current':\n        return 'TRACK'\n", "    if market in REC_MARKETS and _num(player.get('adv_targets'))<=0 and str(player.get('sample_source') or '').lower()!='current':\n        return 'TRACK'\n    if market in REC_MARKETS and int(_num(player.get('target_role_rank')))>=4 and _num(player.get('adv_target_share'))<.10:\n        return 'TRACK'\n    if market in RUSH_MARKETS and _num(player.get('adv_rush_car'))<=0 and str(player.get('sample_source') or '').lower()!='current':\n        return 'TRACK'\n    if market in RUSH_MARKETS and int(_num(player.get('carry_role_rank')))>=3 and _num(player.get('adv_carry_share'))<.16 and _num(player.get('adv_pass_att'))<10:\n        return 'TRACK'\n")
p.write_text(q)

# ---- blowout retention display must never exceed 100% ----
p=Path('cfb_blowout_v26.py')
b=p.read_text()
# Clamp any retention values at source if simple assignments exist; safe final profile clamp too.
if "for k in ('qb_starter_retention','wr1_retention','rb1_retention'):" not in b:
    marker="    return profile\n"
    if marker in b:
        b=b.replace(marker,"    for k in ('qb_starter_retention','wr1_retention','rb1_retention'):\n        if k in profile: profile[k]=max(0.0,min(1.0,_num(profile.get(k),1.0)))\n    return profile\n")
p.write_text(b)
print('CFB v3.0 role/upset repairs applied')
