import streamlit as st
import requests
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
        st.error("Cannot connect to API. Make sure uvicorn is running on port 8000.")
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


# ── Cache helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def check_health():
    return api_get("/health")


@st.cache_data(ttl=300)
def fetch_validation():
    return api_get("/forecast/validation")


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

    health = check_health()
    if health:
        st.success("API Connected")
    else:
        st.error("API Offline")

    st.markdown("---")

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
                st.session_state.forecast_data = None
                st.session_state.balance = None

    if st.session_state.last_synced:
        st.caption(f"Last synced: {st.session_state.last_synced}")

    st.markdown("---")

    st.markdown("### Navigation")
    PAGE_OPTIONS = ["Dashboard", "Ask Your CFO"]

    page = st.radio(
        "Go to",
        PAGE_OPTIONS,
        label_visibility="collapsed",
        index=PAGE_OPTIONS.index(st.session_state.page) if st.session_state.page in PAGE_OPTIONS else 0,
        key=f"nav_radio_{st.session_state.page}"
    )
    st.session_state.page = page

    st.markdown("---")
    st.caption("Powered by Plaid · QuickBooks · Claude AI")


# ── Load data ─────────────────────────────────────────────────────────────────

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


# ── Helper ────────────────────────────────────────────────────────────────────

def send_quick_question(question: str):
    with st.spinner("Thinking..."):
        answer = api_post("/ask", {
            "question": question,
            "current_balance": st.session_state.balance or 0.0
        })
        if answer:
            st.session_state.chat_history = []
            st.session_state.chat_history.append({"role": "user", "content": question})
            st.session_state.chat_history.append({"role": "assistant", "content": answer["answer"]})
            st.session_state.page = "Ask Your CFO"
            st.rerun()


# ── Dashboard ─────────────────────────────────────────────────────────────────

if st.session_state.page == "Dashboard":
    st.markdown("# Financial Dashboard")
    st.markdown(f"*As of {datetime.now().strftime('%B %d, %Y')}*")
    st.markdown("---")

    if st.session_state.balance is not None and st.session_state.forecast_data is not None:
        balance = st.session_state.balance
        forecast = st.session_state.forecast_data
        projected = forecast["projected_balance"]
        trend = forecast["trend"]
        alert = forecast["low_balance_alert"]

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(label="Current Balance", value=f"${balance:,.2f}")
        with col2:
            delta = projected - balance
            st.metric(label="Projected Balance (30d)", value=f"${projected:,.2f}", delta=f"${delta:,.2f}", delta_color="normal")
        with col3:
            st.metric(label="Trend", value="Positive" if trend == "positive" else "Negative")
        with col4:
            st.metric(label="Forecast Period", value=f"{forecast['forecast_days']} days")

        st.markdown("---")

        if "drop below" in alert:
            st.warning(alert)
        else:
            st.success(alert)

        st.markdown("---")

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("#### Current vs Projected Balance")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=["Current Balance", "Projected Balance (30d)"],
                y=[balance, projected],
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
| Current liquid balance | **${balance:,.2f}** |
| 30-day projected balance | **${projected:,.2f}** |
| Forecast trend | **{trend.capitalize()}** |
""")

        st.markdown("---")

        # ── Model Health ──────────────────────────────────────────────────────
        with st.expander("Model Health"):
            validation = fetch_validation()

            if validation and "error" not in validation:
                v_col1, v_col2, v_col3 = st.columns(3)

                with v_col1:
                    st.metric(
                        label="Avg Daily Error (MAE)",
                        value=f"${validation['mae']:,.0f}",
                        help="Average dollar difference between forecast and actual per day"
                    )
                with v_col2:
                    st.metric(
                        label="Error Rate (MAPE)",
                        value=f"{validation['mape']:.1f}%",
                        help="Average percentage error — lower is better"
                    )
                with v_col3:
                    st.metric(
                        label="Data Points",
                        value=validation["data_points"],
                        help="Number of days used to train the model"
                    )

                st.caption(validation["interpretation"])
                st.info(
                    "Forecast accuracy improves naturally as more transaction history "
                    "accumulates. With 3-6 months of data, error rates typically drop "
                    "significantly. Current metrics reflect your available history."
                )

            elif validation and "error" in validation:
                st.warning(validation["error"])
            else:
                st.caption("Model health data unavailable. Make sure the API is running.")

        st.markdown("---")
        st.markdown("#### Quick Insights")
        st.markdown("Click a question to get an instant answer from your CFO agent.")

        q_col1, q_col2, q_col3 = st.columns(3)
        with q_col1:
            if st.button("Will I make payroll?"):
                send_quick_question("Will I make payroll this month?")
        with q_col2:
            if st.button("What are my biggest expenses?"):
                send_quick_question("What are my biggest expenses?")
        with q_col3:
            if st.button("Should I be worried?"):
                send_quick_question("Should I be worried about my cash flow?")

    else:
        st.info("No data loaded yet. Click Sync Plaid + QuickBooks in the sidebar to get started.")


# ── Chat page ─────────────────────────────────────────────────────────────────

elif st.session_state.page == "Ask Your CFO":
    st.markdown("# Ask Your CFO")
    st.markdown("*Ask anything about your cash flow, expenses, invoices, or financial health.*")
    st.markdown("---")

    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])

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
                        "question": suggestion,
                        "current_balance": st.session_state.balance or 0.0
                    })
                    if answer:
                        st.session_state.chat_history.append({"role": "user", "content": suggestion})
                        st.session_state.chat_history.append({"role": "assistant", "content": answer["answer"]})
                        st.rerun()

    st.markdown("---")

    user_input = st.chat_input("Ask your CFO anything...")

    if user_input:
        with st.spinner("Your CFO is thinking..."):
            answer = api_post("/ask", {
                "question": user_input.strip(),
                "current_balance": st.session_state.balance or 0.0
            })
            if answer:
                st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
                st.session_state.chat_history.append({"role": "assistant", "content": answer["answer"]})
                st.rerun()

    st.markdown("---")
    if st.session_state.chat_history:
        if st.button("Clear conversation"):
            api_post("/reset", {})
            st.session_state.chat_history = []
            st.rerun()
