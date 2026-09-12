from pathlib import Path
import re

# v3.4: hard-disable the known-blocked Underdog server path and make PropLine the only
# automatic live player-line provider. This prevents the app from spamming 11 blocked
# endpoints and keeps diagnostics focused on the provider that can actually work.

p=Path('app.py')
s=p.read_text()
s=re.sub(r'APP_VERSION = "CFB Prop Engine v[^"]+"',
         'APP_VERSION = "CFB Prop Engine v3.4 — PROPLINE ONLY LIVE LINES"',s,count=1)

s=s.replace(
    'live_sources=(["Auto Lines","PropLine Live","Underdog Live"] if propline_key else ["Underdog Live"]) + (["Live Odds API"] if odds.ready else []) + ["Manual"]',
    'live_sources=(["Auto Lines","PropLine Live"] if propline_key else []) + (["Live Odds API"] if odds.ready else []) + ["Manual"]'
)
s=s.replace('if source in {"Auto Lines","Underdog Live"}:','if source=="Auto Lines":')

# Remove Auto Lines fallback to Underdog even when PropLine is healthy-but-empty.
old='''                if not pl_rows and str(pl_debug.get("status") or "").upper()=="EMPTY":\n                    raw_ud,ud_debug=fetch_underdog_cfb_props(force=refresh)\n                    st.session_state["ud_cfb_rows"]=raw_ud\n                    st.session_state["ud_cfb_debug"]=ud_debug\n                    ud_rows=raw_ud\n                    provider_note=f"PropLine empty → Underdog fallback · {len(raw_ud)} rows"\n                elif not pl_rows:\n                    ud_rows=[]\n                    provider_note=f"PropLine {pl_debug.get('status','ERROR')} · Underdog circuit breaker active"\n'''
new='''                if not pl_rows:\n                    ud_rows=[]\n                    provider_note=f"PropLine {pl_debug.get('status','EMPTY')} · Underdog disabled (HTTP 426)"\n'''
if old in s:
    s=s.replace(old,new)

# Remove the direct Underdog branch if still present.
old2='''            else:\n                raw_ud,ud_debug=fetch_underdog_cfb_props(force=refresh)\n                st.session_state["ud_cfb_rows"]=raw_ud\n                st.session_state["ud_cfb_debug"]=ud_debug\n                ud_rows=raw_ud\n                provider_note=f"Underdog direct · {len(raw_ud)} rows"\n'''
if old2 in s:
    s=s.replace(old2,'')

# Slate bootstrap: PropLine only. Never call blocked Underdog when PropLine has no rows.
old3='''        if not boot_rows:\n            boot_rows,boot_debug=fetch_underdog_cfb_props(force=force)\n            st.session_state["ud_cfb_rows"]=boot_rows\n            st.session_state["ud_cfb_debug"]=boot_debug\n'''
if old3 in s:
    s=s.replace(old3,'')

s=s.replace(
    'No standard PropLine CFB player lines matched this slate. If PropLine reports ERROR, Underdog is intentionally not retried because its server-side endpoint is currently blocked with HTTP 426.',
    'No standard PropLine CFB player lines matched this slate. Underdog is disabled because its server-side endpoint is currently blocked with HTTP 426.'
)

# Make sure old Underdog diagnostics are not shown in Auto Lines.
s=s.replace('st.json({"PropLine":pl_debug,"Underdog":ud_debug})','st.json({"PropLine":pl_debug,"Underdog":"DISABLED — HTTP 426"})')

p.write_text(s)

# Hard circuit breaker inside the Underdog module too, so any stray call from older
# code paths returns instantly without network traffic.
p=Path('underdog_cfb_v15.py')
u=p.read_text()
start=u.index('def fetch_underdog_cfb_props(force=False)->Tuple[List[Dict[str,Any]],List[Dict[str,Any]]]:')
end=u.index('\n\ndef props_for_game', start)
replacement='''def fetch_underdog_cfb_props(force=False)->Tuple[List[Dict[str,Any]],List[Dict[str,Any]]]:\n    return [], [{\n        'provider':'Underdog',\n        'status':'DISABLED',\n        'rows':0,\n        'error':'Server-side Underdog endpoint disabled after repeated HTTP 426 Upgrade Required responses.'\n    }]\n'''
u=u[:start]+replacement+u[end:]
p.write_text(u)

print('v3.4 PropLine-only live-line repair applied')
