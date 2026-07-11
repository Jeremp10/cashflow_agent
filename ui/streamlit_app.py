import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="Cashflow Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: #1e2130;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #2d3250;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #8b92a5;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .positive { color: #00c48c; }
    .negative { color: #ff6b6b; }
    .warning  { color: #ffd166; }
    .chat-message-user {
        background: #1e2130;
        border-radius: 12px;
        padding: 12px 16px;
        margin: 8px 0;
        border-left: 3px solid #4a6fa5;
    }
    .chat-message-assistant {
        background: #161b2e;
        border-radius: 12px;
        padding: 12px 16px;
        margin: 8px 0;
        border-left: 3px solid #00c48c;
    }
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        font-weight: 600;
    }
    div[data-testid="stSidebarContent"] {
        background: #161b2e;
    }
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────────────────────────

def api_get(endpoint: str):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API. Make sure `uvicorn api.main:app --reload --port 8000` is running.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(endpoint: str, payload: dict):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to API.")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


# ── Session state ─────────────────────────────────────────────────────────────

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "forecast_data" not in st.session_state:
    st.session_state.forecast_data = None

if "balance" not in st.session_state:
    st.session_state.balance = None

if "last_synced" not in st.session_state:
    st.session_state.last_synced = None
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Cashflow Agent")
    st.markdown("---")

    # Connection status
    health = api_get("/health")
    if health:
        st.success("API Connected")
    else:
        st.error("API Offline")

    st.markdown("---")

    # Sync button
    st.markdown("### Data Sync")
    if st.button("Sync Plaid + QuickBooks", type="primary"):
        with st.spinner("Syncing data from Plaid and QuickBooks..."):
            result = api_post("/sync", {})
            if result:
                if result["plaid_synced"]:
                    st.success("Plaid synced")
                else:
                    st.warning("Plaid sync failed")
                if result["qbo_synced"]:
                    st.success("QuickBooks synced")
                else:
                    st.warning("QuickBooks sync failed")
                st.session_state.last_synced = datetime.now().strftime("%H:%M:%S")
                # Refresh forecast after sync
                st.session_state.forecast_data = None
                st.session_state.balance = None

    if st.session_state.last_synced:
        st.caption(f"Last synced: {st.session_state.last_synced}")

    st.markdown("---")

    # Navigation
    st.markdown("### Navigation")
    page = st.radio(
        "Go to",
        ["Dashboard", "Ask Your CFO"],
        label_visibility="collapsed",
        index=["Dashboard", " Ask Your CFO"].index(st.session_state.page),
    key="nav_radio"
    )
    st.session_state.page = page

    st.markdown("---")
    st.caption("Powered by Plaid · QuickBooks · Claude AI")


# ── Load data ─────────────────────────────────────────────────────────────────

# Cache balance + forecast in session state to avoid re-fetching on every rerender
if st.session_state.balance is None:
    with st.spinner("Fetching balance..."):
        balance_data = api_get("/balance")
        if balance_data:
            st.session_state.balance = balance_data["current_balance"]

if st.session_state.forecast_data is None:
    with st.spinner("Running forecast..."):
        forecast_data = api_get("/forecast")
        if forecast_data:
            st.session_state.forecast_data = forecast_data


# ── Dashboard page ────────────────────────────────────────────────────────────

if page == "Dashboard":
    st.markdown("# Financial Dashboard")
    st.markdown(f"*As of {datetime.now().strftime('%B %d, %Y')}*")
    st.markdown("---")

    if st.session_state.balance is not None and st.session_state.forecast_data is not None:
        balance = st.session_state.balance
        forecast = st.session_state.forecast_data
        projected = forecast["projected_balance"]
        trend = forecast["trend"]
        alert = forecast["low_balance_alert"]

        # ── Key metrics row ──
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Current Balance",
                value=f"${balance:,.2f}",
            )

        with col2:
            delta = projected - balance
            st.metric(
                label="Projected Balance (30d)",
                value=f"${projected:,.2f}",
                delta=f"${delta:,.2f}",
                delta_color="normal",
            )

        with col3:
            trend_icon = "📈" if trend == "positive" else "📉"
            st.metric(
                label="Trend",
                value=f"{trend_icon} {trend.capitalize()}",
            )

        with col4:
            st.metric(
                label="Forecast Period",
                value=f"{forecast['forecast_days']} days",
            )

        st.markdown("---")

        # ── Alert banner ──
        if "drop below" in alert:
            st.warning(f" {alert}")
        else:
            st.success(f" {alert}")

        st.markdown("---")

        # ── Balance gauge ──
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Current vs Projected Balance")
            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=["Current Balance", "Projected Balance (30d)"],
                y=[balance, max(projected, 0)],
                marker_color=["#4a6fa5", "#00c48c" if projected > 0 else "#ff6b6b"],
                text=[f"${balance:,.2f}", f"${projected:,.2f}"],
                textposition="auto",
            ))

            fig.update_layout(
                plot_bgcolor="#1e2130",
                paper_bgcolor="#1e2130",
                font_color="#ffffff",
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_right:
            st.markdown("#### Cash Flow Summary")
            st.markdown(f"""
| | Amount |
|---|---|
|  Current liquid balance | **${balance:,.2f}** |
|  30-day projected balance | **${projected:,.2f}** |
|  Outstanding invoices (QBO) | **to be collected** |
|  Unpaid bills (QBO) | **due out** |
|  Forecast trend | **{trend.capitalize()}** |
""")

        st.markdown("---")
        st.markdown("####  Quick Insights")

        q_col1, q_col2, q_col3 = st.columns(3)
        with q_col1:
            if st.button("Will I make payroll?"):
                st.session_state.chat_history = []
                answer = api_post("/ask", {
                    "question": "Will I make payroll this month?",
                    "current_balance": st.session_state.balance or 320.0
                        })
                if answer:
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "Will I make payroll this month?"
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer["answer"]
                    })
                    st.session_state.page = " Ask Your CFO"
                    st.rerun()

        with q_col2:
            if st.button("What are my biggest expenses?"):
                st.session_state.chat_history = []
                answer = api_post("/ask", {
                    "question": "What are my biggest expenses?",
                    "current_balance": st.session_state.balance or 320.0
                })
                if answer:
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "What are my biggest expenses?"
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer["answer"]
                    })
                    st.session_state.page = " Ask Your CFO"
                    st.rerun()

        with q_col3:
            if st.button("Should I be worried?"):
                st.session_state.chat_history = []
                answer = api_post("/ask", {
                    "question": "Should I be worried about my cash flow?",
                    "current_balance": st.session_state.balance or 320.0
                })

                if answer:
                    st.session_state.chat_history.append({
                        "role": "user",
                        "content": "Should I be worried about my cash flow?"
                    })
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer["answer"]
                    })
                    st.session_state.page = " Ask Your CFO"
                    st.rerun()

    else:
        st.info("No data loaded yet. Click **Sync Plaid + QuickBooks** in the sidebar to get started.")


# ── Chat page ─────────────────────────────────────────────────────────────────

elif page == " Ask Your CFO":
    st.markdown("#  Ask Your CFO")
    st.markdown("*Ask anything about your cash flow, expenses, invoices, or financial health.*")
    st.markdown("---")

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"""
<div class="chat-message-user">
<strong>You:</strong><br>{msg['content']}
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
<div class="chat-message-assistant">
<strong>CFO Agent:</strong><br>{msg['content']}
</div>
""", unsafe_allow_html=True)

    # Input
    st.markdown("---")
    col_input, col_send = st.columns([5, 1])

    with col_input:
        user_input = st.text_input(
            "Ask a question",
            placeholder="e.g. Will I have enough cash to hire someone next month?",
            label_visibility="collapsed",
            key="chat_input"
        )

    with col_send:
        send = st.button("Send →", type="primary")

    # Suggested questions
    st.markdown("**Suggested questions:**")
    sug_col1, sug_col2, sug_col3, sug_col4 = st.columns(4)

    suggestions = [
        "What's my cash runway?",
        "When will I run out of cash?",
        "Which invoices should I chase first?",
        "How does this month compare to last?",
    ]

    for i, (col, suggestion) in enumerate(zip(
        [sug_col1, sug_col2, sug_col3, sug_col4], suggestions
    )):
        with col:
            if st.button(suggestion, key=f"sug_{i}"):
                with st.spinner("Thinking..."):
                    answer = api_post("/ask", {
                    "question": "Will I make payroll this month?",
                    "current_balance": st.session_state.balance or 320.0
                        })
                    if answer:
                        st.session_state.chat_history.append({
                            "role": "user", "content": suggestion
                        })
                        st.session_state.chat_history.append({
                            "role": "assistant", "content": answer["answer"]
                        })
                        st.rerun()

    # Handle send
    if send and user_input.strip():
        with st.spinner("Your CFO is thinking..."):
            answer = api_post("/ask", {
                    "question": "Will I make payroll this month?",
                    "current_balance": st.session_state.balance or 320.0
                        })
            if answer:
                st.session_state.chat_history.append({
                    "role": "user", "content": user_input.strip()
                })
                st.session_state.chat_history.append({
                    "role": "assistant", "content": answer["answer"]
                })
                st.rerun()

    # Clear conversation
    if st.session_state.chat_history:
        st.markdown("---")
        if st.button("Clear conversation"):
            api_post("/reset", {})
            st.session_state.chat_history = []
            st.rerun()
