# ecobot.py
import streamlit as st
import numpy as np
import pandas as pd
import re

# --- Petites fonctions utilitaires internes ---

def _power_to_kwh(series_w: pd.Series) -> float:
    """Convertit une série de puissances (W/minute) en kWh sur la période."""
    return series_w.sum() / (1000 * 60)


def _daily_kwh(series_w: pd.Series) -> pd.Series:
    """Convertit une série W/minute en énergie journalière (kWh/jour)."""
    return series_w.resample("D").sum() / (1000 * 60)


def _describe_day(df_day: pd.DataFrame):
    """Retourne quelques stats simples sur un jour donné."""
    s = df_day["Aggregate"]
    kwh = _power_to_kwh(s)
    mean_w = s.mean()
    max_w = s.max()
    min_w = s.min()
    return kwh, mean_w, max_w, min_w


# --- Cœur du chatbot : génération de la réponse ---

def answer_ecobot(question: str,
                  df: pd.DataFrame,
                  start: pd.Timestamp,
                  end: pd.Timestamp,
                  y_use: pd.Series,
                  y_pred: pd.Series,
                  metrics: dict,
                  H: int) -> str:
    """
    Génère une réponse texte à partir de la question de l’utilisateur
    en utilisant des règles simples + les données du projet.
    """
    q = question.lower().strip()

    # ----------------- 1) Explication des métriques -----------------
    if any(k in q for k in ["mae", "rmse", "r2", "r²", "mape"]):
        txt = []
        txt.append("Voici une explication des principales métriques utilisées 👇\n")
        txt.append(f"- **MAE (Mean Absolute Error)** : erreur absolue moyenne entre la vraie consommation et la valeur prédite. "
                   f"Plus c’est petit, mieux le modèle colle à la réalité. Sur la période sélectionnée, MAE ≈ **{metrics['MAE']:.1f} W**.")
        txt.append(f"- **RMSE (Root Mean Squared Error)** : pénalise davantage les grosses erreurs. "
                   f"Sur la période, RMSE ≈ **{metrics['RMSE']:.1f} W**.")
        txt.append(f"- **R² (coefficient de détermination)** : mesure la part de variance expliquée par le modèle. "
                   f"Un R² proche de 1 signifie un modèle très explicatif. Ici R² ≈ **{metrics['R2']:.3f}**.")
        txt.append(f"- **MAPE (Mean Absolute Percentage Error)** : erreur moyenne en pourcentage. "
                   f"Ici ≈ **{metrics['MAPE%']:.1f}%**.\n")
        txt.append(f"Concrètement : notre modèle prédit la puissance à **+{H} minutes** avec une erreur "
                   "moyenne raisonnable, ce qui est suffisant pour un assistant d’aide à la décision énergétique.")
        return "\n".join(txt)

    # ----------------- 2) Consommation du jour X -----------------
    # On cherche une date au format AAAA-MM-JJ dans la question
    date_match = re.search(r"\d{4}-\d{2}-\d{2}", question)
    if "consommation" in q and date_match:
        date_str = date_match.group(0)
        try:
            day_df = df.loc[date_str]
        except KeyError:
            day_df = pd.DataFrame()

        if day_df is None or len(day_df) == 0:
            return (f"Je n’ai pas trouvé de données pour le **{date_str}** dans le dataset. "
                    "Vérifie que la date est bien dans la période REFIT de House 21.")

        kwh, mean_w, max_w, min_w = _describe_day(day_df)

        # Comparaison avec la période actuelle (si y_use non vide)
        period_df = df.loc[start:end]
        daily_kwh_period = _daily_kwh(period_df["Aggregate"])
        median_kwh = daily_kwh_period.median() if len(daily_kwh_period) > 0 else np.nan

        txt = []
        txt.append(f"📅 **Consommation du {date_str} (House 21)**")
        txt.append(f"- Énergie totale ≈ **{kwh:.2f} kWh** sur la journée")
        txt.append(f"- Puissance moyenne ≈ **{mean_w:.0f} W**")
        txt.append(f"- Pic de puissance ≈ **{max_w:.0f} W**")
        txt.append(f"- Puissance minimale ≈ **{min_w:.0f} W**\n")

        if not np.isnan(median_kwh):
            if kwh > 1.2 * median_kwh:
                txt.append("🔴 Ce jour consomme **au-dessus de la médiane** des jours de la période sélectionnée.")
                txt.append("Il est intéressant de regarder quels appareils étaient utilisés ce jour-là.")
            elif kwh < 0.8 * median_kwh:
                txt.append("🟢 Ce jour consomme **plutôt moins** que la médiane des jours de la période.")
            else:
                txt.append("🟠 Ce jour est **proche de la consommation typique** de la maison sur cette période.")
        return "\n".join(txt)

        # ----------------- 3) Comment réduire la consommation ? -----------------
    if any(k in q for k in ["réduire", "diminuer", "baisser", "facture", "économiser"]):
        period_df = df.loc[start:end]
        if len(period_df) == 0:
            return ("Pour te proposer des conseils personnalisés, il faut d’abord sélectionner une période "
                    "dans le tableau de bord et lancer la prédiction.")

        # Base load = p10
        base_load = period_df["Aggregate"].quantile(0.10)

        # Part du soir (18h–23h)
        evening = period_df.between_time("18:00", "23:00")["Aggregate"]
        total_kwh = _power_to_kwh(period_df["Aggregate"])
        evening_kwh = _power_to_kwh(evening)
        ratio_evening = 100 * evening_kwh / total_kwh if total_kwh > 0 else 0

        txt = []
        txt.append("💡 **Pistes concrètes pour réduire ta consommation sur cette période :**\n")

        txt.append(
            "1️⃣ **Agir sur les pics de consommation**  \n"
            "- Évite de lancer plusieurs gros appareils en même temps "
            "(four, lave-linge, sèche-linge).  \n"
            "- Essaie de déplacer ces usages en dehors des heures de pointe "
            "si ton contrat le permet.\n"
        )

        txt.append(
            f"2️⃣ **Réduire la charge de base**  \n"
            f"- La charge de base (≈ p10) est autour de **{base_load:.0f} W**.  \n"
            "- Cela correspond souvent aux appareils en veille "
            "(box internet, TV, frigo ancien, chargeurs branchés en permanence).  \n"
            "- Identifier et éteindre ces veilles peut réduire ta facture "
            "**sans changer ton confort**.\n"
        )

        txt.append(
            f"3️⃣ **Optimiser les soirées (18h–23h)**  \n"
            f"- Sur la période sélectionnée, environ **{ratio_evening:.1f}%** de l’énergie "
            "est consommée le soir.  \n"
            "- Si ce pourcentage est élevé, tu peux :  \n"
            "  • programmer le lave-linge pendant la nuit ou tôt le matin  \n"
            "  • utiliser moins d’appareils énergivores en même temps le soir.\n"
        )

        txt.append(
            "4️⃣ **Suivre les indicateurs du modèle**  \n"
            "- Surveille **RMSE** et **MAPE** : si ces valeurs diminuent au fil du temps, "
            "cela veut dire que le profil de consommation devient plus régulier et prévisible.  \n"
            "- En pratique, cela signifie que tu as réussi à stabiliser tes usages.\n"
        )

        txt.append(
            "En résumé : moins de veilles inutiles, étaler les gros appareils, "
            "et surveiller les pics → c’est la combinaison la plus efficace pour réduire ta facture ⚡."
        )
        return "\n".join(txt)


    # ----------------- 4) Question sur les pics / base load / qualité du modèle -----------------
    if "pic" in q or "pointe" in q or "base" in q or "charge" in q:
        period_df = df.loc[start:end]
        if len(period_df) == 0:
            return "Je n’ai pas de période sélectionnée pour analyser les pics de consommation."

        s = period_df["Aggregate"]
        p90 = s.quantile(0.90)
        p10 = s.quantile(0.10)

        txt = []
        txt.append("📊 **Analyse rapide du profil de charge sur la période sélectionnée :**")
        txt.append(f"- Seuil de **pic (p90)** ≈ **{p90:.0f} W**")
        txt.append(f"- **Charge de base (p10)** ≈ **{p10:.0f} W**")
        txt.append("- Les valeurs au-dessus du p90 correspondent aux instants où plusieurs appareils "
                   "fonctionnent en même temps ou à l’usage d’un gros appareil (four, chauffe-eau…).")
        txt.append("- La charge de base reflète les équipements toujours allumés (frigo, box, routeur…).")
        return "\n".join(txt)

    # ----------------- 5) Réponse par défaut -----------------
    txt = []
    txt.append("Je n’ai pas parfaitement compris ta question, mais voici ce que je peux faire :")
    txt.append("- t’expliquer les métriques : **MAE, RMSE, R², MAPE**")
    txt.append("- analyser la **consommation d’un jour précis** (ex : `consommation du 2015-04-02`)")
    txt.append("- donner des conseils pour **réduire la consommation** ou lisser les pics")
    txt.append("- résumer le **profil de charge** sur la période sélectionnée.\n")
    txt.append("Essaie par exemple : `explique MAE et RMSE`, "
               "`explique la consommation du 2015-04-02` ou `comment réduire la consommation ?`")
    return "\n".join(txt)


# --- Rendu Streamlit du chatbot ---

def render_ecobot(df, start, end, y_use, y_pred, metrics, H):
    """
    Affiche l’onglet EcoBot dans Streamlit.
    df : DataFrame complet House 21
    start, end : bornes de la période sélectionnée
    y_use : série des vraies valeurs (puissance) sur la période
    y_pred : série des valeurs prédites
    metrics : dictionnaire des métriques sur la période
    H : horizon de prédiction en minutes
    """
    st.subheader("🤖 EcoBot – Assistant énergie")
    st.caption(
        "Pose une question en langage naturel, par exemple : "
        "`explique MAE, RMSE, R²`, "
        "`explique la consommation du 2015-04-02`, "
        "`comment réduire la consommation ?`"
    )

    # Bouton visuel (bonus demandé par la prof)
    st.button("💬 Pose ta question à EcoBot", use_container_width=True)

    # Historique de conversation
    if "ecobot_messages" not in st.session_state:
        st.session_state.ecobot_messages = [
            {
                "role": "assistant",
                "content": (
                    "Bonjour, je suis **EcoBot** 🌱.\n\n"
                    "Je peux t’aider à comprendre :\n"
                    "- les métriques du modèle (MAE, RMSE, R², MAPE),\n"
                    "- la consommation d’un jour précis,\n"
                    "- comment réduire ta consommation et lisser les pics.\n\n"
                    "N’hésite pas à me poser une question !"
                ),
            }
        ]

    # Affichage de l'historique
    for msg in st.session_state.ecobot_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Zone de saisie
    user_q = st.chat_input("Écris ta question à EcoBot ici…")
    if user_q:
        # Ajouter la question de l'utilisateur
        st.session_state.ecobot_messages.append(
            {"role": "user", "content": user_q}
        )

        # Générer la réponse
        answer = answer_ecobot(
            user_q, df=df, start=start, end=end,
            y_use=y_use, y_pred=y_pred, metrics=metrics, H=H
        )

        st.session_state.ecobot_messages.append(
            {"role": "assistant", "content": answer}
        )

        st.rerun()
