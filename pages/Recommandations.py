# pages/Recommandations.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import requests

from ui_theme import apply_theme
from ui_sidebar import render_sidebar

from auth import init_auth_state, login_form
from energy_utils import make_recos, style_fig
from notifications_ui import render_top_notifications


# =============================
# Palette couleurs (cohérente Dashboard)
# =============================
COLOR_TRUE = "#1f77b4"   # Vrai
COLOR_PRED = "#ff7f0e"   # Prédit


# =============================
# Config + Theme
# =============================
st.set_page_config(page_title="Recommandations – EcoEnergy Insight", layout="wide")
apply_theme()


# =============================
# Auth
# =============================
init_auth_state()
if not st.session_state.auth["is_auth"]:
    login_form()
    st.stop()

current_user = st.session_state.auth["user"]
render_sidebar(user=current_user, show_date_selector=False, show_run_button=False)


# =============================
# Guard prediction
# =============================
if not st.session_state.get("pred_ready", False):
    st.title("💡 Recommandations")
    st.warning("Lance d’abord une prédiction depuis la page Home.")
    st.stop()

render_top_notifications()


# =============================
# Data session
# =============================
start = pd.to_datetime(st.session_state["pred_start"])
end = pd.to_datetime(st.session_state["pred_end"])
y_use = st.session_state["y_use"]
y_pred = st.session_state["y_pred"]

st.title("💡 Recommandations")
st.caption(f"Période analysée : **{start} → {end}**")


# =============================
# Helpers
# =============================
def kwh_day(series_w_min: pd.Series) -> pd.Series:
    """W/min -> kWh/jour"""
    return (series_w_min.resample("D").sum() / (1000 * 60)).dropna()

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def robust_reset_index(df: pd.DataFrame, name="Date") -> pd.DataFrame:
    """Reset index et renomme la 1ère colonne en 'Date' quelle que soit son nom."""
    out = df.copy().reset_index()
    first = out.columns[0]
    out = out.rename(columns={first: name})
    out[name] = pd.to_datetime(out[name])
    return out

def _fmt_date(d: pd.Timestamp) -> str:
    return pd.to_datetime(d).strftime("%d/%m")

def _fmt_money(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ").replace(".", ",")


# =============================
# Daily series (kWh/j)
# =============================
daily_true = kwh_day(y_use.rename("W_true")).rename("Vrai (kWh)")
daily_pred = kwh_day(y_pred.rename("W_pred")).rename("Prédit (kWh)")
df_daily = pd.concat([daily_true, daily_pred], axis=1).dropna()

if df_daily.empty or len(df_daily) < 2:
    st.info("Période trop courte pour produire des recommandations fiables (au moins 2 jours conseillés).")
    st.stop()

# KPIs (orientés action)
total_kwh = safe_float(df_daily["Vrai (kWh)"].sum())
mean_kwh = safe_float(df_daily["Vrai (kWh)"].mean())
max_kwh = safe_float(df_daily["Vrai (kWh)"].max())
gap_kwh = safe_float((df_daily["Prédit (kWh)"] - df_daily["Vrai (kWh)"]).abs().mean())

top_days = df_daily["Vrai (kWh)"].sort_values(ascending=False).head(3)
top_days_str = ", ".join([_fmt_date(d) for d in top_days.index])


# =============================
# Résumé rapide (sans dupliquer Dashboard)
# =============================
st.subheader("📌 Résumé rapide (orienté actions)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Énergie totale", f"{total_kwh:.1f} kWh")
c2.metric("Moyenne / jour", f"{mean_kwh:.1f} kWh")
c3.metric("Jour le + élevé", f"{max_kwh:.1f} kWh")
c4.metric("Écart moyen (|prédit-vrai|)", f"{gap_kwh:.2f} kWh/j")

st.caption(f"🔎 **Jours à investiguer** (les plus énergivores) : **{top_days_str}**")


# =============================
# Graph conso journalière (compact) — ✅ corrigé (1 seul plot) + key unique
# =============================
st.markdown("---")
st.subheader("📈 Conso journalière (comparaison simple)")

df_plot = robust_reset_index(df_daily, name="Date")
fig = px.bar(
    df_plot,
    x="Date",
    y=["Vrai (kWh)", "Prédit (kWh)"],
    barmode="group",
    labels={"value": "kWh / jour", "variable": ""},
    color_discrete_map={"Vrai (kWh)": COLOR_TRUE, "Prédit (kWh)": COLOR_PRED},
)

# Sécurité couleurs
fig.for_each_trace(lambda t: t.update(marker_color=COLOR_TRUE) if t.name == "Vrai (kWh)" else None)
fig.for_each_trace(lambda t: t.update(marker_color=COLOR_PRED) if t.name == "Prédit (kWh)" else None)

fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
fig = style_fig(fig)
st.plotly_chart(fig, use_container_width=True, key="rec_daily_bar")


# =============================
# MÉTÉO (Open-Meteo) + fallback manuel
# =============================
st.markdown("---")
st.subheader("🌦️ Contexte météo (pour expliquer certains jours)")

@st.cache_data(ttl=3600)
def fetch_open_meteo_daily(lat: float, lon: float, start_date: str, end_date: str) -> pd.DataFrame:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "timezone": "auto",
        "start_date": start_date,
        "end_date": end_date,
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()
    d = data.get("daily", {}) or {}
    if not d:
        return pd.DataFrame()

    dfw = pd.DataFrame({
        "Date": pd.to_datetime(d.get("time", [])),
        "Tmax": d.get("temperature_2m_max", []),
        "Tmin": d.get("temperature_2m_min", []),
        "Pluie(mm)": d.get("precipitation_sum", []),
    })
    if dfw.empty:
        return dfw
    dfw["Tmean"] = (dfw["Tmax"] + dfw["Tmin"]) / 2
    return dfw

colA, colB, colC = st.columns([1.2, 1.2, 2.2])
with colA:
    meteo_mode = st.radio("Source météo", ["Auto (Open-Meteo)", "Manuel"], horizontal=False, key="rec_meteo_mode")
with colB:
    st.caption("📍 Coordonnées (mode Auto)")
    lat = st.number_input("Latitude", value=36.8065, format="%.6f", key="rec_lat")  # Tunis
    lon = st.number_input("Longitude", value=10.1815, format="%.6f", key="rec_lon")
with colC:
    st.caption("💡 Si Internet bloque / API down → passe en Manuel.")

weather_df = pd.DataFrame()
if meteo_mode.startswith("Auto"):
    try:
        weather_df = fetch_open_meteo_daily(lat, lon, start.date().isoformat(), end.date().isoformat())
        if weather_df.empty:
            st.warning("Météo indisponible (réponse vide). Passe en Manuel.")
    except Exception:
        st.warning("Impossible de récupérer la météo (connexion/API). Passe en Manuel.")
        weather_df = pd.DataFrame()

if meteo_mode == "Manuel" or weather_df.empty:
    tmean_manual = st.slider("Température moyenne estimée (°C)", -5, 45, 18, key="rec_tmean_manual")
    rain_manual = st.slider("Pluie totale estimée sur la période (mm)", 0, 250, 0, key="rec_rain_manual")
    weather_df = pd.DataFrame({
        "Date": pd.to_datetime(df_daily.index),
        "Tmean": [tmean_manual] * len(df_daily),
        "Pluie(mm)": [rain_manual / max(1, len(df_daily))] * len(df_daily),
    })

# Merge conso + météo
df_rec = robust_reset_index(df_daily, name="Date")
weather_df = weather_df.copy()
weather_df["Date"] = pd.to_datetime(weather_df["Date"])
df_rec = df_rec.merge(weather_df[["Date", "Tmean", "Pluie(mm)"]], on="Date", how="left")

tmean_avg = safe_float(np.nanmean(df_rec["Tmean"].values), default=np.nan)
rain_sum = safe_float(np.nansum(df_rec["Pluie(mm)"].values), default=np.nan)

wx1, wx2, wx3 = st.columns(3)
wx1.metric("Temp. moyenne (période)", "N/A" if np.isnan(tmean_avg) else f"{tmean_avg:.1f} °C")
wx2.metric("Pluie totale approx.", "N/A" if np.isnan(rain_sum) else f"{rain_sum:.1f} mm")

try:
    corr = np.corrcoef(df_rec["Tmean"].fillna(tmean_avg), df_rec["Vrai (kWh)"])[0, 1]
    wx3.metric("Corrélation (Temp ↔ kWh)", f"{corr:.2f}")
except Exception:
    wx3.metric("Corrélation (Temp ↔ kWh)", "N/A")

with st.expander("📌 Lecture rapide (à quoi ça sert ?)"):
    st.markdown(
        """
- Température basse → souvent + de conso (chauffage / eau chaude).
- Température haute → conso possible de clim/ventilation.
- La corrélation est **indicative** : utile pour justifier des jours “anormaux”.
"""
    )

fig_sc = px.scatter(
    df_rec,
    x="Tmean",
    y="Vrai (kWh)",
    hover_data=["Date", "Pluie(mm)"],
    labels={"Tmean": "Température moyenne (°C)", "Vrai (kWh)": "kWh/jour"},
    title="Conso (kWh/j) vs Température (indication)",
)
fig_sc.update_traces(marker=dict(color=COLOR_TRUE))
fig_sc = style_fig(fig_sc)
st.plotly_chart(fig_sc, use_container_width=True, key="rec_weather_scatter")


# =============================
# TARIFS + ESTIMATION COÛT
# =============================
st.markdown("---")
st.subheader("💶 Tarifs & estimation de coût (pour décider quoi prioriser)")

tcol1, tcol2, tcol3, tcol4 = st.columns([1.2, 1, 1, 1])
with tcol1:
    tariff = st.selectbox("Type de tarif", ["Fixe", "HP/HC (Heures Pleines / Creuses)"], key="rec_tariff")
with tcol2:
    price_kwh = st.number_input("Prix kWh (DT)", min_value=0.0, value=0.30, step=0.01, key="rec_price_kwh")
with tcol3:
    target_save_pct = st.slider("Objectif économie (%)", 0, 25, 8, key="rec_target_save")
with tcol4:
    show_cost = st.toggle("Afficher estimations de coût", value=True, key="rec_show_cost")

hc_start, hc_end = "00:00", "06:00"
hp_price = float(price_kwh)
hc_price = float(price_kwh) * 0.7

if tariff.startswith("HP/HC"):
    h1, h2, h3 = st.columns(3)
    with h1:
        hc_start = st.selectbox("Début HC", ["21:00", "22:00", "23:00", "00:00", "01:00"], index=3, key="rec_hc_start")
    with h2:
        hc_end = st.selectbox("Fin HC", ["05:00", "06:00", "07:00", "08:00"], index=1, key="rec_hc_end")
    with h3:
        hc_price = st.number_input("Prix HC (DT/kWh)", min_value=0.0, value=float(hc_price), step=0.01, key="rec_hc_price")
    hp_price = st.number_input("Prix HP (DT/kWh)", min_value=0.0, value=float(price_kwh), step=0.01, key="rec_hp_price")

cost_fixed = total_kwh * float(price_kwh)

cost_hphc = None
if tariff.startswith("HP/HC"):
    s = y_use.dropna().copy()
    s = s.loc[(s.index >= start) & (s.index <= end)]
    if len(s):
        kwh_min = s / (1000 * 60)
        try:
            hc_start_h = int(hc_start.split(":")[0])
            hc_end_h = int(hc_end.split(":")[0])
            hours = kwh_min.index.hour

            if hc_start_h < hc_end_h:
                is_hc = (hours >= hc_start_h) & (hours < hc_end_h)
            else:
                is_hc = (hours >= hc_start_h) | (hours < hc_end_h)

            kwh_hc = float(kwh_min[is_hc].sum())
            kwh_hp = float(kwh_min[~is_hc].sum())
            cost_hphc = kwh_hc * float(hc_price) + kwh_hp * float(hp_price)
        except Exception:
            cost_hphc = None

if show_cost:
    cost_used = cost_hphc if cost_hphc is not None else cost_fixed
    cA, cB, cC = st.columns(3)
    cA.metric("Coût estimé (tarif choisi)", _fmt_money(cost_used) + " DT")
    cB.metric("Économie cible", f"{target_save_pct}%  (~{_fmt_money(cost_used*target_save_pct/100)} DT)")
    cC.metric("Conso cible", f"{(total_kwh*(1-target_save_pct/100)):.1f} kWh")


# =============================
# RECOMMANDATIONS ENRICHIES (sans dupliquer autres pages)
# =============================
st.markdown("---")
st.subheader("✅ Recommandations (concrètes, contextualisées)")

base_recos = make_recos(daily_true, daily_pred) or []
base_recos = [r for r in base_recos if isinstance(r, str) and r.strip()]

premium = []

premium.append(
    f"🔎 **Investiguer {top_days_str}** : note les usages (four, lave-linge, chauffe-eau, invités). "
    "Objectif : identifier 1 cause répétable → action simple."
)

if not np.isnan(tmean_avg):
    if tmean_avg <= 10:
        premium.append(
            "🌡️ Température plutôt basse : la conso peut venir du **chauffage / eau chaude**. "
            "Actions : réduire 1°C, programmer chauffe-eau, vérifier fuites d’eau chaude."
        )
    elif tmean_avg >= 28:
        premium.append(
            "🌡️ Température élevée : attention à **clim/ventilation**. "
            "Actions : mode éco, filtres propres, fermer fenêtres aux heures chaudes, consigne +1°C."
        )
    else:
        premium.append(
            "🌡️ Température modérée : variations plutôt liées aux **habitudes d’usage**. "
            "Action : étaler les gros appareils + réduire les veilles."
        )

if not np.isnan(rain_sum) and rain_sum >= 20:
    premium.append(
        "🌧️ Pluie notable : plus d’activités à la maison possible. "
        "Action : planifier les machines en dehors des plages chargées."
    )

if tariff.startswith("HP/HC"):
    premium.append(
        f"⏱️ Tarif HP/HC : décale **lave-linge / lave-vaisselle / chauffe-eau** vers **{hc_start} → {hc_end}** quand c’est possible."
    )
else:
    premium.append("💶 Tarif fixe : priorité à **réduire la base (veilles)** + **éviter les pics** (cumul d’appareils).")

premium.append(
    f"🎯 Objectif réaliste : **-{target_save_pct}%** sur la prochaine période → choisis 2 actions simples (veilles + décalage 1 appareil)."
)

if gap_kwh >= 0.8:
    premium.append(
        "🧪 Écart prédiction/réel visible : utilise ces recommandations comme **guides de tendance**, puis valide sur 2–3 jours."
    )

final_recos = premium + base_recos[:6]
for r in final_recos:
    st.markdown(f"- {r}")


# =============================
# PLAN D’ACTION (sans répéter Assistant IA)
# =============================
st.markdown("---")
st.subheader("🗓️ Plan d’action (7 jours) — simple & mesurable")

colp1, colp2 = st.columns(2)
with colp1:
    st.markdown(
        """
**Priorité 1 : Baisser la consommation “inutile”**
- Jour 1 : repérer veilles (TV/console/chargeurs) → multiprise OFF la nuit  
- Jour 2 : test “nuit propre” (0–6h) → noter différence  
- Jour 3 : corriger 1 source permanente (box, veille, chargeur, chauffe-eau)
"""
    )
with colp2:
    st.markdown(
        f"""
**Priorité 2 : Déplacer 1 gros usage**
- Jour 4 : choisir 1 appareil à décaler (machine / four / chauffe-eau)  
- Jour 5 : faire 1 journée sans cumul (pas 2 gros appareils en parallèle)  
- Jour 6 : refaire et comparer kWh/jour  
- Jour 7 : relancer une analyse → viser **-{target_save_pct}%**
"""
    )

st.caption("💡 Page centrée sur **l’action et le contexte** (météo/tarifs).")
