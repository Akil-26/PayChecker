"""
Paychecker — Streamlit Dashboard
Razorpay Buildathon · Track 03: AI Revenue Recovery

Design System: Claude / Anthropic Visual Language
  Primary BG   : #FAF9F5  Warm Cream
  Surface       : #F0EEE6  Muted Parchment
  Dark BG       : #1C1B1A  Warm Charcoal
  Accent        : #DA7756  Terracotta
  Text Primary  : #1E1E1E  Dark Espresso
  Text Secondary: #6B6963  Muted Warm Gray
  Border        : #E5E3DA  Subtle Warm Gray
  Highlight     : #F2E3D5  Soft Peach

Start backend:   uvicorn app.main:app --reload
Start dashboard: streamlit run dashboard.py
"""

from __future__ import annotations
from typing import Any
import requests
import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────
BASE_URL   = "http://127.0.0.1:8000/api"
HEALTH_URL = "http://127.0.0.1:8000/health"

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Paychecker · Revenue Recovery",
    page_icon="🔁",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM — injected via st.markdown
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── Google Fonts ──────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap');

/* ── Design tokens ─────────────────────────────────────────────────── */
:root {
  --bg-primary:   #FAF9F5;
  --bg-surface:   #F0EEE6;
  --bg-dark:      #1C1B1A;
  --accent:       #DA7756;
  --accent-deep:  #CC6B49;
  --text-primary: #1E1E1E;
  --text-muted:   #6B6963;
  --border:       #E5E3DA;
  --highlight:    #F2E3D5;
  --success:      #4A7C59;
  --warning:      #B8860B;
  --danger:       #9B2C2C;
  --radius-sm:    8px;
  --radius-md:    12px;
  --radius-lg:    20px;
}

/* ── App background ────────────────────────────────────────────────── */
.stApp {
  background-color: var(--bg-primary) !important;
  font-family: 'Inter', system-ui, -apple-system, sans-serif;
  color: var(--text-primary);
}

/* ── Sidebar ───────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background-color: var(--bg-dark) !important;
  border-right: 1px solid #2C2B2A !important;
}
[data-testid="stSidebar"] * {
  color: #E8E4DC !important;
}
[data-testid="stSidebar"] .stRadio label {
  font-size: 0.85rem !important;
  font-weight: 400 !important;
  padding: 6px 0 !important;
  color: #B0AA9F !important;
  transition: color 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover {
  color: #FAF9F5 !important;
}
[data-testid="stSidebar"] [data-baseweb="radio"] input:checked + div {
  color: var(--accent) !important;
}
[data-testid="stSidebar"] hr {
  border-color: #2C2B2A !important;
}

/* ── Typography ────────────────────────────────────────────────────── */
h1, h2, h3 {
  font-family: 'Lora', Georgia, serif !important;
  color: var(--text-primary) !important;
  font-weight: 500 !important;
  letter-spacing: -0.01em;
}
h1 { font-size: 1.75rem !important; }
h2 { font-size: 1.25rem !important; }
h3 { font-size: 1.05rem !important; }
p, li, label, .stMarkdown p {
  font-family: 'Inter', sans-serif !important;
  line-height: 1.6 !important;
  color: var(--text-primary) !important;
}
.stCaption, small, .caption-text {
  color: var(--text-muted) !important;
  font-size: 0.78rem !important;
}

/* ── Metric cards ──────────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  padding: 18px 20px !important;
  transition: border-color 0.15s;
}
[data-testid="stMetric"]:hover {
  border-color: var(--accent) !important;
}
[data-testid="stMetricLabel"] {
  font-family: 'Inter', sans-serif !important;
  font-size: 0.72rem !important;
  font-weight: 500 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  color: var(--text-muted) !important;
}
[data-testid="stMetricValue"] {
  font-family: 'Lora', Georgia, serif !important;
  font-size: 1.5rem !important;
  font-weight: 500 !important;
  color: var(--text-primary) !important;
}

/* ── Buttons ───────────────────────────────────────────────────────── */
.stButton > button {
  font-family: 'Inter', sans-serif !important;
  font-size: 0.82rem !important;
  font-weight: 500 !important;
  border-radius: var(--radius-lg) !important;
  border: 1px solid var(--border) !important;
  background: var(--bg-surface) !important;
  color: var(--text-primary) !important;
  padding: 8px 20px !important;
  transition: all 0.15s !important;
  letter-spacing: 0.01em;
}
.stButton > button:hover {
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  background: var(--highlight) !important;
}
.stButton > button[kind="primary"] {
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--accent-deep) !important;
  border-color: var(--accent-deep) !important;
  color: #ffffff !important;
}

/* ── Inputs / Selectbox / Number input ─────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-sm) !important;
  color: var(--text-primary) !important;
  font-family: 'Inter', sans-serif !important;
  font-size: 0.85rem !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(218,119,86,0.12) !important;
}
.stSelectbox label, .stTextInput label, .stNumberInput label {
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  color: var(--text-muted) !important;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* ── Dataframes / Tables ────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  overflow: hidden;
}
.stDataFrame thead th {
  background: var(--bg-surface) !important;
  color: var(--text-muted) !important;
  font-size: 0.72rem !important;
  text-transform: uppercase !important;
  letter-spacing: 0.05em !important;
  font-weight: 500 !important;
  border-bottom: 1px solid var(--border) !important;
}
.stDataFrame tbody tr:hover td {
  background: var(--highlight) !important;
}

/* ── Alerts ────────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  border-radius: var(--radius-md) !important;
  border-left-width: 3px !important;
  font-size: 0.83rem !important;
}
[data-testid="stAlert"][data-baseweb="notification"] {
  background: var(--highlight) !important;
}

/* ── Expander ──────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  background: var(--bg-surface) !important;
  margin-bottom: 10px !important;
}
[data-testid="stExpander"] summary {
  font-family: 'Inter', sans-serif !important;
  font-size: 0.88rem !important;
  font-weight: 500 !important;
  color: var(--text-primary) !important;
  padding: 14px 16px !important;
}
[data-testid="stExpander"] summary:hover {
  color: var(--accent) !important;
}

/* ── Dividers ──────────────────────────────────────────────────────── */
hr {
  border-color: var(--border) !important;
  margin: 24px 0 !important;
}

/* ── Code blocks ────────────────────────────────────────────────────── */
code {
  background: var(--bg-surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 4px !important;
  color: var(--accent-deep) !important;
  font-size: 0.8rem !important;
  padding: 1px 5px !important;
}

/* ── Spinner ────────────────────────────────────────────────────────── */
.stSpinner > div {
  border-top-color: var(--accent) !important;
}

/* ── Custom components ──────────────────────────────────────────────── */
.pc-page-header {
  padding: 24px 0 8px 0;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}
.pc-page-title {
  font-family: 'Lora', Georgia, serif;
  font-size: 1.55rem;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.2;
}
.pc-page-sub {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-top: 4px;
}
.pc-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px 22px;
  margin-bottom: 12px;
}
.pc-card-accent {
  border-left: 3px solid var(--accent);
}
.pc-badge {
  display: inline-block;
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 3px 10px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--bg-primary);
  color: var(--text-muted);
}
.pc-badge-recovered  { background: #EAF3EC; color: #3A6B48; border-color: #B8D9BF; }
.pc-badge-stopped    { background: #F9ECEC; color: #8B2020; border-color: #E5B8B8; }
.pc-badge-escalated  { background: #FEF5E7; color: #9B6B00; border-color: #F0D49A; }
.pc-badge-scheduled  { background: #FDF0E8; color: #9B4A1A; border-color: #EEC9AB; }
.pc-badge-detected   { background: #F0EEE6; color: #5A5750; border-color: #D5D2C8; }
.pc-badge-active     { background: #E8EFF9; color: #1A4080; border-color: #B0C8E8; }
.pc-safety-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: 0.84rem;
}
.pc-safety-row:last-child { border-bottom: none; }
.pc-check-ok   { color: #4A7C59; font-size: 1rem; }
.pc-check-fail { color: #9B2C2C; font-size: 1rem; }
.pc-audit-row {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  align-items: flex-start;
  font-size: 0.83rem;
}
.pc-audit-row:last-child { border-bottom: none; }
.pc-audit-ts {
  font-size: 0.72rem;
  color: var(--text-muted);
  font-family: monospace;
  white-space: nowrap;
  padding-top: 2px;
  min-width: 120px;
}
.pc-audit-type {
  font-weight: 500;
  color: var(--accent-deep);
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  min-width: 200px;
}
.pc-audit-msg {
  color: var(--text-primary);
  line-height: 1.4;
  flex: 1;
}
.pc-sidebar-logo {
  font-family: 'Lora', Georgia, serif;
  font-size: 1.15rem;
  font-weight: 500;
  color: #FAF9F5;
  letter-spacing: -0.01em;
}
.pc-sidebar-sub {
  font-size: 0.7rem;
  color: #6B6560;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.pc-sidebar-status-ok {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: #6BBF82;
  padding: 5px 10px;
  background: rgba(107,191,130,0.1);
  border: 1px solid rgba(107,191,130,0.2);
  border-radius: var(--radius-lg);
}
.pc-sidebar-status-err {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  color: #E07070;
  padding: 5px 10px;
  background: rgba(224,112,112,0.1);
  border: 1px solid rgba(224,112,112,0.2);
  border-radius: var(--radius-lg);
}
.pc-section-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  margin-bottom: 10px;
  margin-top: 4px;
}
.pc-scenario-key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--accent);
  color: white;
  border-radius: 50%;
  font-size: 0.78rem;
  font-weight: 600;
  flex-shrink: 0;
}
.pc-scenario-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.pc-narrative {
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.55;
  margin-bottom: 16px;
  padding: 12px 14px;
  background: var(--bg-primary);
  border-radius: var(--radius-sm);
  border-left: 2px solid var(--border);
}
.pc-clock-display {
  font-family: 'Lora', Georgia, serif;
  font-size: 2.2rem;
  font-weight: 400;
  color: var(--text-primary);
  letter-spacing: 0.02em;
  text-align: center;
  padding: 32px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-bottom: 24px;
}
.pc-clock-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  text-align: center;
  margin-bottom: 8px;
}
.pc-danger-box {
  background: #FDF4F4;
  border: 1px solid #E8C8C8;
  border-radius: var(--radius-md);
  padding: 16px 20px;
  margin-bottom: 20px;
}
.pc-danger-title {
  font-weight: 600;
  color: #8B2020;
  font-size: 0.85rem;
  margin-bottom: 4px;
}
.pc-danger-desc {
  font-size: 0.8rem;
  color: #A04040;
  line-height: 1.5;
}
.pc-empty {
  text-align: center;
  padding: 48px 24px;
  color: var(--text-muted);
  font-size: 0.85rem;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.pc-empty-icon {
  font-size: 2rem;
  margin-bottom: 8px;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def api(method: str, path: str, **kwargs) -> dict | list | None:
    try:
        r = requests.request(method, f"{BASE_URL}{path}", timeout=15, **kwargs)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach backend — run `uvicorn app.main:app --reload`")
        return None
    except requests.exceptions.HTTPError as exc:
        try:
            body = exc.response.json()
        except Exception:
            body = {}
        st.error(f"API {exc.response.status_code}: {body.get('error', {}).get('message', str(exc))}")
        return None


def fmt_inr(money: dict | int | float | None) -> str:
    if money is None:
        return "₹ –"
    if isinstance(money, (int, float)):
        return f"₹{money / 100:,.2f}"
    amt = money.get("amount")
    if amt is None:
        return "₹ –"
    return f"₹{amt / 100:,.2f}"


def pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "–"


def backend_alive() -> bool:
    try:
        return requests.get(HEALTH_URL, timeout=4).status_code == 200
    except Exception:
        return False


STATE_BADGE_CLASS = {
    "RECOVERED": "pc-badge-recovered",
    "STOPPED":   "pc-badge-stopped",
    "ESCALATED": "pc-badge-escalated",
    "SCHEDULED": "pc-badge-scheduled",
    "DETECTED":  "pc-badge-detected",
    "FAILED":    "pc-badge-stopped",
    "BLOCKED":   "pc-badge-stopped",
}

def state_badge_html(state: str) -> str:
    cls = STATE_BADGE_CLASS.get(state, "pc-badge pc-badge-active")
    if cls == "pc-badge-detected":
        cls = "pc-badge " + cls
    elif "pc-badge-" in cls and "pc-badge pc-badge" not in cls:
        cls = "pc-badge " + cls
    return f'<span class="{cls}">{state}</span>'


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f"""
    <div class="pc-page-header">
      <div class="pc-page-title">{title}</div>
      {"<div class='pc-page-sub'>" + subtitle + "</div>" if subtitle else ""}
    </div>
    """, unsafe_allow_html=True)


def section_label(text: str) -> None:
    st.markdown(f'<div class="pc-section-label">{text}</div>', unsafe_allow_html=True)


def card(content_html: str, accent: bool = False) -> None:
    cls = "pc-card pc-card-accent" if accent else "pc-card"
    st.markdown(f'<div class="{cls}">{content_html}</div>', unsafe_allow_html=True)


def empty_state(icon: str, message: str) -> None:
    st.markdown(f"""
    <div class="pc-empty">
      <div class="pc-empty-icon">{icon}</div>
      <div>{message}</div>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    alive = backend_alive()
    status_html = (
        '<span class="pc-sidebar-status-ok">● Online</span>'
        if alive else
        '<span class="pc-sidebar-status-err">● Offline</span>'
    )
    st.markdown(f"""
    <div style="padding: 8px 0 20px 0;">
      <div class="pc-sidebar-logo">Paychecker</div>
      <div class="pc-sidebar-sub" style="margin: 4px 0 12px 0;">
        AI Revenue Recovery
      </div>
      {status_html}
    </div>
    """, unsafe_allow_html=True)

    if not alive:
        st.markdown("""
        <div style="font-size:0.72rem; color:#E07070; margin: 8px 0 4px 0;">
        Start backend:
        </div>
        """, unsafe_allow_html=True)
        st.code("uvicorn app.main:app --reload", language="bash")

    st.markdown('<hr style="border-color:#2C2B2A; margin: 16px 0;"/>', unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Demo Scenarios",
            "Recovery Cases",
            "Payments",
            "Autopilot",
            "Strategy Lab",
            "Simulation Clock",
            "Reset Demo",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<hr style="border-color:#2C2B2A; margin: 16px 0;"/>', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size:0.68rem; color:#4A4744; line-height:1.6;">
      Razorpay Buildathon<br>
      Track 03 · Synthetic data only.<br>
      No real payments processed.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: OVERVIEW
# ══════════════════════════════════════════════════════════════════════════

if page == "Overview":
    page_header("Command Center", "Live revenue recovery metrics and safety posture")

    data = api("GET", "/recovery/overview")
    if not data:
        st.stop()

    # ── KPI row 1: money ────────────────────────────────────────────────
    section_label("Revenue")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("At Risk",        fmt_inr(data.get("revenue_at_risk")))
    c2.metric("Recovered",      fmt_inr(data.get("revenue_recovered")))
    c3.metric("Recovery Rate",  pct(data.get("recovery_rate")))
    c4.metric("Avg per Case",   fmt_inr(data.get("average_recovery_value")))

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── KPI row 2: cases ────────────────────────────────────────────────
    section_label("Cases")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total",            data.get("cases_total", 0))
    c2.metric("Recovered",        data.get("cases_recovered", 0))
    c3.metric("Active",           data.get("active_cases", 0))
    c4.metric("Scheduled",        data.get("scheduled_cases", 0))
    c5.metric("Payments at Risk", data.get("payments_at_risk", 0))

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    col_l, col_r = st.columns([1, 1])

    # ── Cases by state ──────────────────────────────────────────────────
    with col_l:
        section_label("Cases by state")
        cbs = data.get("cases_by_state", {})
        if cbs:
            rows_html = ""
            for state, count in sorted(cbs.items(), key=lambda x: -x[1]):
                badge = state_badge_html(state)
                rows_html += f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                     padding:9px 0; border-bottom:1px solid var(--border); font-size:0.84rem;">
                  {badge}
                  <span style="font-weight:500; color:var(--text-primary);">{count}</span>
                </div>"""
            st.markdown(f'<div class="pc-card">{rows_html}</div>', unsafe_allow_html=True)
        else:
            empty_state("📭", "No case data yet — run Reset Demo first.")

    # ── By failure reason ───────────────────────────────────────────────
    with col_r:
        section_label("By failure reason")
        reasons = data.get("by_failure_reason", [])
        if reasons:
            import pandas as pd
            df = pd.DataFrame([{
                "Reason":    r["failure_reason"],
                "Cases":     r["cases"],
                "At Risk":   fmt_inr(r.get("amount_at_risk")),
                "Recovered": fmt_inr(r.get("amount_recovered")),
                "Rate":      pct(r.get("recovery_rate")),
            } for r in reasons])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            empty_state("📊", "No breakdown data yet.")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    # ── Safety posture ──────────────────────────────────────────────────
    section_label("Safety posture")
    safety = data.get("safety", {})
    checks = [
        ("Recovery budget enforced",        safety.get("recovery_budget_enforced")),
        ("High-value escalation enabled",   safety.get("high_value_escalation_enabled")),
        ("Blocked actions never executed",  safety.get("blocked_actions_never_executed")),
        ("Outcomes independently verified", safety.get("outcomes_independently_verified")),
        ("Complete audit trail",            safety.get("complete_audit_trail")),
    ]
    rows_html = "".join(f"""
    <div class="pc-safety-row">
      <span class="{'pc-check-ok' if ok else 'pc-check-fail'}">{'✓' if ok else '✗'}</span>
      <span style="font-size:0.84rem; color:var(--text-primary);">{label}</span>
    </div>""" for label, ok in checks)

    hv  = safety.get("high_value_threshold")
    mr  = safety.get("max_automatic_retries")
    cap = f'<div style="font-size:0.72rem; color:var(--text-muted); margin-top:12px;">High-value threshold: {fmt_inr(hv)} · Max automatic retries: {mr}</div>' if hv else ""

    st.markdown(f'<div class="pc-card">{rows_html}{cap}</div>', unsafe_allow_html=True)

    vt = data.get("virtual_clock_time", "–")
    st.markdown(f'<div style="font-size:0.72rem; color:var(--text-muted); margin-top:8px;">Virtual clock: {str(vt)[:19]}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: DEMO SCENARIOS
# ══════════════════════════════════════════════════════════════════════════

elif page == "Demo Scenarios":
    page_header("Demo Scenarios", "Four deterministic cases — each guaranteed to show a different recovery path")

    data = api("GET", "/recovery/scenarios")
    if not data:
        st.stop()

    scenarios = data.get("scenarios", [])
    if not scenarios:
        empty_state("🎬", "No scenarios found. Run Reset Demo first.")
        st.stop()

    for sc in scenarios:
        key       = sc.get("key", "?")
        title     = sc.get("title", "")
        narrative = sc.get("narrative", "")
        case_id   = sc.get("case_id", "")
        state     = sc.get("current_state", "–")
        amount    = fmt_inr(sc.get("amount"))
        reason    = sc.get("failure_reason", "–")
        exp_act   = sc.get("expected_action", "–")
        exp_fin   = sc.get("expected_final_state", "–")
        needs_clk = sc.get("requires_clock_advance", False)

        badge_html  = state_badge_html(state)
        clock_note  = ' <span style="font-size:0.72rem; color:var(--text-muted);">· requires clock advance</span>' if needs_clk else ""

        with st.expander(f"Scenario {key} — {title}", expanded=True):
            st.markdown(f"""
            <div class="pc-scenario-header">
              <div class="pc-scenario-key">{key}</div>
              <div>
                <div style="font-weight:500; font-size:0.95rem; color:var(--text-primary);">{title}</div>
                <div style="font-size:0.72rem; color:var(--text-muted); margin-top:2px;">{case_id}</div>
              </div>
              <div style="margin-left:auto;">{badge_html}</div>
            </div>
            <div class="pc-narrative">{narrative}</div>
            """, unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            c1.metric("Amount at Risk", amount)
            c2.metric("Failure Reason", reason)
            c3.metric("Expected Action", exp_act)

            st.markdown(f"""
            <div style="font-size:0.75rem; color:var(--text-muted); margin: 10px 0 14px 0;">
              Expected outcome: <code>{exp_act}</code> → <code>{exp_fin}</code>{clock_note}
            </div>
            """, unsafe_allow_html=True)

            col_run, col_audit, col_space = st.columns([1, 1, 2])

            if col_run.button("Run cycle", key=f"run_{case_id}", type="primary"):
                with st.spinner("Running recovery cycle…"):
                    result = api("POST", f"/recovery/cases/{case_id}/run")
                if result:
                    action = result.get("selected_action") or "–"
                    new_state = result.get("state") or result.get("final_status") or "–"
                    st.success(f"Action: **{action}** → State: **{new_state}**")
                    msg = result.get("message", "")
                    if msg:
                        st.info(msg)

            if col_audit.button("Audit trail", key=f"audit_{case_id}"):
                audit = api("GET", f"/recovery/cases/{case_id}/audit")
                if audit:
                    events = audit.get("events", [])
                    if not events:
                        st.info("No audit events yet — run the cycle first.")
                    else:
                        rows_html = ""
                        for ev in events:
                            ts  = str(ev.get("timestamp", ""))[:19]
                            evt = ev.get("event_type", "")
                            msg = ev.get("message", "")
                            rows_html += f"""
                            <div class="pc-audit-row">
                              <div class="pc-audit-ts">{ts}</div>
                              <div class="pc-audit-type">{evt}</div>
                              <div class="pc-audit-msg">{msg}</div>
                            </div>"""
                        st.markdown(f"""
                        <div class="pc-card" style="margin-top:12px;">
                          <div class="pc-section-label">{len(events)} audit events</div>
                          {rows_html}
                        </div>
                        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: RECOVERY CASES
# ══════════════════════════════════════════════════════════════════════════

elif page == "Recovery Cases":
    page_header("Recovery Cases", "Browse and inspect all active and terminal recovery cases")

    import pandas as pd

    col_f, col_lim = st.columns([3, 1])
    with col_f:
        state_filter = st.selectbox("Filter by state", [
            "ALL","DETECTED","DIAGNOSING","DIAGNOSED","EVALUATING",
            "DECISION_READY","POLICY_CHECK","APPROVED","BLOCKED",
            "SCHEDULED","EXECUTING","VERIFYING","RECOVERED","FAILED",
            "ESCALATED","STOPPED",
        ])
    with col_lim:
        limit = st.number_input("Rows", 10, 100, 20, step=10)

    params: dict[str, Any] = {"limit": int(limit), "offset": 0}
    if state_filter != "ALL":
        params["state"] = state_filter

    data = api("GET", "/recovery/cases", params=params)
    if not data:
        st.stop()

    items = data.get("items", [])
    st.markdown(f'<div style="font-size:0.78rem; color:var(--text-muted); margin-bottom:10px;">Showing {len(items)} of {data.get("total", 0)} cases</div>', unsafe_allow_html=True)

    if items:
        df = pd.DataFrame([{
            "Case ID":       c["case_id"],
            "Payment ID":    c.get("payment_id", "–"),
            "State":         c.get("state", "–"),
            "Amount at Risk": fmt_inr(c.get("amount_at_risk")),
            "Created":       str(c.get("created_at") or "")[:19],
            "Updated":       str(c.get("updated_at") or "")[:19],
        } for c in items])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("📭", "No cases match this filter.")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    section_label("Inspect a case")

    selected_id = st.text_input("Case ID", placeholder="e.g. case_demo_a")
    if selected_id:
        detail = api("GET", f"/recovery/cases/{selected_id}")
        if detail:
            c1, c2, c3 = st.columns(3)
            c1.metric("State",         detail.get("state", "–"))
            c2.metric("Amount at Risk", fmt_inr(detail.get("amount_at_risk")))
            c3.metric("Terminal",      "Yes" if detail.get("is_terminal") else "No")

            wu = detail.get("waiting_until")
            if wu:
                st.info(f"⏳ Waiting until **{str(wu)[:19]}** — advance the Simulation Clock to unblock.")

            diag = detail.get("diagnosis")
            if diag:
                section_label("Diagnosis")
                st.json(diag)

            latest = detail.get("latest_action")
            if latest:
                section_label("Latest action")
                exp = latest.get("decision_explanation") or {}
                st.markdown(f"""
                <div class="pc-card pc-card-accent">
                  <div style="font-size:0.85rem;">
                    <strong>{latest.get("action_type", "–")}</strong> &nbsp;·&nbsp;
                    status <code>{latest.get("status", "–")}</code>
                  </div>
                  {"<div style='margin-top:8px; font-size:0.8rem; color:var(--text-muted);'>" + exp.get("reason","") + "</div>" if exp.get("reason") else ""}
                </div>
                """, unsafe_allow_html=True)

            if not detail.get("is_terminal"):
                if st.button("Run one cycle", type="primary", key="run_single"):
                    with st.spinner("Running…"):
                        result = api("POST", f"/recovery/cases/{selected_id}/run")
                    if result:
                        st.success(f"State: **{result.get('state')}** · Action: **{result.get('selected_action') or '–'}**")
                        if result.get("message"):
                            st.info(result["message"])
            else:
                st.markdown('<div class="pc-card"><div style="font-size:0.84rem; color:var(--text-muted);">This case is in a terminal state — no further runs permitted.</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: PAYMENTS
# ══════════════════════════════════════════════════════════════════════════

elif page == "Payments":
    page_header("Payments", "Browse the synthetic payment ledger")

    import pandas as pd

    col_f, col_lim = st.columns([3, 1])
    with col_f:
        status_filter = st.selectbox("Filter by status",
            ["ALL","CREATED","PENDING","SUCCEEDED","FAILED","ABANDONED"])
    with col_lim:
        limit = st.number_input("Rows", 10, 100, 20, step=10)

    params: dict[str, Any] = {"limit": int(limit), "offset": 0}
    if status_filter != "ALL":
        params["status"] = status_filter

    data = api("GET", "/payments", params=params)
    if not data:
        st.stop()

    items = data.get("items", [])
    st.markdown(f'<div style="font-size:0.78rem; color:var(--text-muted); margin-bottom:10px;">Showing {len(items)} of {data.get("total", 0)} payments</div>', unsafe_allow_html=True)

    if items:
        df = pd.DataFrame([{
            "Payment ID": p["payment_id"],
            "Amount":     fmt_inr(p.get("money")),
            "Status":     p.get("status", "–"),
            "Method":     p.get("payment_method", "–"),
            "Failure":    p.get("failure_reason") or "–",
            "Attempts":   p.get("attempt_count", 0),
            "Customer":   p.get("customer_id", "–"),
            "Created":    str(p.get("created_at") or "")[:19],
        } for p in items])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        empty_state("💳", "No payments match this filter.")

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
    section_label("Inspect a payment")

    pid = st.text_input("Payment ID", placeholder="e.g. pay_demo_a")
    if pid:
        pdata = api("GET", f"/payments/{pid}")
        if pdata:
            c1, c2, c3 = st.columns(3)
            c1.metric("Status",   pdata.get("status", "–"))
            c2.metric("Amount",   fmt_inr(pdata.get("money")))
            c3.metric("Method",   pdata.get("payment_method", "–"))
            c4, c5 = st.columns(2)
            c4.metric("Attempts", pdata.get("attempt_count", 0))
            c5.metric("Failure",  pdata.get("failure_reason") or "–")

            attempts = pdata.get("attempts", [])
            if attempts:
                section_label(f"{len(attempts)} attempt(s)")
                rows_html = ""
                for att in attempts:
                    ts  = str(att.get("attempted_at", ""))[:19]
                    num = att.get("attempt_number", "?")
                    st_ = att.get("status", "–")
                    fr  = att.get("failure_reason") or "–"
                    rows_html += f"""
                    <div class="pc-audit-row">
                      <div class="pc-audit-ts">{ts}</div>
                      <div class="pc-audit-type">Attempt #{num}</div>
                      <div class="pc-audit-msg">{st_} · {fr}</div>
                    </div>"""
                st.markdown(f'<div class="pc-card">{rows_html}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: AUTOPILOT
# ══════════════════════════════════════════════════════════════════════════

elif page == "Autopilot":
    page_header("Autopilot", "Drive every pending case to a terminal state in one batch run")

    st.markdown("""
    <div class="pc-card" style="margin-bottom:20px;">
      <div style="font-size:0.85rem; color:var(--text-muted); line-height:1.6;">
        Autopilot processes all non-terminal cases through the same recovery workflow
        used by single-case runs. Delayed retries are clock-advanced automatically,
        so the batch always produces terminal outcomes — nothing is left scheduled.
      </div>
    </div>
    """, unsafe_allow_html=True)

    limit = st.number_input("Maximum cases to process", 1, 200, 50, step=10)

    if st.button("Run Autopilot", type="primary"):
        with st.spinner("Processing batch — this may take a moment…"):
            result = api("POST", "/recovery/autopilot", json={"limit": int(limit)})

        if result:
            section_label("Batch results")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Cases",    result.get("total_cases", 0))
            c2.metric("Recovered",      result.get("cases_recovered", 0))
            c3.metric("Recovery Rate",  pct(result.get("recovery_rate")))
            c4.metric("Total Recovered", fmt_inr(result.get("total_recovered")))

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Stopped",          result.get("cases_stopped", 0))
            c6.metric("Escalated",        result.get("cases_escalated", 0))
            c7.metric("Actions Executed", result.get("actions_executed", 0))
            c8.metric("Total at Risk",    fmt_inr(result.get("total_at_risk")))

            import pandas as pd
            cases = result.get("results", [])
            if cases:
                st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
                section_label(f"Per-case detail — {len(cases)} cases")
                rows = [{
                    "Case ID":     c["case_id"],
                    "Failure":     c.get("failure_reason", "–"),
                    "Method":      c.get("payment_method", "–"),
                    "At Risk":     fmt_inr(c.get("amount_at_risk")),
                    "Recovered":   fmt_inr(c.get("recovered_amount")),
                    "Final State": c.get("final_state", "–"),
                    "Action":      c.get("selected_action") or "–",
                    "Policy":      c.get("policy_outcome") or "–",
                    "Runs":        c.get("runs", 0),
                } for c in cases]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: STRATEGY LAB
# ══════════════════════════════════════════════════════════════════════════

elif page == "Strategy Lab":
    page_header("Strategy Lab", "Compare every recovery action for one case — read-only, no state changes")

    col_id, col_btn = st.columns([3, 1])
    with col_id:
        case_id = st.text_input("Case ID to analyse", value="case_demo_a", placeholder="e.g. case_demo_a")

    section_label("Policy overrides (optional)")
    col1, col2, col3 = st.columns(3)
    with col1:
        max_retries = st.number_input("Max automatic retries", 0, 10, 2)
    with col2:
        hv_threshold = st.number_input("High-value threshold (paise)", 100_000, 50_000_000, 5_000_000, step=100_000,
                                        help="5000000 paise = ₹50,000")
    with col3:
        delay_min = st.number_input("Retry-later delay (minutes)", 1, 120, 15)

    if st.button("Evaluate strategies", type="primary"):
        payload = {
            "max_automatic_retries": int(max_retries),
            "high_value_escalation_threshold": int(hv_threshold),
            "retry_later_delay_minutes": int(delay_min),
        }
        with st.spinner("Evaluating all strategies…"):
            result = api("POST", f"/recovery/cases/{case_id}/simulate", json=payload)

        if result:
            c1, c2, c3 = st.columns(3)
            c1.metric("Amount",             fmt_inr(result.get("amount")))
            c2.metric("Failure Reason",     result.get("failure_reason", "–"))
            c3.metric("Recommended Action", result.get("recommended_action") or "None")

            reason = result.get("recommendation_reason", "")
            if reason:
                st.markdown(f'<div class="pc-card" style="margin-top:14px; font-size:0.83rem; color:var(--text-muted); line-height:1.55;">{reason}</div>', unsafe_allow_html=True)

            options = result.get("options", [])
            if options:
                import pandas as pd
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                section_label("All strategy options — ranked by expected recovery value")
                rows = [{
                    "Action":      ("⭐ " if o.get("is_recommended") else "") + o["action"],
                    "Probability": pct(o.get("probability")),
                    "Confidence":  f"{o.get('confidence', 0):.2f}",
                    "ERV":         fmt_inr(o.get("expected_recovery_value")),
                    "Policy":      o.get("policy_outcome", "–"),
                    "Rule":        o.get("policy_rule_id") or "–",
                    "Risk":        o.get("risk_level", "–"),
                    "Eligible":    "Yes" if o.get("eligible") else "No",
                } for o in options]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            customer = result.get("customer", {})
            if customer:
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                section_label("Customer context")
                cc1, cc2, cc3, cc4, cc5 = st.columns(5)
                cc1.metric("Total Payments",   customer.get("total_payments", 0))
                cc2.metric("Successful",       customer.get("successful_payments", 0))
                cc3.metric("Success Rate",     pct(customer.get("success_rate")))
                cc4.metric("Avg Value",        fmt_inr(customer.get("average_transaction_value")))
                cc5.metric("Subscription",     customer.get("subscription_status", "–"))


# ══════════════════════════════════════════════════════════════════════════
# PAGE: SIMULATION CLOCK
# ══════════════════════════════════════════════════════════════════════════

elif page == "Simulation Clock":
    page_header("Simulation Clock", "Advance virtual time to trigger scheduled retries")

    clock_data = api("GET", "/simulate/clock")
    vt = str(clock_data.get("virtual_clock_time", "–"))[:19] if clock_data else "–"
    date_part = vt[:10] if len(vt) >= 10 else vt
    time_part = vt[11:] if len(vt) >= 16 else ""

    st.markdown(f"""
    <div class="pc-clock-label">Current simulation time</div>
    <div class="pc-clock-display">
      {date_part}
      <span style="color:var(--text-muted); font-size:1.2rem; margin:0 8px;">·</span>
      {time_part}
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="pc-card" style="margin-bottom:20px; font-size:0.83rem; color:var(--text-muted); line-height:1.55;">
      The clock never moves on its own. Advance it to make a scheduled
      <code>RETRY_LATER</code> case become due, then run its cycle to execute the retry.
    </div>
    """, unsafe_allow_html=True)

    section_label("Advance by")
    col_h, col_m = st.columns(2)
    with col_h:
        hours   = st.number_input("Hours",   0, 72, 0)
    with col_m:
        minutes = st.number_input("Minutes", 0, 59, 20)

    if st.button("Advance clock", type="primary"):
        total = int(hours) * 60 + int(minutes)
        if total == 0:
            st.warning("Enter at least 1 minute or 1 hour.")
        else:
            with st.spinner("Advancing…"):
                result = api("POST", "/simulate/advance-clock",
                             json={"hours": int(hours), "minutes": int(minutes)})
            if result:
                new_vt = str(result.get("virtual_clock_time", "–"))[:19]
                adv    = result.get("advanced_by_minutes", total)
                st.success(f"Advanced by **{adv} minutes** — clock is now **{new_vt}**")
                st.info("Scheduled cases that are now due will execute on their next run.")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: RESET DEMO
# ══════════════════════════════════════════════════════════════════════════

elif page == "Reset Demo":
    page_header("Reset Demo", "Rebuild the synthetic dataset from scratch")

    st.markdown("""
    <div class="pc-danger-box">
      <div class="pc-danger-title">Destructive operation</div>
      <div class="pc-danger-desc">
        All tables are dropped and recreated. The virtual clock resets to its
        starting position. Four deterministic demo scenarios are seeded alongside
        a configurable number of background cases. No real payment data is involved.
      </div>
    </div>
    """, unsafe_allow_html=True)

    bg = st.number_input(
        "Background customers",
        min_value=0, max_value=60, value=12, step=4,
        help="Synthetic customers seeded around the 4 main demo cases."
    )

    if st.button("Reset now", type="primary"):
        with st.spinner("Dropping tables, reseeding data, resetting clock…"):
            result = api("POST", "/demo/reset", json={"background_customers": int(bg)})

        if result:
            c1, c2, c3 = st.columns(3)
            c1.metric("Customers", result.get("customers", 0))
            c2.metric("Payments",  result.get("payments", 0))
            c3.metric("Cases",     result.get("cases", 0))

            vt = str(result.get("virtual_clock_time", "–"))[:19]
            st.success(f"Reset complete — virtual clock at **{vt}**")

            scenarios = result.get("scenarios", [])
            if scenarios:
                st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
                section_label("Seeded scenarios")
                for sc in scenarios:
                    key    = sc.get("key", "?")
                    title  = sc.get("title", "")
                    cid    = sc.get("case_id", "")
                    amount = fmt_inr(sc.get("amount"))
                    exp    = sc.get("expected_final_state", "")
                    st.markdown(f"""
                    <div class="pc-card" style="margin-bottom:8px; display:flex; align-items:center; gap:14px;">
                      <div class="pc-scenario-key">{key}</div>
                      <div style="flex:1;">
                        <div style="font-size:0.88rem; font-weight:500; color:var(--text-primary);">{title}</div>
                        <div style="font-size:0.72rem; color:var(--text-muted); margin-top:3px;">{cid} · {amount} · expected: {exp}</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("""
                <div style="font-size:0.83rem; color:var(--text-muted); margin-top:12px;">
                  ↗ Go to <strong>Demo Scenarios</strong> and click <strong>Run cycle</strong>
                  on each scenario to walk through the recovery workflow.
                </div>
                """, unsafe_allow_html=True)
