# ui_sidebar.py
# Ce fichier contient le code pour rendre la barre latérale (sidebar) dans l'application Streamlit EcoEnergy.
# Il utilise Streamlit pour créer une interface utilisateur interactive.
# Import des modules nécessaires :
# - streamlit : bibliothèque pour créer des applications web interactives en Python
# - pandas : bibliothèque pour manipuler des données, ici utilisée pour les dates
# - logout : fonction importée depuis le module auth pour gérer la déconnexion

import streamlit as st
import pandas as pd
from auth import logout


# Définition de la fonction render_sidebar qui crée et affiche la sidebar
# Paramètres :
# - user : dictionnaire contenant les informations de l'utilisateur (nom, email, rôle)
# - df : dataframe optionnel indexé par datetime, utilisé pour la sélection de dates
# - show_date_selector : booléen pour afficher ou non le sélecteur de dates
# - show_run_button : booléen pour afficher ou non le bouton de lancement
def render_sidebar(
    user,
    df=None,
    show_date_selector=True,
    show_run_button=True,
):
    """
    Sidebar EcoEnergy – version premium
    - user : dict {name, email, role}
    - df : dataframe indexé par datetime (optionnel)
    - show_date_selector : afficher la sélection de période
    - show_run_button : afficher le bouton Run
    """

    # =========================
    # LOGO / APP NAME
    # =========================

    # 🔷 LOGO (AJOUTÉ – image depuis le dossier du projet)
    st.sidebar.image(
        "assets/Logo.png",
        use_container_width=True
    )

    # Section pour afficher le logo et le nom de l'application
    # Utilise markdown avec HTML pour styliser le texte
    st.sidebar.markdown(
        """
        <div style="font-size:1.25rem;font-weight:800;letter-spacing:-0.02em;">
            ⚡ EcoEnergy
        </div>
        <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:0.6rem;">
            Insight Platform
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Ajout d'un séparateur visuel dans la sidebar
    st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    # =========================
    # NAVIGATION (info)
    # =========================
    st.sidebar.markdown("### 🧭 Navigation")
    st.sidebar.caption("Utilise le menu *Pages* ci-dessus")

    st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

    # =========================
    # USER CARD
    # =========================
    st.sidebar.markdown("### 👤 Compte")

    st.sidebar.markdown(
        f"""
        <div class="sidebar-card">
            <div style="font-weight:600;">{user['name']}</div>
            <div class="small">{user['email']}</div>
            <div class="small" style="margin-top:0.35rem;">
                🏷️ Rôle : <b>{user['role']}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.sidebar.button("🚪 Se déconnecter"):
        logout()
        st.rerun()

    # =========================
    # STATUT DE LA PRÉDICTION
    # =========================
    if st.session_state.get("pred_ready", False):
        st.sidebar.success("✅ Analyse prête")
        if "pred_start" in st.session_state and "pred_end" in st.session_state:
            st.sidebar.caption(
                f"{st.session_state['pred_start'].date()} → "
                f"{st.session_state['pred_end'].date()}"
            )
    else:
        st.sidebar.info("ℹ️ Aucune analyse active")

    # =========================
    # DATE SELECTION
    # =========================
    start_date = None
    end_date = None
    run_clicked = False

    if show_date_selector and df is not None:
        st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        st.sidebar.markdown("### ⏱️ Période d’analyse")

        min_date = df.index.min().date()
        max_date = df.index.max().date()

        start_date = st.sidebar.date_input(
            "Date de début",
            value=min_date,
            min_value=min_date,
            max_value=max_date,
        )

        end_date = st.sidebar.date_input(
            "Date de fin",
            value=min_date + pd.Timedelta(days=7),
            min_value=min_date,
            max_value=max_date,
        )

        if start_date > end_date:
            st.sidebar.error("⚠️ La date de début est après la date de fin")
            st.stop()

        if user["role"] == "Free":
            max_days = 3
            if (end_date - start_date).days > max_days:
                st.sidebar.warning(
                    f"🔒 Version Free : analyse limitée à {max_days} jours"
                )
                st.stop()

        if show_run_button:
            run_clicked = st.sidebar.button(
                "▶️ Lancer la prédiction",
                type="primary",
                use_container_width=True,
            )

    # =========================
    # FOOTER
    # =========================
    st.sidebar.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
    st.sidebar.caption("EcoEnergy Insight • House 21")

    return start_date, end_date, run_clicked
