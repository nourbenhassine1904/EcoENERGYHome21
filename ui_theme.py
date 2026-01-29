# ui_theme.py
# Ce fichier définit le thème visuel de l'application EcoEnergy en utilisant du CSS personnalisé injecté via Streamlit.

# Importation de la bibliothèque Streamlit pour injecter le CSS dans l'application.
import streamlit as st

# Définition de la fonction apply_theme, qui applique le thème personnalisé à l'application Streamlit.
def apply_theme():
    # Utilisation de st.markdown pour injecter du HTML/CSS dans l'application.
    # Le paramètre unsafe_allow_html=True permet d'utiliser du HTML personnalisé.
    st.markdown(
        """
        <style>
        /* ==============================
           ECOENERGY — THEME GLOBAL
           ============================== */

        /* Définition du fond global de l'application avec un dégradé de couleurs douces. */
        .stApp {
            background: linear-gradient(135deg, #f0fdf4 0%, #e0f2fe 40%, #fff7ed 100%);
            color: #0f172a;
        }

        /* Style des titres principaux (h1) avec un dégradé de couleurs et un effet de texte transparent. */
        h1 {
            background: linear-gradient(90deg, #22c55e, #0ea5e9, #f97316);
            -webkit-background-clip: text;
            color: transparent;
            font-weight: 800;
            letter-spacing: -0.02em;
        }

        /* Style des titres secondaires (h2, h3) avec une couleur sombre et un espacement des lettres. */
        h2, h3 {
            color: #0f172a;
            letter-spacing: -0.01em;
        }

        /* ==============================
           SIDEBAR — PREMIUM DARK
           ============================== */

        /* Style de la sidebar avec un fond sombre en dégradé et une bordure droite. */
        section[data-testid="stSidebar"]{
            background: linear-gradient(180deg, #0f172a 0%, #020617 100%);
            border-right: 1px solid #1e293b;
        }

        /* Définition de l'espace interne (padding) de la sidebar pour un meilleur espacement. */
        section[data-testid="stSidebar"] > div {
            padding: 1.1rem 0.9rem;
        }

        /* Couleur du texte dans la sidebar, forcée à une teinte claire. */
        section[data-testid="stSidebar"] * {
            color: #e5e7eb !important;
        }

        /* Couleur des titres dans la sidebar, encore plus claire pour la visibilité. */
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #f8fafc !important;
        }

        /* Style des liens dans la sidebar avec une couleur bleue et un soulignement au survol. */
        section[data-testid="stSidebar"] a {
            color: #93c5fd !important;
            text-decoration: none !important;
        }
        section[data-testid="stSidebar"] a:hover {
            text-decoration: underline !important;
        }

        /* Style d'un séparateur réutilisable dans la sidebar avec une bordure subtile. */
        .sidebar-divider {
            margin: 0.85rem 0 0.95rem 0;
            border-bottom: 1px solid rgba(148, 163, 184, 0.25);
        }

        /* Style d'une "carte" dans la sidebar pour afficher des informations comme le profil. */
        .sidebar-card {
            background: rgba(2, 6, 23, 0.55);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 0.9rem;
            padding: 0.85rem 0.9rem;
            box-shadow: 0 14px 26px rgba(2, 6, 23, 0.35);
            margin-bottom: 0.8rem;
        }
        /* Style du texte petit dans les cartes de la sidebar. */
        .sidebar-card .small {
            font-size: 0.82rem;
            color: #94a3b8 !important;
        }

        /* Style des champs de saisie (input, textarea) dans la sidebar avec un fond sombre. */
        section[data-testid="stSidebar"] input,
        section[data-testid="stSidebar"] textarea {
            background: rgba(15, 23, 42, 0.55) !important;
            border: 1px solid rgba(148, 163, 184, 0.22) !important;
            border-radius: 0.75rem !important;
        }

        /* Style des widgets de sélection (selectbox, multiselect, date) dans la sidebar. */
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-baseweb="input"] > div {
            background: rgba(15, 23, 42, 0.55) !important;
            border-radius: 0.75rem !important;
            border: 1px solid rgba(148, 163, 184, 0.22) !important;
        }

        /* Style général des boutons dans la sidebar avec un arrondi et une police grasse. */
        section[data-testid="stSidebar"] button {
            border-radius: 0.9rem !important;
            font-weight: 600 !important;
        }

        /* Style du bouton principal (comme "Run") avec un dégradé vert et un arrondi complet. */
        button[kind="primary"] {
            background: linear-gradient(135deg, #22c55e, #16a34a) !important;
            color: white !important;
            border-radius: 999px !important;
            border: none !important;
            padding: 0.45rem 1.2rem !important;
        }
        /* Effet au survol du bouton principal pour une légère luminosité. */
        button[kind="primary"]:hover {
            filter: brightness(1.08);
        }

        /* Style des boutons secondaires (comme logout) avec un arrondi. */
        button[kind="secondary"] {
            border-radius: 0.9rem !important;
        }

        /* ==============================
           CARDS / METRICS
           ============================== */

        /* Style des cartes de métriques avec un fond en dégradé radial et une ombre. */
        .metric-card {
            padding: 1rem 1.5rem;
            border-radius: 0.9rem;
            background: radial-gradient(circle at top left, #bbf7d0, #e0f2fe);
            border: 1px solid #bae6fd;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.12);
        }
        /* Style du label des métriques avec une taille petite et une couleur verte. */
        .metric-label {
            font-size: 0.8rem;
            color: #166534;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        /* Style de la valeur des métriques avec une taille grande et une couleur sombre. */
        .metric-value {
            font-size: 1.7rem;
            font-weight: 750;
            color: #022c22;
        }
        /* Style du sous-texte des métriques avec une taille moyenne. */
        .metric-sub {
            font-size: 0.9rem;
            color: #065f46;
        }

        /* Style des métriques Streamlit avec un fond en dégradé et du texte blanc. */
        .stMetric {
            background: linear-gradient(135deg, #0ea5e9, #22c55e);
            padding: 0.8rem 1rem;
            border-radius: 0.8rem;
            color: white !important;
        }

        /* Style des alertes avec un arrondi pour une apparence moderne. */
        .stAlert {
            border-radius: 0.85rem;
        }

        /* Style d'une carte générique avec un fond semi-transparent et une ombre. */
        .card {
            padding: 1rem 1.2rem;
            border-radius: 1rem;
            border: 1px solid #e5e7eb;
            background: rgba(255, 255, 255, 0.65);
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.10);
        }

        </style>
        """,
        unsafe_allow_html=True,
    )
