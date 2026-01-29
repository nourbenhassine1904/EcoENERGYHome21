# assistant.py
import streamlit as st
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Commentaire pédagogique (FR) :
# Ce fichier contient un assistant qui analyse une série temporelle de
# consommation électrique (colonne "Aggregate") et produit un rapport
# non-technique en français. Les fonctions ci-dessous font :
# - calculs simples sur les séries (kWh, percentiles, pics),
# - construction d'un prompt pour un LLM (optionnel),
# - génération d'un rapport local (texte markdown),
# - interface minimale Streamlit pour afficher le rapport.
# ---------------------------------------------------------------------------


# ---------------------------
# Helpers
# ---------------------------
def _kwh_from_w_series(s_w: pd.Series) -> float:
        """
        Convertit une série de puissances (W) en énergie (kWh).

        Explication pas-à-pas :
        - s_w.sum() fait la somme des valeurs en watts-minute (on suppose que
            les mesures sont espacées d'une minute).
        - Diviser par 1000 convertit W en kW.
        - Diviser par 60 convertit les minutes en heures (kW·h = kWh).
        - Si la série est vide ou None, renvoyer 0.0 pour éviter une erreur.
        """
        return float(s_w.sum() / (1000 * 60)) if s_w is not None and len(s_w) else 0.0


def _safe_pct(a, b):
    """
    Calcule un pourcentage sécurisé : (a / b) * 100.

    - Si b est nul ou falsy, on renvoie 0.0 pour éviter la division par zéro.
    - Convertit le résultat en float.
    """
    return float(100 * a / b) if b and b > 0 else 0.0


def _fmt_hours(hours):
    """
    Formate une liste d'heures (ex: [18, 20]) en chaîne lisible '18h, 20h'.

    - Si la liste est vide, renvoie "N/A".
    - On force l'entier et on ajoute un zéro si nécessaire (02d) pour la lisibilité.
    """
    if not hours:
        return "N/A"
    return ", ".join([f"{int(h):02d}h" for h in hours])


def _median_or_nan(x: pd.Series):
    """
    Retourne la médiane d'une série si elle existe, sinon NaN.
    Utile pour éviter d'avoir des erreurs quand il n'y a pas de données.
    """
    return float(x.median()) if x is not None and len(x) else np.nan


def _clamp(x, lo, hi):
    """
    Rentre une valeur x dans l'intervalle [lo, hi].

    - Tente de convertir x en float.
    - Si la conversion échoue, renvoie la borne basse par défaut (lo).
    """
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return lo


# ---------------------------
# 1) Indicateurs (robustes)
# ---------------------------
def compute_energy_insights(
    df_full: pd.DataFrame | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    y_true: pd.Series,
    y_pred: pd.Series,
    baseline_days: int = 7,
) -> dict | None:

    # Vérifications d'entrées : s'assurer qu'on a bien un DataFrame
    # indexé par des dates et contenant la colonne 'Aggregate'. Sinon,
    # on ne peut pas calculer les métriques — on renvoie None.
    if df_full is None or not isinstance(df_full, pd.DataFrame):
        return None
    if not isinstance(df_full.index, pd.DatetimeIndex):
        return None
    if "Aggregate" not in df_full.columns:
        return None

    # Extraction de la période d'étude : on découpe df_full entre start et end.
    # Utiliser try/except pour capturer des erreurs sur les types de dates.
    try:
        df_period = df_full.loc[start:end].copy()
    except Exception:
        return None

    # Si après découpe il n'y a pas de données, on ne peut rien faire.
    if df_period.empty:
        return None

    # Séries de puissance nettoyée (sans NaN). On exige au moins 60 points
    # pour avoir des statistiques raisonnables.
    s = df_period["Aggregate"].dropna()
    if s.empty or len(s) < 60:
        return None

    # Calcul de la période baseline (précédente) pour comparer le comportement
    # par défaut (ex : 7 jours avant le début de la période étudiée).
    base_start = start - pd.Timedelta(days=baseline_days)
    base_end = start - pd.Timedelta(minutes=1)
    df_base = df_full.loc[base_start:base_end].copy()
    s_base = df_base["Aggregate"].dropna() if not df_base.empty else pd.Series(dtype=float)

    # Calcul de statistiques simples : énergie totale, moyenne et pic.
    total_kwh = _kwh_from_w_series(s)
    mean_w = float(s.mean())
    max_w = float(s.max())

    # Percentiles utiles pour décrire la distribution de la puissance.
    # p10 : niveau de base ; p50 : médiane ; p90/p99 : seuils de pic.
    p10 = float(s.quantile(0.10))
    p50 = float(s.quantile(0.50))
    p90 = float(s.quantile(0.90))
    p99 = float(s.quantile(0.99))

    # Séparation par créneaux horaire : soirée et nuit.
    evening = df_period.between_time("18:00", "23:00")["Aggregate"].dropna()
    night = df_period.between_time("00:00", "06:00")["Aggregate"].dropna()
    # On calcule la part (en %) de l'énergie consommée pendant ces créneaux.
    ratio_evening = _safe_pct(_kwh_from_w_series(evening), total_kwh)
    ratio_night = _safe_pct(_kwh_from_w_series(night), total_kwh)

    # Détection des pics : on considère comme pic tout point > p90.
    peaks_mask = s > p90
    nb_peaks = int(peaks_mask.sum())
    # Pourcentage de points correspondant à des pics.
    peaks_ratio = float(100 * nb_peaks / len(s))

    # Heures les plus concernées par les pics : on regroupe par heure et
    # on garde les 3 heures qui ont la plus grande moyenne de puissance.
    top_peak_hours = []
    if nb_peaks > 0:
        peak_hours = (
            s[peaks_mask]
            .groupby(s[peaks_mask].index.hour)
            .mean()
            .sort_values(ascending=False)
        )
        top_peak_hours = [int(h) for h in peak_hours.head(3).index.tolist()]

    # Conversion en énergie par jour (kWh) et calcul de la médiane quotidienne.
    daily_kwh = (s.resample("D").sum() / (1000 * 60)).dropna()
    daily_median = _median_or_nan(daily_kwh)

    # Analyse des résidus entre la prédiction et la vérité terrain (y_true).
    # - On aligne les indices, on enlève les NaN, puis on calcule :
    #   biais moyen (prédit - vrai), écart-type, et pourcentages sous/over.
    y_true_al = y_true.dropna()
    y_pred_al = y_pred.reindex(y_true_al.index).dropna()
    common = y_true_al.index.intersection(y_pred_al.index)
    resid = (y_pred_al.loc[common] - y_true_al.loc[common]).dropna()

    bias = float(resid.mean()) if len(resid) else 0.0
    resid_std = float(resid.std()) if len(resid) else 0.0
    under_ratio = float((resid < 0).mean() * 100) if len(resid) else 0.0
    over_ratio = float((resid > 0).mean() * 100) if len(resid) else 0.0

    return {
        "start": str(start),
        "end": str(end),
        "total_kwh": total_kwh,
        "mean_w": mean_w,
        "max_w": max_w,
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "p99": p99,
        "ratio_evening": ratio_evening,
        "ratio_night": ratio_night,
        "nb_peaks": nb_peaks,
        "peaks_ratio": peaks_ratio,
        "top_peak_hours": top_peak_hours,
        "daily_kwh": daily_kwh,
        "daily_median_kwh": float(daily_median) if not np.isnan(daily_median) else None,
        "bias": bias,
        "resid_std": resid_std,
        "under_ratio": under_ratio,
        "over_ratio": over_ratio,
        "baseline": {"has_baseline": len(s_base) > 0, "baseline_days": baseline_days},
    }


# ---------------------------
# 2) Prompt Engineering (template)
# ---------------------------
def build_prompt(ins: dict, metrics: dict, H: int) -> str:
        """
        Construit un prompt (texte) pour un modèle de langage si nécessaire.

        - Le prompt décrit le rôle, l'objectif, les contraintes et fournit les
            métriques chiffrées que le modèle doit utiliser pour écrire le rapport.
        - Ici, le texte est en anglais pour le rôle mais demande explicitement
            des phrases simples en français dans les contraintes (cf. usage interne).
        """
        return f"""
ROLE:
You are EcoEnergy Assistant. You generate a clear, non-technical, action-oriented energy report.

GOAL:
Explain what happened during the selected period, then propose concrete actions to reduce waste and peaks.

CONSTRAINTS:
- Simple French, short sentences.
- Always cite numbers (kWh, p10/p90/p99, evening/night shares, peaks).
- Output structure:
    1) Diagnostic
    2) Explication non-tech
    3) Recommandations (3–7)
    4) Priorités (Top 2) + Plan 7 jours
    5) Transparence modèle (2 lignes)

MODEL CONTEXT:
- Horizon: +{H} minutes
- Metrics: MAE={metrics.get('MAE',0):.1f}, RMSE={metrics.get('RMSE',0):.1f}, MAPE={metrics.get('MAPE%',0):.1f}, R2={metrics.get('R2',0):.3f}

DATA:
- total_kwh={ins['total_kwh']:.2f}
- mean_w={ins['mean_w']:.0f}, max_w={ins['max_w']:.0f}
- p10={ins['p10']:.0f}, p50={ins['p50']:.0f}, p90={ins['p90']:.0f}, p99={ins['p99']:.0f}
- ratio_evening={ins['ratio_evening']:.1f}, ratio_night={ins['ratio_night']:.1f}
- peaks_ratio={ins['peaks_ratio']:.1f}, nb_peaks={ins['nb_peaks']}
- top_peak_hours={ins['top_peak_hours']}
""".strip()


# ---------------------------
# 3) Génération rapport premium (local, sans API)
# ---------------------------
def generate_report(ins: dict, metrics: dict, H: int) -> str:
    # petits scores (heuristiques)
    high_evening = ins["ratio_evening"] >= 50
    high_night = ins["ratio_night"] >= 25
    high_baseload = ins["p10"] >= 300
    many_peaks = ins["peaks_ratio"] >= 12
    extreme_peaks = ins["p99"] >= (ins["p90"] * 1.35)

    # Construction du rapport : on assemble une liste de lignes markdown
    # pour être affichée proprement dans Streamlit.
    lines = []
    lines.append("## 🧠 EcoEnergy Assistant — Rapport intelligent\n")
    lines.append(f"**Période analysée :** {ins['start']} → {ins['end']}\n")

    # 1) Diagnostic : synthèse chiffrée et compréhensible pour un public
    # non-technique (p.ex. : une étudiante qui veut comprendre son profil).
    lines.append("### 1) Diagnostic")
    lines.append(f"- Énergie totale : **{ins['total_kwh']:.2f} kWh**")
    lines.append(f"- Puissance moyenne : **{ins['mean_w']:.0f} W** ; pic max : **{ins['max_w']:.0f} W**")
    lines.append(f"- Charge de base (p10) : **{ins['p10']:.0f} W** ; pics (p90) : **{ins['p90']:.0f} W** ; extrêmes (p99) : **{ins['p99']:.0f} W**")
    lines.append(f"- Soir (18–23h) : **{ins['ratio_evening']:.1f}%** ; Nuit (0–6h) : **{ins['ratio_night']:.1f}%**")
    lines.append(f"- Pics : **{ins['peaks_ratio']:.1f}%** du temps (**{ins['nb_peaks']}** points) ; heures critiques : **{_fmt_hours(ins['top_peak_hours'])}**")

    # 2) Explication simple : donner du sens aux nombres pour une personne
    # qui ne maîtrise pas forcément les termes techniques.
    lines.append("\n### 2) Ce que ça signifie (non-tech)")
    lines.append(f"- **p10 = {ins['p10']:.0f} W** : consommation “toujours allumée” (veilles, box, frigo…).")
    lines.append(f"- **p90 = {ins['p90']:.0f} W** : moments où plusieurs appareils tournent ensemble.")
    if high_night:
        lines.append("- La **nuit** pèse lourd → probable appareils laissés actifs (chauffe-eau, veilles, réseau).")
    if high_evening:
        lines.append("- La **soirée** concentre beaucoup d’énergie → cumuls d’usages (cuisine + machines + eau chaude).")
    if extreme_peaks:
        lines.append("- Des **pics extrêmes** existent → un gros appareil ponctuel (four, sèche-linge…) est probable.")
    if many_peaks:
        lines.append("- Beaucoup de **pics** → profil instable, risque de surcoût.")

    # 3) Recommandations pratiques : listes d'actions simples à mettre en place.
    lines.append("\n### 3) Recommandations personnalisées (3–7)")
    recos = []

    # Recommandations liées au base load / nuit
    if high_baseload or high_night:
        recos.append(f"✅ **Baisser la base load** (objectif : réduire p10 = {ins['p10']:.0f} W) : multiprises OFF la nuit, veilles, box/routeur, mode éco.")
        recos.append(f"✅ **Audit nuit (0–6h)** : nuit = {ins['ratio_night']:.1f}% → vérifier chauffe-eau, appareils en veille, programmation.")
    else:
        recos.append("✅ **Base load correcte** : continuer les bonnes pratiques (veilles minimisées).")

    # Recommandations liées à la soirée
    if high_evening:
        recos.append(f"✅ **Désaturer 18–23h** : soir = {ins['ratio_evening']:.1f}% → éviter 2 gros appareils en parallèle.")
        if ins["top_peak_hours"]:
            recos.append(f"✅ **Heures critiques** : { _fmt_hours(ins['top_peak_hours']) } → déplacer lave-linge/lave-vaisselle de 30–60 min.")
    else:
        recos.append("✅ **Soirée équilibrée** : garder une répartition des usages.")

    recos.append(f"✅ **Réduire les pics** : limiter le temps au-dessus de p90 ({ins['p90']:.0f} W).")

    # Note de transparence sur le modèle si le biais est significatif
    if ins["bias"] < -10:
        recos.append("✅ **Note modèle** : légère sous-estimation → se fier surtout aux tendances et aux pics.")
    elif ins["bias"] > 10:
        recos.append("✅ **Note modèle** : légère sur-estimation → comparer avec le réel.")

    # Ne garder que les 7 premières recommandations pour rester lisible.
    recos = recos[:7]
    lines.extend([f"- {r}" for r in recos])

    # 4) Priorités et plan d'actions sur 7 jours : simple et concret.
    lines.append("\n### 4) Priorités + Plan 7 jours")
    p1 = "Baisser la base load (nuit + veilles)" if (high_baseload or high_night) else "Réduire les pics (éviter les cumuls)"
    p2 = "Désaturer 18–23h (étaler les gros usages)" if high_evening else "Optimiser les horaires des gros appareils"
    lines.append(f"- **Priorité 1 :** {p1}")
    lines.append(f"- **Priorité 2 :** {p2}")

    lines.append("\n**Plan 7 jours (simple)**")
    lines.append("- J1 : couper les veilles la nuit (multiprises).")
    lines.append("- J2 : choisir 1 appareil à décaler hors 18–23h.")
    lines.append("- J3 : repérer une heure de pic et noter l’appareil responsable.")
    lines.append("- J4 : programmer chauffe-eau / machine sur créneau moins chargé (si possible).")
    lines.append("- J5 : journée “sans cumul” (pas 2 gros appareils ensemble).")
    lines.append("- J6 : comparer 2 journées : laquelle a moins de pics ?")
    lines.append("- J7 : relancer une analyse et vérifier : p10 ↓, pics ↓, soirée ↓.")

    # 5) Transparence sur la qualité des prédictions : RMSE, MAPE, biais.
    lines.append("\n---\n### 5) Transparence modèle")
    lines.append(f"- Horizon : **+{H} min** ; RMSE ≈ **{metrics.get('RMSE',0):.1f} W** ; MAPE ≈ **{metrics.get('MAPE%',0):.1f}%**.")
    lines.append(f"- Biais (prédit - vrai) : **{ins['bias']:.1f} W** ; sur={ins['over_ratio']:.1f}% ; sous={ins['under_ratio']:.1f}%.")

    return "\n".join(lines)


# ---------------------------
# 4) UI Streamlit
# ---------------------------
def render_assistant(df_full, start, end, y_use, y_pred, metrics, H):
    st.subheader("🧠 EcoEnergy Assistant — Recommandations intelligentes")
    st.caption("Rapport dynamique : diagnostic chiffré, explications non-tech et plan d’action personnalisé.")

    # Clé pour stocker le rapport dans la session Streamlit en fonction de
    # la période analysée (pour pouvoir avoir plusieurs rapports en cache).
    period_key = f"{pd.to_datetime(start).date()}_{pd.to_datetime(end).date()}"

    # UI : un bouton pour générer le rapport et un toggle pour afficher le
    # prompt (utile pour preuve de prompt engineering en cas d'usage d'un LLM).
    col1, col2 = st.columns([1, 1])
    with col1:
        gen = st.button("⚡ Générer / Mettre à jour le rapport", use_container_width=True)
    with col2:
        show_prompt = st.toggle("Afficher le prompt", value=False)

    # Si l'utilisateur clique sur le bouton : calculer les insights et
    # générer le rapport. On stocke ensuite le résultat dans la session pour
    # éviter de recalculer inutilement.
    if gen:
        ins = compute_energy_insights(df_full, start, end, y_use, y_pred, baseline_days=7)
        if ins is None:
            st.error(
                "❌ Impossible de générer le rapport.\n"
                "➡️ Solution : retourne sur Home, relance une prédiction, et vérifie que df_full est bien stocké."
            )
            return

        st.session_state[f"assistant_ins_{period_key}"] = ins
        st.session_state[f"assistant_report_{period_key}"] = generate_report(ins, metrics, H)

    # Récupération depuis la session : si le rapport existe déjà, on l'affiche.
    ins = st.session_state.get(f"assistant_ins_{period_key}")
    report = st.session_state.get(f"assistant_report_{period_key}")

    if ins is None or report is None:
        st.info("👈 Clique sur **Générer / Mettre à jour le rapport**.")
        return

    # Optionnel : afficher le prompt si l'on veut voir la consigne envoyée au
    # modèle de langage (utile pour l'enseignement/validation).
    if show_prompt:
        with st.expander("🔎 Prompt utilisé (preuve de prompt engineering)"):
            st.code(build_prompt(ins, metrics, H), language="text")

    # Affichage final du rapport au format markdown.
    st.markdown(report)
