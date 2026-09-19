from pathlib import Path

p=Path("free_data_v16.py")
s=p.read_text()
old="""    resolved_week=int(week)
    wc=base._col(schedule,'week','season_week') if schedule is not None else None
    available=[]
    if wc and not schedule.empty:
        available=sorted(pd.to_numeric(schedule[wc],errors='coerce').dropna().astype(int).unique().tolist())
        if available and resolved_week not in available:
            resolved_week=max(available)

    games=base._schedule_rows(schedule,resolved_week)
    if not games:
        games=base._espn_schedule(year,resolved_week)
        health['espn_schedule']=len(games)
"""
new="""    resolved_week=int(week)
    wc=base._col(schedule,'week','season_week') if schedule is not None else None
    available=[]
    if wc and not schedule.empty:
        available=sorted(pd.to_numeric(schedule[wc],errors='coerce').dropna().astype(int).unique().tolist())
        # IMPORTANT: never silently roll a requested future/current week backward.
        # A lagging cfbfastR release can be one week behind the actual live slate.
        # Keep resolved_week equal to the requested week and use ESPN/live events
        # for schedule identity while current player tables remain season-to-date.
        if available and resolved_week not in available:
            health['schedule_week_missing']=resolved_week

    games=base._schedule_rows(schedule,resolved_week)
    if not games:
        games=base._espn_schedule(year,resolved_week)
        health['espn_schedule']=len(games)
"""
if old not in s: raise SystemExit("week fallback block not found")
s=s.replace(old,new)
p.write_text(s)

p=Path("app.py")
s=p.read_text()
s=s.replace("CFB Prop Engine v3.8 — EVENT LOCK + PROJECTION VERIFY","CFB Prop Engine v3.9 — TRUE WEEK + PLAYER DATA LOCK")
# Ensure provenance is in compact table.
old='show=["player","team","prop","side","line","projection","edge","probability","status","quality_tier","integrity_tier","integrity_flags","notes"]'
new='show=["player","team","prop","side","line","projection","projection_source","sample_games","edge","probability","status","quality_tier","integrity_tier","integrity_flags","notes"]'
s=s.replace(old,new)
# Make unresolved player joins explicit and non-playable rather than inventing confidence.
needle="""            if str(model_pr.get("sample_source") or "")=="team_role_fallback":
                p=clamp(p,.36,.64)
                pcap=min(sf(pcap,1.0),.64)
                quality_tier="LOW"
                qprob_notes.append("team-role fallback confidence capped at 64%")
"""
repl="""            if str(model_pr.get("sample_source") or "")=="team_role_fallback":
                p=clamp(p,.40,.60)
                pcap=min(sf(pcap,1.0),.60)
                quality_tier="LOW"
                qprob_notes.append("team-role fallback confidence capped at 60%")
"""
if needle in s:s=s.replace(needle,repl)
p.write_text(s)

for f in ["free_data_v16.py","app.py"]:
    compile(Path(f).read_text(),f,"exec")
print("v3.9 true-week patch ready")
