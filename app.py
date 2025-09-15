# app.py
import streamlit as st
import pandas as pd
import pickle as pkl
from pathlib import Path

# ---------- Page setup ----------
st.set_page_config(
    page_title="IPL Win Probability",
    page_icon="🏏",
    layout="wide",
    menu_items={
        "Report a bug": None,
        "About": "Win probability predictor for IPL run-chases."
    },
)
# ---------- Custom Background Color ----------
# ---------- Custom Background (Gradient) ----------
# ---------- Custom Background (Pattern) ----------





# ---------- Minimal theming & CSS ----------
PRIMARY = "#5B8DEF"
SUCCESS = "#2BA84A"
DANGER = "#E74C3C"
MUTED = "#8892a0"

st.markdown(
    f"""
    <style>
      .app-title {{
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: .2px;
        margin-bottom: .25rem;
      }}
      .subtitle {{
        color: {MUTED};
        margin-bottom: 1rem;
      }}
      .card {{
        border: 1px solid rgba(0,0,0,0.08);
        padding: 1rem 1.25rem;
        border-radius: 14px;
        background: rgba(255,255,255,0.65);
      }}
      .pill {{
        display:inline-block;
        padding: .25rem .6rem;
        border-radius: 999px;
        font-size: .8rem;
        border: 1px solid rgba(0,0,0,.1);
        color: {MUTED};
        margin-left: .5rem;
      }}
      .kpi-title {{
        color: {MUTED};
        font-size: .9rem;
        margin-bottom: .25rem;
      }}
      .kpi-value {{
        font-size: 1.6rem;
        font-weight: 700;
      }}
      .prob-bar {{
        height: 16px;
        border-radius: 999px;
        background: #e9ecef;
        overflow: hidden;
        position: relative;
      }}
      .prob-fill {{
        height: 100%;
        transition: width .5s ease;
      }}
      .prob-label {{
        font-weight: 700;
        font-size: 1rem;
      }}
      .footer-note {{
        color: {MUTED};
        font-size: 0.85rem;
        margin-top: .75rem;
      }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Load artifacts ----------
@st.cache_resource(show_spinner=False)
def load_artifacts():
    app_dir = Path(__file__).parent.resolve()
    art = app_dir / "artifacts"
    team_p = art / "team.pkl"
    city_p = art / "city.pkl"
    model_p = art / "model.pkl"

    if not (team_p.is_file() and city_p.is_file() and model_p.is_file()):
        st.error("Could not load required files from ./artifacts.")
        st.caption(f"Checked: {team_p.name}: {team_p.exists()}, {city_p.name}: {city_p.exists()}, {model_p.name}: {model_p.exists()}")
        st.stop()

    teams  = pkl.load(open(team_p, "rb"))
    cities = pkl.load(open(city_p, "rb"))
    model  = pkl.load(open(model_p, "rb"))
    return teams, cities, model, None
    # except Exception as e:
    #     return None, None, None, e

teams, cities, model, load_error = load_artifacts()

# ---------- Header ----------
st.markdown('<div class="app-title">🏏 IPL Win Probability Prediction</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Estimate the chasing team’s win chance in real time. Add the current match context and get instant probabilities.</div>',
    unsafe_allow_html=True,
)

if load_error:
    st.error(f"Could not load required files. Make sure `team.pkl`, `city.pkl`, and `model.pkl` are present.\n\nError: {load_error}")
    st.stop()

# ---------- Sidebar (help & instructions) ----------
with st.sidebar:
    st.header("How it works")
    st.write(
        """
        • Pick the **batting** and **bowling** teams and the **city**.  
        • Enter the **target**, **current score**, **overs completed**, and **wickets fallen**.  
        • Click **Predict** to see the probabilities.
        """
    )
    with st.expander("Feature definitions"):
        st.markdown(
            """
            - **CRR**: Current Run Rate (runs/over).  
            - **RRR**: Required Run Rate (runs/over).  
            - **Remaining Balls**: `120 - 6 × overs_completed`.  
            - **Wickets Left**: `10 - wickets_fallen`.  
            - **Target Left**: `target - score`.
            """
        )
    st.divider()
    st.caption("Tip: Use integer overs only (e.g., 12, 13). If you want ball-precision, store balls separately (e.g., 12.3 → 12 overs, 3 balls).")

# ---------- Input Form ----------
with st.form("input_form", clear_on_submit=False):
    top_cols = st.columns(3)
    with top_cols[0]:
        batting_team = st.selectbox("Batting Team", sorted(teams))
    with top_cols[1]:
        bowling_team = st.selectbox("Bowling Team", sorted(teams), index=1 if len(teams) > 1 else 0)
    with top_cols[2]:
        selected_city = st.selectbox("City", sorted(cities))

    mid_cols = st.columns(4)
    with mid_cols[0]:
        target = st.number_input("Target Score", min_value=0, max_value=500, step=1, value=160)
    with mid_cols[1]:
        score = st.number_input("Current Score", min_value=0, max_value=500, step=1, value=82)
    with mid_cols[2]:
        overs = st.number_input("Overs Completed (0–20)", min_value=0, max_value=20, step=1, value=11)
    with mid_cols[3]:
        wickets = st.number_input("Wickets Fallen (0–10)", min_value=0, max_value=10, step=1, value=2)

    submitted = st.form_submit_button("🔮 Predict Probability", use_container_width=True)

# ---------- Validation ----------
def validate_inputs():
    problems = []
    if batting_team == bowling_team:
        problems.append("Batting and bowling teams must be different.")
    if overs > 20:
        problems.append("Overs completed cannot exceed 20.")
    if wickets > 10:
        problems.append("Wickets fallen cannot exceed 10.")
    if target < 0 or score < 0:
        problems.append("Target and score must be non-negative.")
    return problems

# ---------- Prediction ----------
def compute_and_predict():
    runs_left = target - score
    balls_left = 120 - (overs * 6)
    wickets_left = 10 - wickets

    # Handle edge cases
    crr = (score / overs) if overs > 0 else 0.0
    rrr = (runs_left * 6 / balls_left) if balls_left > 0 else float("inf")

    # Early outcomes
    if runs_left <= 0:
        return {
            "input_df": None,
            "win_prob": 1.0,
            "loss_prob": 0.0,
            "runs_left": runs_left,
            "balls_left": balls_left,
            "wickets_left": wickets_left,
            "crr": crr,
            "rrr": rrr,
            "decided": f"{batting_team} already reached the target."
        }
    if balls_left <= 0:
        return {
            "input_df": None,
            "win_prob": 0.0,
            "loss_prob": 1.0,
            "runs_left": runs_left,
            "balls_left": balls_left,
            "wickets_left": wickets_left,
            "crr": crr,
            "rrr": rrr,
            "decided": f"No balls left. {bowling_team} should win."
        }
    if wickets_left <= 0:
        return {
            "input_df": None,
            "win_prob": 0.0,
            "loss_prob": 1.0,
            "runs_left": runs_left,
            "balls_left": balls_left,
            "wickets_left": wickets_left,
            "crr": crr,
            "rrr": rrr,
            "decided": f"All out. {bowling_team} should win."
        }

    input_df = pd.DataFrame(
        {
            "batting_team": [batting_team],
            "bowling_team": [bowling_team],
            "city": [selected_city],
            "Score": [score],
            "Wickets": [wickets_left],      # NOTE: model expects 'wickets left' per your original code
            "Remaining Balls": [balls_left],
            "target_left": [runs_left],
            "crr": [crr],
            "rrr": [rrr],
        }
    )

    try:
        result = model.predict_proba(input_df)
        loss = float(result[0][0])
        win = float(result[0][1])
    except Exception as e:
        st.exception(e)
        st.stop()

    return {
        "input_df": input_df,
        "win_prob": win,
        "loss_prob": loss,
        "runs_left": runs_left,
        "balls_left": balls_left,
        "wickets_left": wickets_left,
        "crr": crr,
        "rrr": rrr,
        "decided": None,
    }

# ---------- Output / Results ----------
if submitted:
    issues = validate_inputs()
    if issues:
        for i in issues:
            st.error(i)
        st.stop()

    res = compute_and_predict()

    # KPIs row
    kpi_cols = st.columns(4)
    with kpi_cols[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-title">Runs required</div><div class="kpi-value">{max(res["runs_left"],0)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with kpi_cols[1]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-title">Balls left</div><div class="kpi-value">{max(res["balls_left"],0)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with kpi_cols[2]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="kpi-title">Wickets in hand</div><div class="kpi-value">{max(res["wickets_left"],0)}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with kpi_cols[3]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        rrr_show = "∞" if res["rrr"] == float("inf") else f'{res["rrr"]:.2f}'
        st.markdown(f'<div class="kpi-title">CRR / RRR</div><div class="kpi-value">{res["crr"]:.2f} <span class="pill">CRR</span> &nbsp; {rrr_show} <span class="pill">RRR</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.write("")

    # Probability bars
    win_pct = round(res["win_prob"] * 100, 1)
    loss_pct = round(res["loss_prob"] * 100, 1)

    left, right = st.columns(2)
    with left:
        st.markdown(f'<div class="prob-label">{batting_team} Win Probability</div>', unsafe_allow_html=True)
        st.markdown(
            f'''
            <div class="prob-bar">
              <div class="prob-fill" style="width:{win_pct}%; background:{SUCCESS};"></div>
            </div>
            <div class="footer-note">{win_pct}%</div>
            ''',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(f'<div class="prob-label">{bowling_team} Win Probability</div>', unsafe_allow_html=True)
        st.markdown(
            f'''
            <div class="prob-bar">
              <div class="prob-fill" style="width:{loss_pct}%; background:{DANGER};"></div>
            </div>
            <div class="footer-note">{loss_pct}%</div>
            ''',
            unsafe_allow_html=True,
        )

    # Verdict / status
    st.write("")
    verdict_box = st.container()
    with verdict_box:
        if res["decided"]:
            st.success(res["decided"])
        else:
            if win_pct >= 65:
                st.success(f"{batting_team} are well on course.")
            elif win_pct <= 35:
                st.error(f"{bowling_team} on top; chase getting tough.")
            else:
                st.info("Tight contest—this could go either way!")

    # Advanced debug (optional)
    with st.expander("See model inputs (debug)"):
        st.dataframe(res["input_df"])

# ---------- Footer ----------
st.markdown(
    """
    <hr/>
    <div class="footer-note">
      Disclaimer: This tool provides probabilistic estimates for educational purposes. Actual outcomes may vary.
    </div>
    """,
    unsafe_allow_html=True,
)
