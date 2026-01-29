import streamlit as st

from ui_theme import apply_theme
from ui_sidebar import render_sidebar

from auth import init_auth_state, login_form
from alerts import render_alerts
from notifications_ui import render_top_notifications


st.set_page_config(page_title="Alertes – EcoEnergy Insight", layout="wide")
apply_theme()

# AUTH
init_auth_state()
if not st.session_state.auth["is_auth"]:
    login_form()
    st.stop()

current_user = st.session_state.auth["user"]

# SIDEBAR (sans dates)
render_sidebar(user=current_user, show_date_selector=False, show_run_button=False)

# GUARD pred
if not st.session_state.get("pred_ready", False):
    st.title("⚠️ Alertes")
    st.warning("Lance d’abord une prédiction depuis la page Home.")
    st.stop()

render_top_notifications()

# DATA
start = st.session_state["pred_start"]
end = st.session_state["pred_end"]
alerts = st.session_state.get("alerts", {})

st.title("⚠️ Alertes")
st.caption(f"Période analysée : **{start} → {end}**")

render_alerts(alerts)

st.markdown("---")
st.info("Astuce : relance une nouvelle période depuis **EcoEnergy Home** pour mettre à jour les alertes.")

if st.button("📚 Voir l’historique des prédictions"):
    st.switch_page("pages/Historique.py")
