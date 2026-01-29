# pages/About.py
import streamlit as st
import pandas as pd

from ui_theme import apply_theme
from ui_sidebar import render_sidebar
from auth import init_auth_state, login_form
from notifications_ui import render_top_notifications

# DB (pour afficher l'état de la base + stats simples)
from database.db import DB_PATH, engine
from database.models import Base
from database.crud import list_predictions

# -----------------------------
# Config + Theme
# -----------------------------
st.set_page_config(page_title="À propos / Documentation – EcoEnergy Insight", layout="wide")
apply_theme()

# -----------------------------
# Auth (comme toutes les pages)
# -----------------------------
init_auth_state()
if not st.session_state.auth["is_auth"]:
    login_form()
    st.stop()

current_user = st.session_state.auth["user"]
render_sidebar(user=current_user, show_date_selector=False, show_run_button=False)
render_top_notifications()

# -----------------------------
# Page
# -----------------------------
st.title("ℹ️ À propos / Documentation")
st.caption("Documentation intégrée : projet, fonctionnement, base de données, limites et préparation soutenance.")

# -----------------------------
# 1) Résumé du projet
# -----------------------------
st.markdown("## 🎯 EcoEnergy Insight — Résumé")
st.markdown(
    """
**EcoEnergy Insight** est une application d’analyse et de prévision de la consommation électrique (House 21 – REFIT).
Elle combine :
- **Data Science** (préparation + statistiques)
- **Machine Learning** (prédiction minute par minute)
- **Visualisation** (graphiques lisibles)
- **Aide à la décision** (alertes + recommandations contextualisées)
- **Traçabilité** via **SQLite + SQLAlchemy** (historique exportable)
"""
)

# -----------------------------
# 2) Ce que l'app sait faire
# -----------------------------
st.markdown("## ✅ Fonctionnalités principales")
st.markdown(
    """
- **Prédire la consommation** minute par minute sur une période choisie.
- **Afficher un dashboard** : indicateurs + courbes + analyse journalière.
- **Générer des alertes** (pics, base load, soirée énergivore, biais…).
- **Générer des recommandations** (actions concrètes + météo + tarifs si activés).
- **Enregistrer en base** : prédictions + alertes + recommandations.
- **Consulter l’historique** et **exporter** (Excel + JSON).
"""
)

# -----------------------------
# 3) Pages (sans duplication)
# -----------------------------
st.markdown("## 🧭 Pages de l’application (rôles)")
st.markdown(
    """
- **Home (ecoenergy_app.py)** : lancement d’une analyse (période → prédiction → sauvegarde).
- **Dashboard** : analyse et visualisations (vrai vs prédit, résidus, kWh/jour).
- **Alertes / Notifications** : synthèse des alertes sur la période.
- **Recommandations** : actions concrètes + contexte (météo / tarifs) sans refaire le dashboard.
- **Historique** : traçabilité DB (liste prédictions + alertes + recos + export).
- **À propos / Documentation** : la page actuelle (pour soutenance & lecture projet).
"""
)

# -----------------------------
# 4) Machine Learning (explication soutenance)
# -----------------------------
st.markdown("## 🤖 Machine Learning (explication claire)")
st.markdown(
    """
### Modèle
- Modèle principal : **Random Forest** (prédiction de la puissance **Aggregate**).
- Horizon : **H minutes** (défini dans `model_meta_house21.json` et utilisé dans `build_features()`).

### Feature Engineering (exemples)
- **Heure / jour / mois / week-end**
- Encodage cyclique **sin/cos**
- **Lags** (1 → 60 minutes)
- **Rolling statistics** (moyennes / écart-type)

### Évaluation
- **MAE, RMSE, MAPE, R²**
- Comparaison possible avec une **baseline** (si disponible dans `reports/`)

"""
)

# -----------------------------
# 5) Alertes & recommandations (logique)
# -----------------------------
st.markdown("## 🚨 Alertes & 💡 Recommandations (logique métier)")
st.markdown(
    """
### Alertes
Le moteur d’alertes détecte des situations utiles à l’utilisateur, par exemple :
- pics extrêmes (p90 / p99),
- base load anormale,
- soirée trop énergivore,
- biais du modèle sur la période, etc.

### Recommandations
Elles sont orientées **actions** :
- “quoi faire” (réduire veilles, éviter cumuls…),
- “quand le faire” (tarifs HP/HC),
- “pourquoi c’est arrivé” (contexte météo, corrélation indicative).
"""
)

# -----------------------------
# 6) Base de données (SQLite + SQLAlchemy)
# -----------------------------
st.markdown("## 🗃️ Base de données (SQLite + SQLAlchemy)")
st.markdown(
    f"""
- Type : **SQLite** (un fichier local)
- Fichier DB : **`{DB_PATH}`**
- ORM : **SQLAlchemy**
- Tables : `predictions`, `alerts`, `recommendations`

✅ Intérêt : **persister l’historique** (traçabilité) et pouvoir **exporter** des rapports.
"""
)

# Essayer de créer tables (sans casser si déjà OK)
with st.expander("🔧 Vérifier la DB (diagnostic)"):
    try:
        Base.metadata.create_all(bind=engine)
        st.success("DB OK : tables accessibles (create_all exécuté sans erreur).")
    except Exception as e:
        st.error(f"DB KO : {e}")

    try:
        preds = list_predictions(limit=50)
        st.write(f"Nombre de prédictions enregistrées : **{len(preds)}**")
        if preds:
            last = preds[0]
            st.write(
                f"Dernière prédiction : **#{last.id}**, créée le **{last.created_at}**, période **{last.start_date} → {last.end_date}**"
            )
    except Exception as e:
        st.warning(f"Impossible de lire l’historique : {e}")

st.markdown(
    """
📌 **Comment ouvrir `ecoenergy.db` ?**  
- Avec **DB Browser for SQLite** (interface simple), ou  
- avec l’extension **SQLite** dans VS Code.  
Vous verrez directement les tables et les lignes.
"""
)

# -----------------------------
# 7) Exports (Excel vs JSON)
# -----------------------------
st.markdown("## ⬇️ Exports (Excel & JSON) ")
st.markdown(
    """
- **Excel (.xlsx)** : parfait pour la soutenance et la lecture humaine (tableau des prédictions).
- **JSON** : parfait pour un “rapport complet” **structuré** (prédiction + alertes + recommandations).
  - utile si vous voulez : archiver, partager, ou recharger plus tard,
  - utile aussi si un jour vous faites une API / intégration (format standard).
"""
)

# -----------------------------
# 8) Guide d’utilisation (pas à pas)
# -----------------------------
st.markdown("## 🧪 Comment utiliser l’app (workflow)")
st.markdown(
    """
1) Aller dans **Home**  
2) Choisir une **période**  
3) Cliquer **Lancer la prédiction**  
4) Consulter :
   - **Dashboard** (analyse)
   - **Alertes** (anomalies)
   - **Recommandations** (actions)
5) Aller dans **Historique** pour retrouver les analyses + exporter.
"""
)

# -----------------------------
# 9) Pitch soutenance (super important)
# -----------------------------
st.markdown("## 🎤 Résumé ")
st.info(
    """
**EcoEnergy Insight** est une application d’aide à la décision énergétique basée sur des données réelles (House 21 – REFIT).
Nous avons construit un pipeline complet : **préparation**, **prédiction ML**, **évaluation**, puis **interprétation** via alertes et recommandations.
Enfin, nous avons intégré une base **SQLite + SQLAlchemy** pour conserver l’historique des analyses et permettre l’export (Excel/JSON),
ce qui rend le projet **traçable, démontrable et professionnel** pour la soutenance.
"""
)

# -----------------------------
# 10) Limites & prochaines améliorations
# -----------------------------
st.markdown("## ⚠️ Limites & améliorations possibles")
st.markdown(
    """
### Limites 
- La météo est utilisée comme **contexte**, pas comme feature du modèle (pas dans l’entraînement).
- Les tarifs HP/HC sont une **simulation** (valeurs paramétrables).
- SQLite est une base locale (parfait académique), pas un serveur multi-utilisateur.

"""
)

st.markdown("---")
st.caption("EcoEnergy Insight — Documentation intégrée (page About).")
