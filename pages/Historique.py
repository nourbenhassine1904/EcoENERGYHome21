# pages/Historique.py
import json
from io import BytesIO

import streamlit as st
import pandas as pd

from ui_theme import apply_theme
from ui_sidebar import render_sidebar
from auth import init_auth_state, login_form
from notifications_ui import render_top_notifications

from database.crud import (
    list_predictions,
    list_predictions_for_user,   # ✅ IMPORTANT (à ajouter dans crud.py)
    get_alerts_for_prediction,
    get_recommendations_for_prediction,
    get_prediction,
)

# =============================
# Config + Theme
# =============================
st.set_page_config(page_title="Historique – EcoEnergy Insight", layout="wide")
apply_theme()

# =============================
# Auth
# =============================
init_auth_state()
if not st.session_state.auth["is_auth"]:
    login_form()
    st.stop()

current_user = st.session_state.auth["user"] or {}
render_sidebar(user=current_user, show_date_selector=False, show_run_button=False)
render_top_notifications()

role = (current_user.get("role") or "").lower()
user_id = current_user.get("id", None)

# =============================
# Page
# =============================
st.title("🗂️ Historique des analyses")
st.caption(
    "Historique des prédictions enregistrées (SQLite + SQLAlchemy) : traçabilité, alertes, recommandations, export."
)

# =============================
# Charger l’historique selon rôle
# =============================
if role == "admin":
    preds = list_predictions(limit=200)
    st.info("👑 Mode admin : vous voyez toutes les prédictions.")
else:
    if user_id is None:
        st.error("❌ Impossible de détecter votre ID utilisateur. Vérifiez auth.py (st.session_state.auth['user']['id']).")
        st.stop()
    preds = list_predictions_for_user(user_id=int(user_id), limit=200)
    st.info("👤 Mode utilisateur : vous voyez uniquement vos prédictions.")

if not preds:
    st.warning("Aucune prédiction visible pour l’instant. Lance une prédiction depuis Home.")
    st.stop()

# =============================
# Export EXCEL (historique visible)
# =============================
st.markdown("### ⬇️ Export")

rows = []
for p in preds:
    rows.append({
        "id": p.id,
        "created_at": p.created_at.isoformat(sep=" ", timespec="seconds") if p.created_at else None,
        "start_date": p.start_date.isoformat(sep=" ", timespec="seconds") if p.start_date else None,
        "end_date": p.end_date.isoformat(sep=" ", timespec="seconds") if p.end_date else None,
        "horizon": p.horizon,
        "total_kwh": p.total_kwh,
        "mae": p.mae,
        "rmse": p.rmse,
        "mape": p.mape,
        "r2": p.r2,
        "user_id": getattr(p, "user_id", None),
    })

df_export = pd.DataFrame(rows)

def dataframe_to_excel_bytes(df: pd.DataFrame, sheet_name: str = "predictions") -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buffer.getvalue()

c_exp1, c_exp2 = st.columns([1.5, 2.5])
with c_exp1:
    try:
        xlsx_data = dataframe_to_excel_bytes(df_export, sheet_name="predictions")
        st.download_button(
            "⬇️ Télécharger l’historique (Excel)",
            data=xlsx_data,
            file_name="ecoenergy_predictions_history.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except Exception as e:
        st.warning(
            "⚠️ Export Excel impossible. Installe openpyxl : `pip install openpyxl`\n\n"
            f"Détail : {e}"
        )

with c_exp2:
    st.caption("Excel = période + métriques + énergie (selon vos permissions).")

st.markdown("---")

# =============================
# Sélection d’une prédiction
# =============================
st.subheader("📌 Sélectionner une analyse")

options = []
pred_map = {}

for p in preds:
    created = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "?"
    start = p.start_date.strftime("%Y-%m-%d") if p.start_date else "?"
    end = p.end_date.strftime("%Y-%m-%d") if p.end_date else "?"
    kwh = float(p.total_kwh) if p.total_kwh is not None else 0.0
    uid = getattr(p, "user_id", None)
    uid_str = f" | user_id={uid}" if role == "admin" else ""
    label = f"#{p.id} | {created} | {start} → {end} | {kwh:.1f} kWh{uid_str}"
    options.append(label)
    pred_map[label] = p.id

# sélectionner par défaut last_prediction_id si possible
default_index = 0
last_id = st.session_state.get("last_prediction_id", None)
if last_id is not None:
    for i, lab in enumerate(options):
        if lab.startswith(f"#{last_id} "):
            default_index = i
            break

selected = st.selectbox("Choisir une prédiction :", options, index=default_index)
pred_id = pred_map[selected]

# =============================
# Charger détails (alerts/recos)
# =============================
p = get_prediction(pred_id)
alerts = get_alerts_for_prediction(pred_id)
recos = get_recommendations_for_prediction(pred_id)

# =============================
# ✅ Résumé soutenance (PRO)
# =============================
st.markdown("## 🧾 Résumé ")

if p is None:
    st.warning("Impossible de charger cette prédiction.")
else:
    period_str = f"{p.start_date:%Y-%m-%d} → {p.end_date:%Y-%m-%d}" if p.start_date and p.end_date else "?"
    total_kwh = float(p.total_kwh) if p.total_kwh is not None else 0.0
    rmse = float(p.rmse) if p.rmse is not None else None
    mae = float(p.mae) if p.mae is not None else None

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("ID analyse", pred_id)
    s2.metric("Période", period_str)
    s3.metric("Énergie totale", f"{total_kwh:.2f} kWh")
    s4.metric("RMSE / MAE", f"{rmse:.1f} / {mae:.1f}" if (rmse is not None and mae is not None) else "N/A")
    s5.metric("Alertes / Recos", f"{len(alerts)} / {len(recos)}")

    with st.expander("💬 Description "):
        st.write(
            "Pour cette période, nous avons persisté une prédiction en base SQLite (SQLAlchemy) "
            "avec les métriques (RMSE/MAE), l’énergie totale (kWh), ainsi que les alertes et recommandations associées. "
            "Cela assure la traçabilité, l’historique des analyses et la reproductibilité du projet."
        )

st.markdown("---")

# =============================
# KPIs (globaux)
# =============================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Prédictions visibles", len(preds))
c2.metric("Alertes", len(alerts))
c3.metric("Recommandations", len(recos))
c4.metric("ID sélectionné", pred_id)

# =============================
# Export JSON (rapport complet)
# =============================
def build_prediction_details_json(prediction, alerts_list, recos_list) -> dict:
    if prediction is None:
        return {}
    return {
        "prediction": {
            "id": prediction.id,
            "created_at": prediction.created_at.isoformat() if prediction.created_at else None,
            "start_date": prediction.start_date.isoformat() if prediction.start_date else None,
            "end_date": prediction.end_date.isoformat() if prediction.end_date else None,
            "horizon": prediction.horizon,
            "total_kwh": prediction.total_kwh,
            "mae": prediction.mae,
            "rmse": prediction.rmse,
            "mape": prediction.mape,
            "r2": prediction.r2,
            "user_id": getattr(prediction, "user_id", None),
        },
        "alerts": [
            {
                "id": a.id,
                "level": a.level,
                "title": a.title,
                "message": a.message,
                "metric": getattr(a, "metric", None),
                "value": getattr(a, "value", None),
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts_list
        ],
        "recommendations": [
            {
                "id": r.id,
                "content": r.content,
                "category": r.category,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recos_list
        ],
    }

details = build_prediction_details_json(p, alerts, recos)

st.download_button(
    "⬇️ Télécharger ce rapport (JSON)",
    data=json.dumps(details, ensure_ascii=False, indent=2).encode("utf-8"),
    file_name=f"ecoenergy_prediction_{pred_id}.json",
    mime="application/json",
    use_container_width=True,
)

st.markdown("---")

# =============================
# Affichage Alertes
# =============================
st.subheader("🚨 Alertes enregistrées")
if alerts:
    for a in alerts:
        level = (a.level or "").lower()
        line = f"**[{(a.level or '').upper()}] {a.title}** — {a.message}"
        if level == "critical":
            st.error(line)
        elif level == "warning":
            st.warning(line)
        else:
            st.info(line)
else:
    st.info("Aucune alerte pour cette prédiction.")

st.markdown("---")

# =============================
# Affichage Recos
# =============================
st.subheader("💡 Recommandations enregistrées")
if recos:
    recos_sorted = sorted(recos, key=lambda r: (r.category or "zzz", r.id))
    for r in recos_sorted:
        tag = f"**[{r.category}]** " if r.category else ""
        st.markdown(f"- {tag}{r.content}")
else:
    st.info("Aucune recommandation pour cette prédiction.")
