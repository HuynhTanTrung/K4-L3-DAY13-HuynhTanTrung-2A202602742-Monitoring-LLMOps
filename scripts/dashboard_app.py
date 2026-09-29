from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

LOG_PATH = Path("data/logs.jsonl")
TIME_RANGE_MIN = 60
REFRESH_SEC = 30

st.set_page_config(page_title="Day 13 — Monitoring Dashboard", layout="wide")
st.title("K4-L3A Day 13 Monitoring & LLMOps")
st.caption(f"Source: {LOG_PATH} | Time range: last {TIME_RANGE_MIN} min | Refresh: {REFRESH_SEC}s")


@st.cache_data(ttl=REFRESH_SEC)
def load_logs() -> pd.DataFrame:
    rows = []
    if not LOG_PATH.exists():
        return pd.DataFrame()
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    df = pd.DataFrame(rows)
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True, errors="coerce")
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=TIME_RANGE_MIN)
        df = df[df["ts"] >= cutoff]
    return df


df = load_logs()

if df.empty:
    st.warning("No log data. Run the API and a load test first.")
    st.stop()

responses = df[df["event"] == "response_sent"]
requests = df[df["event"] == "request_received"]
failures = df[df["event"] == "request_failed"]

# ── Panel 1: Latency ─────────────────────────────────────────────
st.subheader("1. Latency percentiles and TTFT (ms)")
if not responses.empty and "latency_ms" in responses:
    lat = responses["latency_ms"].dropna()
    ttft = responses["ttft_ms"].dropna() if "ttft_ms" in responses else pd.Series(dtype=float)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("P50 latency", f"{lat.quantile(0.50):.0f} ms")
    c2.metric("P95 latency", f"{lat.quantile(0.95):.0f} ms",
              delta=f"{'OK' if lat.quantile(0.95) <= 3000 else 'BREACH'} (SLO ≤3000)")
    c3.metric("P99 latency", f"{lat.quantile(0.99):.0f} ms")
    c4.metric("TTFT P95", f"{ttft.quantile(0.95):.0f} ms" if not ttft.empty else "n/a")
else:
    st.info("No response_sent events in range.")

# ── Panel 2: Traffic ─────────────────────────────────────────────
st.subheader("2. Request traffic (requests/min)")
if not requests.empty and "ts" in requests:
    per_min = requests.set_index("ts").resample("1min").size()
    st.line_chart(per_min, height=180)
else:
    st.info("No request_received events in range.")

# ── Panel 3: Errors ──────────────────────────────────────────────
st.subheader("3. Error rate and retrieval success (%)")
col1, col2 = st.columns(2)
with col1:
    total = len(requests) + len(failures)
    err_pct = (len(failures) / total * 100) if total else 0.0
    st.metric("Error rate", f"{err_pct:.2f} %",
              delta=f"{'OK' if err_pct <= 2 else 'BREACH'} (SLO ≤2%)")
with col2:
    if "tool_success" in responses:
        valid = responses["tool_success"].dropna()
        ok_pct = (valid.sum() / len(valid) * 100) if len(valid) else 0.0
        st.metric("Retrieval success", f"{ok_pct:.1f} %",
                  delta=f"{'OK' if ok_pct >= 90 else 'BREACH'} (min 90%)")
    else:
        st.metric("Retrieval success", "n/a")

# ── Panel 4: Cost ────────────────────────────────────────────────
st.subheader("4. Cost over time (USD)")
if not responses.empty and "cost_usd" in responses:
    total_cost = responses["cost_usd"].sum()
    st.metric("Total cost", f"${total_cost:.4f}",
              delta=f"{'OK' if total_cost <= 2.5 else 'BREACH'} (max $2.5)")
    per_min_cost = responses.set_index("ts")["cost_usd"].resample("1min").sum()
    st.bar_chart(per_min_cost, height=180)
else:
    st.info("No cost data.")

# ── Panel 5: Tokens ──────────────────────────────────────────────
st.subheader("5. Input and output tokens")
if not responses.empty:
    tin = responses["tokens_in"].sum() if "tokens_in" in responses else 0
    tout = responses["tokens_out"].sum() if "tokens_out" in responses else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Tokens in", f"{tin:,}")
    c2.metric("Tokens out", f"{tout:,}")
    c3.metric("Total", f"{tin + tout:,}",
              delta=f"{'OK' if tin + tout <= 50000 else 'BREACH'} (max 50k)")

# ── Panel 6: Quality ─────────────────────────────────────────────
st.subheader("6. Quality proxy (0–1)")
if not responses.empty and "quality_score" in responses:
    q = responses["quality_score"].dropna()
    mean_q = q.mean() if len(q) else 0.0
    st.metric("Mean quality score", f"{mean_q:.3f}",
              delta=f"{'OK' if mean_q >= 0.75 else 'BREACH'} (min 0.75)")
    st.line_chart(responses.set_index("ts")["quality_score"], height=180)
else:
    st.info("No quality data.")

st.caption(f"Last refresh: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")