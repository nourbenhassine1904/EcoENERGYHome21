# notifications_ui.py
# Ce fichier contient le code pour l'interface utilisateur des notifications dans l'application EcoENERGY.

# Importation de la bibliothèque Streamlit, qui permet de créer des applications web interactives en Python.
import streamlit as st

# Définition de la fonction render_top_notifications, qui gère l'affichage des notifications en haut de la page.
def render_top_notifications():
    # Récupération de la liste des alertes depuis l'état de session de Streamlit.
    # Si aucune alerte n'est présente, on utilise une liste vide par défaut.
    alerts = st.session_state.get("alerts", [])

    # Vérification s'il y a des alertes. Si la liste est vide, on sort de la fonction pour ne rien afficher.
    if not alerts:
        return

    # Filtrage des alertes pour séparer celles de niveau "critical" (critique).
    # On utilise une compréhension de liste pour créer une nouvelle liste contenant seulement les alertes critiques.
    crit = [a for a in alerts if a.level == "critical"]

    # Filtrage des alertes pour séparer celles de niveau "warning" (avertissement).
    # Même approche que pour les alertes critiques.
    warn = [a for a in alerts if a.level == "warning"]

    # Commentaire : Initialisation du badge texte qui sera affiché sur le bouton des notifications.
    # Le badge indique le nombre d'alertes critiques et d'avertissements.

    # Initialisation d'une chaîne vide pour le badge.
    badge = ""

    # Si il y a des alertes critiques, on ajoute un emoji rouge suivi du nombre d'alertes critiques au badge.
    if crit:
        badge += f"🔴 {len(crit)} "

    # Si il y a des alertes d'avertissement, on ajoute un emoji orange suivi du nombre d'alertes d'avertissement au badge.
    if warn:
        badge += f"🟠 {len(warn)}"

    # Création de deux colonnes dans l'interface Streamlit : une large (8/10) et une étroite (2/10).
    # La colonne 1 (col1) n'est pas utilisée ici, mais col2 contiendra le bouton.
    col1, col2 = st.columns([8, 2])

    # Utilisation de la deuxième colonne pour placer le bouton des notifications.
    with col2:
        # Création d'un bouton avec un emoji de cloche et le texte "Notifications" suivi du badge.
        # Le bouton permet de basculer l'affichage du panneau d'alertes.
        if st.button(f"🔔 Notifications {badge}"):
            # Inversion de l'état du panneau d'alertes dans l'état de session.
            # Si le panneau était affiché, il sera masqué, et vice versa.
            # On utilise .get() pour obtenir la valeur actuelle, avec False par défaut si elle n'existe pas.
            st.session_state["show_alerts_panel"] = not st.session_state.get(
                "show_alerts_panel", False
            )

    # Commentaire : Section pour le panneau déroulant des alertes.
    # Ce panneau s'affiche seulement si l'utilisateur a cliqué sur le bouton.

    # Vérification si le panneau d'alertes doit être affiché (basé sur l'état de session).
    if st.session_state.get("show_alerts_panel", False):
        # Affichage d'un titre en Markdown pour le panneau d'alertes récentes, avec un emoji d'avertissement.
        st.markdown("### ⚠️ Alertes récentes")

        # Boucle sur chaque alerte dans la liste pour les afficher une par une.
        for a in alerts:
            # Si le niveau de l'alerte est "critical", on l'affiche en rouge avec st.error().
            if a.level == "critical":
                st.error(f"**{a.title}** — {a.message}")
            # Sinon, si le niveau est "warning", on l'affiche en orange avec st.warning().
            elif a.level == "warning":
                st.warning(f"**{a.title}** — {a.message}")
            # Pour tous les autres niveaux (par exemple "info"), on l'affiche en bleu avec st.info().
            else:
                st.info(f"**{a.title}** — {a.message}")
