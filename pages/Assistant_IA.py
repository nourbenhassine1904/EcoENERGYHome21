import streamlit as st

from ui_theme import apply_theme
from ui_sidebar import render_sidebar

from auth import init_auth_state, login_form
from assistant import render_assistant
from notifications_ui import render_top_notifications


st.set_page_config(page_title="Assistant IA – EcoEnergy Insight", layout="wide")
apply_theme()

# -----------------------------
# AUTH
# -----------------------------
init_auth_state()
if not st.session_state.auth["is_auth"]:
    login_form()
    st.stop()

current_user = st.session_state.auth["user"]

# -----------------------------
# SIDEBAR
# -----------------------------
render_sidebar(user=current_user, show_date_selector=False, show_run_button=False)

# -----------------------------
# GUARD : prédiction existante ?
# -----------------------------
if not st.session_state.get("pred_ready", False):
    st.title("🧠 Assistant IA")
    st.warning("Lance d’abord une prédiction depuis la page Home.")
    st.stop()

# -----------------------------
# GUARD : df_full dispo ?
# -----------------------------
df_full = st.session_state.get("df_full")
if df_full is None:
    st.title("🧠 Assistant IA")
    st.error(
        "❌ Les données complètes (df_full) ne sont pas disponibles dans la session.\n\n"
        "✅ Solution : retourne à **EcoEnergy Home** et relance une prédiction (cela recharge df_full)."
    )
    st.stop()

render_top_notifications()

# -----------------------------
# DATA
# -----------------------------
start = st.session_state["pred_start"]
end = st.session_state["pred_end"]
y_use = st.session_state["y_use"]
y_pred = st.session_state["y_pred"]
metrics = st.session_state["metrics"]
H = st.session_state.get("H", 10)

# -----------------------------
# UI
# -----------------------------
st.title("🧠 Assistant IA")
st.caption(f"Période analysée : **{start} → {end}**")

render_assistant(
    df_full=df_full,
    start=start,
    end=end,
    y_use=y_use,
    y_pred=y_pred,
    metrics=metrics,
    H=H,
)
