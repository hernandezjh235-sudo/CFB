"""Optional one-shot cache warmer for Railway/GitHub deployments."""
import os, json, requests
from pathlib import Path
from datetime import datetime
BASE="https://api.collegefootballdata.com"
key=os.getenv("CFBD_API_KEY","")
if not key: raise SystemExit("Set CFBD_API_KEY first")
year=int(os.getenv("CFB_YEAR",datetime.now().year)); week=int(os.getenv("CFB_WEEK","1"))
headers={"Authorization":f"Bearer {key}"}
endpoints={
 "games":("/games",{"year":year}),"core":("/ratings/core",{"year":year}),"sp":("/ratings/sp",{"year":year}),
 "srs":("/ratings/srs",{"year":year}),"elo":("/ratings/elo",{"year":year,"week":week}),"rankings":("/rankings",{"year":year,"week":week}),
 "talent":("/talent",{"year":year}),"player_stats":("/stats/player/season",{"year":year,"startWeek":1,"endWeek":week}),
 "advanced":("/stats/season/advanced",{"year":year,"startWeek":1,"endWeek":week,"excludeGarbageTime":True}),
}
out=Path(__file__).resolve().parents[1]/"data"/"bootstrap"; out.mkdir(parents=True,exist_ok=True)
for name,(ep,params) in endpoints.items():
    r=requests.get(BASE+ep,headers=headers,params=params,timeout=30); print(name,r.status_code)
    if r.ok:(out/f"{year}_w{week}_{name}.json").write_text(json.dumps(r.json()))
