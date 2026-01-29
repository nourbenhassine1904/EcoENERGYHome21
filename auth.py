# auth.py
from __future__ import annotations

import streamlit as st

from database.db import engine, Base
from database.crud import (
    authenticate_user,
    create_user,
)

# ============================================================
# DB init + seed users (1 seule fois)
# ============================================================
def _init_db_and_seed_users():
    """
    - Crée les tables si elles n'existent pas
    - Crée 2 comptes par défaut si absents :
        admin / admin123 (role=admin)
        user  / user123  (role=user)
    """
    # 1) créer tables (users/predictions/alerts/recommendations)
    Base.metadata.create_all(bind=engine)

    # 2) seed (si déjà existants => on ignore)
    try:
        create_user(
            username="admin",
            password="admin123",
            role="admin",
            email="admin@ecoenergy.tn",
            is_active=True,
        )
    except ValueError:
        pass

    try:
        create_user(
            username="user",
            password="user123",
            role="user",
            email="user@ecoenergy.tn",
            is_active=True,
        )
    except ValueError:
        pass


# ============================================================
# Session state
# ============================================================
def init_auth_state():
    """
    À appeler au début de CHAQUE page Streamlit (Home + pages/*).
    """
    # Init DB + seed une seule fois par session Streamlit
    if "db_ready" not in st.session_state:
        _init_db_and_seed_users()
        st.session_state["db_ready"] = True

    if "auth" not in st.session_state:
        st.session_state.auth = {
            "is_auth": False,
            "user": None,  # dict: {id, username, email, name, role}
        }


def logout():
    st.session_state.auth = {"is_auth": False, "user": None}
    st.rerun()


# ============================================================
# UI: login form
# ============================================================
def login_form():
    init_auth_state()

    st.title("🔐 Connexion à EcoEnergy Insight")
    st.write("Connectez-vous pour accéder aux pages (Dashboard, Alertes, Historique, etc.)")

    with st.form("login_form", clear_on_submit=False):
        identifier = st.text_input("Identifiant (username ou email)", value="user")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")

    if submitted:
        user = authenticate_user(identifier.strip(), password)
        if user is None:
            st.error("❌ Identifiant ou mot de passe incorrect (ou compte désactivé).")
            return

        # ✅ Format attendu dans votre app : id / username / role
        st.session_state.auth = {
            "is_auth": True,
            "user": {
                "id": int(user.id),
                "username": user.username,
                "email": user.email,
                "name": user.username,  # compat UI existante
                "role": (user.role or "user").lower(),
            },
        }
        st.success(f"Bienvenue {user.username} 👋 (role: {user.role})")
        st.rerun()


# ============================================================
# Helpers (optionnels)
# ============================================================
def require_role(*roles: str):
    """
    Exemple: require_role("admin")
    À utiliser dans les pages protégées.
    """
    init_auth_state()

    if not st.session_state.auth["is_auth"]:
        login_form()
        st.stop()

    role = (st.session_state.auth["user"] or {}).get("role", "").lower()
    roles_norm = [r.lower() for r in roles]

    if role not in roles_norm:
        st.error("⛔ Accès refusé : permissions insuffisantes.")
        st.stop()
