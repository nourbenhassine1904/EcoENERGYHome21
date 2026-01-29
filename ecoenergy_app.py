# ecoenergy_app.py
import streamlit as st
import pandas as pd

# Auth + UI
from auth import init_auth_state, login_form
from ui_theme import apply_theme
from ui_sidebar import render_sidebar
from notifications_ui import render_top_notifications

# ML utils
from energy_utils import (
    load_model_and_data,
    evaluate,
    build_features,
    load_model_comparison,
    make_recos,
)

# Alerts
from alerts import compute_alerts

# ✅ DB (SQLite + SQLAlchemy)
from database.db import engine
from database.models import Base
from database.crud import save_prediction, save_alert, save_recommendation


# -----------------------------
# CONFIG PAGE
# -----------------------------
st.set_page_config(
    page_title="EcoEnergy Insight – House 21",
    layout="wide",
)
apply_theme()

# -----------------------------
# INIT DB (crée les tables si besoin)
# -----------------------------
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    st.error(f"❌ Problème création DB / tables : {e}")
    st.stop()

# -----------------------------
# AUTH
# -----------------------------
init_auth_state()

if not st.session_state.auth["is_auth"]:
    st.title("⚡ EcoEnergy Insight – House 21")
    st.caption(
        "Tableau de bord interactif pour l’analyse et la prévision de la consommation électrique (House 21 – REFIT)"
    )
    login_form()
    st.stop()

current_user = st.session_state.auth["user"] or {}

# ✅ Sécurité : vérifier que l'utilisateur a bien un id
if "id" not in current_user or current_user["id"] is None:
    st.error("❌ Erreur auth: utilisateur sans ID. Reconnecte-toi.")
    st.stop()

current_user_id = int(current_user["id"])

# -----------------------------
# HEADER + NOTIFS
# -----------------------------
st.title("⚡ EcoEnergy Insight – House 21")
st.caption(
    "Tableau de bord interactif pour l’analyse et la prévision de la consommation électrique (House 21 – REFIT)"
)
render_top_notifications()

# -----------------------------
# CHARGEMENT MODÈLE + DONNÉES
# -----------------------------
try:
    model, meta, H, feat_cols, df = load_model_and_data()
except FileNotFoundError as e:
    st.error(f"❌ {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ Erreur lors du chargement du modèle/données : {e}")
    st.stop()

# ✅ Partage multi-pages
st.session_state["df_full"] = df
st.session_state["H"] = H
st.session_state["feat_cols"] = feat_cols
st.session_state["meta"] = meta

# -----------------------------
# SIDEBAR
# -----------------------------
start_date, end_date, run_clicked = render_sidebar(
    user=current_user,
    df=df,
    show_date_selector=True,
    show_run_button=True,
)

# -----------------------------
# HOME
# -----------------------------
st.subheader("🎯 Lancer une analyse")
st.info(
    "👈 Choisis une période dans la barre latérale puis clique sur **Lancer la prédiction**.\n"
    "Ensuite, utilise le menu **Pages** à gauche pour naviguer (Dashboard, Alertes, Recommandations, Assistant IA...)."
)

if st.session_state.get("pred_ready", False):
    st.success("✅ Une prédiction est déjà disponible. Tu peux aller directement sur **Dashboard**.")
    st.caption(
        f"Période en mémoire : {st.session_state['pred_start']} → {st.session_state['pred_end']}"
    )

# -----------------------------
# RUN : CALCUL + SESSION + DB
# -----------------------------
if run_clicked:
    with st.spinner("⏳ Calcul de la prédiction + alertes + enregistrement DB..."):
        # 1) période sélectionnée
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(minutes=1)

        # 2) contexte (pour features)
        context_start = start - pd.Timedelta(minutes=90)
        part = df.loc[context_start:end].copy()

        # 3) features + target
        X_all, y_all = build_features(part, horizon_min=H, feat_list=feat_cols)

        # 4) masque période réelle
        mask = (X_all.index >= start) & (X_all.index <= end)
        X_use = X_all.loc[mask]
        y_use = y_all.loc[mask]

        if len(X_use) == 0:
            st.error("❌ Aucune donnée sur cette période (ou période trop courte). Essaie une autre plage.")
            st.stop()

        # 5) prédiction
        y_pred = pd.Series(model.predict(X_use), index=X_use.index)

        # 6) métriques
        metrics = evaluate(y_use, y_pred)

        # 7) baseline compare
        compare_df = load_model_comparison()
        base_rmse = None
        gain_rmse = None
        if compare_df is not None and "Baseline" in compare_df.index:
            base_rmse = compare_df.loc["Baseline", "RMSE"]
            if base_rmse and base_rmse != 0:
                gain_rmse = 100 * (base_rmse - metrics["RMSE"]) / base_rmse

        # 8) énergie (W-min -> kWh)
        true_energy_kwh = float(y_use.sum() / 1000 / 60)
        pred_energy_kwh = float(y_pred.sum() / 1000 / 60)

        # 9) alertes
        df_period = df.loc[start:end].copy()
        alerts = compute_alerts(
            df_period=df_period,
            y_true=y_use,
            y_pred=y_pred,
            metrics=metrics,
        )

        # 10) recommandations (journalières)
        daily_true = (y_use.resample("D").sum() / 1000 / 60)
        daily_pred = (y_pred.resample("D").sum() / 1000 / 60)
        recos = make_recos(daily_true, daily_pred) or []

        # -----------------------------
        # ✅ SAUVEGARDE DB (avec user_id)
        # -----------------------------
        pred_db = None
        try:
            pred_db = save_prediction({
                "start_date": start,
                "end_date": end,
                "horizon": int(H),
                "total_kwh": float(true_energy_kwh),
                "mae": float(metrics["MAE"]),
                "rmse": float(metrics["RMSE"]),
                "mape": float(metrics["MAPE%"]),
                "r2": float(metrics["R2"]),
                "user_id": current_user_id,  # ✅ IMPORTANT : lien avec l'utilisateur connecté
            })

            # alertes -> DB
            for a in alerts:
                save_alert(
                    prediction_id=pred_db.id,
                    level=str(a.level),
                    title=str(a.title),
                    message=str(a.message),
                )

            # recos -> DB
            for r in recos:
                save_recommendation(
                    prediction_id=pred_db.id,
                    content=str(r),
                    category="general",
                )

        except Exception as e:
            st.warning(
                "⚠️ La prédiction a été calculée, mais l’enregistrement en base a échoué.\n"
                f"Détail : {e}"
            )

        # -----------------------------
        # ✅ STOCKAGE SESSION (multi-pages)
        # -----------------------------
        st.session_state["pred_ready"] = True
        st.session_state["pred_start"] = start
        st.session_state["pred_end"] = end
        st.session_state["y_use"] = y_use
        st.session_state["y_pred"] = y_pred
        st.session_state["metrics"] = metrics
        st.session_state["alerts"] = alerts
        st.session_state["true_energy_kwh"] = true_energy_kwh
        st.session_state["pred_energy_kwh"] = pred_energy_kwh
        st.session_state["base_rmse"] = base_rmse
        st.session_state["gain_rmse"] = gain_rmse
        st.session_state["last_prediction_id"] = getattr(pred_db, "id", None)

    st.success("✅ Prédiction calculée (et enregistrée si DB OK). Redirection vers **Dashboard**...")
    try:
        st.switch_page("pages/Dashboard.py")
    except Exception:
        st.info("➡️ Ouvre la page **Dashboard** via le menu Pages à gauche.")
