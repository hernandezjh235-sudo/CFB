from pathlib import Path

# PropLine currently documents the CFB key as football_ncaaf. Avoid /sports discovery
# as a hard dependency because that endpoint can return provider-side 500s even when
# the sport-specific endpoints are healthy.
p=Path('propline_cfb_v31.py')
s=p.read_text()
start=s.index('def discover_cfb_sport(api_key: str) -> str:')
end=s.index('\n\ndef _event_date', start)
new='''def discover_cfb_sport(api_key: str) -> str:\n    # Official PropLine NCAAF sport key. Do not make /sports a prerequisite.\n    # Their documented CFB endpoints use /sports/football_ncaaf/... directly.\n    return "football_ncaaf"\n'''
s=s[:start]+new+s[end:]
p.write_text(s)

# Auto Lines: only try blocked Underdog when PropLine is genuinely healthy-but-empty.
# If PropLine itself errors, surface that error instead of spamming eleven known-blocked
# Underdog endpoints with 426 responses.
p=Path('app.py')
s=p.read_text()
s=s.replace('APP_VERSION = "CFB Prop Engine v3.2 — ROLE DEPTH + QB UPSET + PROPLINE PRIMARY"',
            'APP_VERSION = "CFB Prop Engine v3.3 — DIRECT PROPLINE NCAAF + CLEAN FAILOVER"')
old='''                if not pl_rows:\n                    raw_ud,ud_debug=fetch_underdog_cfb_props(force=refresh)\n                    st.session_state["ud_cfb_rows"]=raw_ud\n                    st.session_state["ud_cfb_debug"]=ud_debug\n                    ud_rows=raw_ud\n                    provider_note=f"PropLine empty → Underdog fallback · {len(raw_ud)} rows"\n'''
new='''                if not pl_rows and str(pl_debug.get("status") or "").upper()=="EMPTY":\n                    raw_ud,ud_debug=fetch_underdog_cfb_props(force=refresh)\n                    st.session_state["ud_cfb_rows"]=raw_ud\n                    st.session_state["ud_cfb_debug"]=ud_debug\n                    ud_rows=raw_ud\n                    provider_note=f"PropLine empty → Underdog fallback · {len(raw_ud)} rows"\n                elif not pl_rows:\n                    ud_rows=[]\n                    provider_note=f"PropLine {pl_debug.get('status','ERROR')} · Underdog circuit breaker active"\n'''
if old not in s:
    raise SystemExit('Auto Lines fallback anchor missing')
s=s.replace(old,new)
s=s.replace('No standard PropLine CFB player lines matched this slate yet. Underdog fallback was attempted only if PropLine returned zero rows.',
            'No standard PropLine CFB player lines matched this slate. If PropLine reports ERROR, Underdog is intentionally not retried because its server-side endpoint is currently blocked with HTTP 426.')
p.write_text(s)
print('v3.3 direct PropLine NCAAF repair applied')
