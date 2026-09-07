from pathlib import Path

p=Path('app.py')
s=p.read_text()

s=s.replace(
"from cfb_quality_v27 import stabilize_projection, calibrate_probability, status_from_quality\n",
"from cfb_quality_v27 import stabilize_projection, calibrate_probability, status_from_quality\nfrom cfb_integrity_v28 import integrity_audit, enforce_integrity_status, market_grade_summary, segment_grade_summary, miss_audit\n"
)
s=s.replace(
'APP_VERSION = "CFB Prop Engine v2.6 — COACH-AWARE BLOWOUT + COMPLETE OPPORTUNITY"',
'APP_VERSION = "CFB Prop Engine v2.8 — LIVE EVENT LOCK + ROLE INTEGRITY + GRADE AUDIT"'
)

old="""            status=status_from_quality(p,proj,quality_tier,r.get(\"prop\"),model_pr)\n            src=str(model_pr.get(\"sample_source\") or \"fallback\").lower(); gp=sf(model_pr.get(\"games\"),0)\n"""
new="""            status=status_from_quality(p,proj,quality_tier,r.get(\"prop\"),model_pr)\n            integrity_tier,integrity_score,integrity_flags=integrity_audit(r,model_pr,team,opp,row_game,tc,r.get(\"prop\"))\n            status=enforce_integrity_status(status,p,quality_tier,integrity_tier,integrity_flags)\n            if integrity_flags:\n                notes.append('integrity: '+', '.join(integrity_flags))\n            notes.append(f'data integrity {integrity_tier.lower()}')\n            src=str(model_pr.get(\"sample_source\") or \"fallback\").lower(); gp=sf(model_pr.get(\"games\"),0)\n"""
if old not in s: raise SystemExit('status insertion anchor missing')
s=s.replace(old,new)

old="""               \"quality_tier\":quality_tier,\"probability_cap\":pcap,\"live_game_locked\":bool(r.get(\"away\") and r.get(\"home\"))}\n"""
new="""               \"quality_tier\":quality_tier,\"probability_cap\":pcap,\"live_game_locked\":bool(r.get(\"away\") and r.get(\"home\")),\n               \"integrity_tier\":integrity_tier,\"integrity_score\":integrity_score,\"integrity_flags\":\" | \".join(integrity_flags)}\n"""
if old not in s: raise SystemExit('q anchor missing')
s=s.replace(old,new)

s=s.replace(
'show=["player","team","prop","side","line","projection","edge","probability","status","notes"]',
'show=["player","team","prop","side","line","projection","edge","probability","status","quality_tier","integrity_tier","integrity_flags","notes"]'
)

old='''    st.code("SportsDataverse/NCAA + current rosters + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog event lock → opportunity/hook/pressure/explosive engine → QB volume floor + role-quality calibration → Higher/Lower probability + edge → save/grade",language="text")\n'''
new='''    st.code("SportsDataverse/NCAA + current rosters + drives + game rosters + advanced QB/RB/WR + situational/red-zone + Open-Meteo + Underdog event lock → opportunity/hook/pressure/explosive engine → QB volume floor + role-quality calibration → data-integrity gate → Higher/Lower probability + edge → market-by-market grading + miss audit",language="text")\n'''
if old in s:s=s.replace(old,new)

old="""                st.metric(\"Record\",f\"{wins}-{losses}\"+(f\"-{pushes}\" if pushes else \"\"))\n                st.dataframe(gdf[[\"player\",\"prop\",\"side\",\"line\",\"projection\",\"probability\",\"actual\",\"result\"]],width=\"stretch\",hide_index=True)\n                if st.button(\"Append to graded history\"):\n"""
new="""                st.metric(\"Record\",f\"{wins}-{losses}\"+(f\"-{pushes}\" if pushes else \"\"))\n                st.dataframe(gdf[[c for c in [\"player\",\"prop\",\"side\",\"line\",\"projection\",\"probability\",\"status\",\"quality_tier\",\"integrity_tier\",\"actual\",\"result\"] if c in gdf.columns]],width=\"stretch\",hide_index=True)\n                st.markdown(\"**Market performance**\")\n                ms=market_grade_summary(gdf)\n                if not ms.empty: st.dataframe(ms,width=\"stretch\",hide_index=True)\n                cga,cgb,cgc=st.columns(3)\n                with cga:\n                    st.markdown(\"**By status**\"); ss=segment_grade_summary(gdf,'status')\n                    if not ss.empty: st.dataframe(ss,width=\"stretch\",hide_index=True)\n                with cgb:\n                    st.markdown(\"**By projection quality**\"); qs=segment_grade_summary(gdf,'quality_tier')\n                    if not qs.empty: st.dataframe(qs,width=\"stretch\",hide_index=True)\n                with cgc:\n                    st.markdown(\"**By data integrity**\"); ins=segment_grade_summary(gdf,'integrity_tier')\n                    if not ins.empty: st.dataframe(ins,width=\"stretch\",hide_index=True)\n                misses=miss_audit(gdf)\n                if not misses.empty:\n                    with st.expander(f\"❌ Loss audit ({len(misses)})\",expanded=True): st.dataframe(misses,width=\"stretch\",hide_index=True)\n                if st.button(\"Append to graded history\"):\n"""
if old not in s: raise SystemExit('grade block anchor missing')
s=s.replace(old,new)

old="""    if hist_path.exists():\n        h=pd.read_csv(hist_path); st.caption(f\"Historical graded rows: {len(h)}\")\n        if len(h): st.dataframe(h.tail(100),width=\"stretch\",hide_index=True)\n"""
new="""    if hist_path.exists():\n        h=pd.read_csv(hist_path); st.caption(f\"Historical graded rows: {len(h)}\")\n        if len(h):\n            hm=market_grade_summary(h)\n            if not hm.empty:\n                st.markdown(\"**Historical market win rates**\"); st.dataframe(hm,width=\"stretch\",hide_index=True)\n            st.dataframe(h.tail(100),width=\"stretch\",hide_index=True)\n"""
if old not in s: raise SystemExit('history anchor missing')
s=s.replace(old,new)

p.write_text(s)
print('v2.8 integrity/grade upgrade applied')
