# pages/Dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px

# UI
from ui_theme import apply_theme
from ui_sidebar import render_sidebar

# Auth
from auth import init_auth_state, login_form

# Modules métier
from energy_utils import style_fig, make_recos
from alerts import render_alerts
from notifications_ui import render_top_notifications

# --- Palette (lisible + contrastée) ---
COLOR_TRUE = "#1f77b4"   # bleu (Vrai)
COLOR_PRED = "#ff7f0e"   # orange (Prédit)
COLOR_ERR  = "#d62728"   # rouge (Résidus)

# -----------------------------
# CONFIG PAGE + THEME
# -----------------------------
st.set_page_config(page_title="Dashboard – EcoEnergy Insight", layout="wide")
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
# GUARD : PRÉDICTION EXISTE ?
# -----------------------------
if not st.session_state.get("pred_ready", False):
    st.title("📊 Dashboard")
    st.warning("Lance d’abord une prédiction depuis la page principale (Home).")
    st.info("👉 Va sur **EcoEnergy Home**, choisis une période, puis clique sur **Lancer la prédiction**.")
    st.stop()

# -----------------------------
# TOP NOTIFICATIONS
# -----------------------------
render_top_notifications()

# -----------------------------
# DATA DE SESSION
# -----------------------------
start = st.session_state["pred_start"]
end = st.session_state["pred_end"]
y_use = st.session_state["y_use"]
y_pred = st.session_state["y_pred"]
metrics = st.session_state["metrics"]
alerts = st.session_state["alerts"]

true_energy_kwh = st.session_state.get("true_energy_kwh")
pred_energy_kwh = st.session_state.get("pred_energy_kwh")
base_rmse = st.session_state.get("base_rmse")
gain_rmse = st.session_state.get("gain_rmse")

# -----------------------------
# HEADER
# -----------------------------
st.title("📊 Dashboard")
st.caption(f"Période analysée : **{start} → {end}**")

# -----------------------------
# ALERTES
# -----------------------------
st.subheader("🚨 Alertes sur la période")
render_alerts(alerts)
st.markdown("---")

# -----------------------------
# KPI
# -----------------------------
st.subheader("📌 Indicateurs clés")

c1, c2, c3, c4 = st.columns(4)
c1.metric("MAE (W)", f"{metrics['MAE']:.1f}")
c2.metric("RMSE (W)", f"{metrics['RMSE']:.1f}")
c3.metric("MAPE (%)", f"{metrics['MAPE%']:.1f}")
if gain_rmse is not None:
    c4.metric("Gain vs Baseline", f"{gain_rmse:.1f}%")
else:
    c4.metric("R²", f"{metrics['R2']:.3f}")

cA, cB = st.columns(2)
cA.metric("Énergie vraie", f"{true_energy_kwh:.2f} kWh")
cB.metric("Énergie prédite", f"{pred_energy_kwh:.2f} kWh")

if base_rmse is not None and gain_rmse is not None:
    st.caption(f"📌 Baseline RMSE : {base_rmse:.1f} W — gain estimé : {gain_rmse:.1f}%")

st.markdown("---")

# -----------------------------
# COURBE VRAI VS PRÉDIT
# -----------------------------
st.subheader("📈 Courbe vrai vs prédit")

df_ts = pd.DataFrame({
    "Time": y_use.index,
    "Vrai": y_use.values,
    "Prédit": y_pred.loc[y_use.index].values
})

fig_ts = px.line(
    df_ts,
    x="Time",
    y=["Vrai", "Prédit"],
    labels={"value": "Puissance (W)", "variable": ""},
    color_discrete_map={"Vrai": COLOR_TRUE, "Prédit": COLOR_PRED},
)
fig_ts = style_fig(fig_ts)
fig_ts.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

# ✅ UN seul affichage + key unique
st.plotly_chart(fig_ts, use_container_width=True, key="dash_ts")

st.markdown("---")

# -----------------------------
# RÉSIDUS
# -----------------------------
st.subheader("📉 Distribution des erreurs (résidus)")

residuals = (y_pred - y_use).dropna()

fig_hist = px.histogram(
    residuals,
    nbins=50,
    labels={"value": "Erreur (W)"},
    title="Histogramme des erreurs (Prédit - Vrai)",
)
fig_hist = style_fig(fig_hist)
fig_hist.update_traces(marker_color=COLOR_ERR)

st.plotly_chart(fig_hist, use_container_width=True, key="dash_resid_hist")

st.write("**Statistiques sur les erreurs :**")
st.write(f"- Erreur moyenne : {residuals.mean():.1f} W")
st.write(f"- Écart-type : {residuals.std():.1f} W")
st.write(f"- Max sur-prédiction : {residuals.max():.1f} W")
st.write(f"- Max sous-prédiction : {residuals.min():.1f} W")

st.markdown("---")

# -----------------------------
# ANALYSE JOURNALIÈRE
# -----------------------------
st.subheader("📊 Analyse journalière (kWh)")

daily_true = (y_use.resample("D").sum() / 1000 / 60).rename("Vrai (kWh)")
daily_pred = (y_pred.resample("D").sum() / 1000 / 60).rename("Prédit (kWh)")

df_daily = pd.concat([daily_true, daily_pred], axis=1).dropna().reset_index()
df_daily = df_daily.rename(columns={df_daily.columns[0]: "Date"})  # robuste

if df_daily.empty:
    st.info("Période trop courte pour une analyse journalière.")
else:
    fig_bar = px.bar(
        df_daily,
        x="Date",
        y=["Vrai (kWh)", "Prédit (kWh)"],
        barmode="group",
        labels={"value": "kWh / jour", "variable": ""},
        color_discrete_map={"Vrai (kWh)": COLOR_TRUE, "Prédit (kWh)": COLOR_PRED},
    )
    fig_bar = style_fig(fig_bar)
    fig_bar.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

    st.plotly_chart(fig_bar, use_container_width=True, key="dash_daily_bar")

st.markdown("---")

# -----------------------------
# RECOMMANDATIONS
# -----------------------------
st.subheader("💡 Recommandations rapides")

recos = make_recos(daily_true, daily_pred)
if recos:
    for r in recos:
        st.markdown(f"- {r}")
else:
    st.info("Aucune recommandation générée sur cette période.")

if st.button("📚 Voir l’historique des prédictions"):
    st.switch_page("pages/Historique.py")

