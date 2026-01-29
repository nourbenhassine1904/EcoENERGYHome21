# alerts.py
# Ce fichier gère les alertes dans l'application EcoEnergy, permettant de détecter et afficher des anomalies dans la consommation énergétique.

# Importation de NumPy pour les calculs numériques.
import numpy as np

# Importation de Pandas pour la manipulation des données.
import pandas as pd

# Importation de Streamlit pour l'interface utilisateur.
import streamlit as st

# Importation de dataclass pour créer des classes de données simples.
from dataclasses import dataclass

# Importation de types pour les annotations de type.
from typing import List, Optional, Dict, Any


# ---------------------------
# 1) STRUCTURE D'UNE ALERTE
# ---------------------------
@dataclass
class Alert:
    level: str          # "critical" | "warning" | "info"
    title: str
    message: str
    metric: Optional[str] = None
    value: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None


# ---------------------------
# 2) OUTILS
# ---------------------------
# Définition de la fonction _safe_ratio, qui calcule un ratio en évitant la division par zéro.
def _safe_ratio(num: float, den: float) -> float:
    # Retourner le ratio si le dénominateur est valide, sinon 0.0.
    return float(num / den) if den and den != 0 else 0.0

# Définition de la fonction _kwh_from_wmin, qui convertit une série de watts par minute en kWh.
def _kwh_from_wmin(series_w: pd.Series) -> float:
    # séries minute par minute (W) -> kWh sur la période
    # Calcul de la somme des watts, puis conversion en kWh.
    return float(series_w.sum() / (1000 * 60))

# Définition de la fonction _daily_kwh, qui calcule la consommation énergétique quotidienne en kWh.
def _daily_kwh(df_period: pd.DataFrame) -> pd.Series:
    # W/min -> kWh/jour
    # Rééchantillonnage par jour et conversion en kWh.
    return df_period["Aggregate"].resample("D").sum() / (1000 * 60)

# Définition de la fonction _align_true_pred, qui aligne les séries vraies et prédites.
def _align_true_pred(y_true: pd.Series, y_pred: pd.Series) -> pd.DataFrame:
    # Concaténation des séries avec renommage des colonnes.
    aligned = pd.concat(
        [y_true.rename("true"), y_pred.rename("pred")],
        axis=1
    ).dropna()
    # Retour du DataFrame aligné sans valeurs manquantes.
    return aligned
    

# ---------------------------
# 3) CALCUL DES ALERTES
# ---------------------------
def compute_alerts(
    df_period: pd.DataFrame,
    y_true: pd.Series,
    y_pred: pd.Series,
    metrics: Optional[dict] = None,
) -> List[Alert]:
    """
    Génère des alertes dynamiques et chiffrées sur la période sélectionnée.
    - df_period: df index datetime, colonne Aggregate
    - y_true/y_pred: séries minute par minute sur la période
    """
    alerts: List[Alert] = []

    if df_period is None or len(df_period) == 0:
        return [Alert("info", "Aucune donnée", "La période sélectionnée ne contient aucune donnée exploitable.")]

    s = df_period["Aggregate"].dropna()
    if len(s) < 60:  # trop court pour des alertes sérieuses
        return [Alert("info", "Période trop courte", "Sélectionne une période un peu plus longue pour obtenir des alertes fiables.")]

    # ---------- Indicateurs "profil conso" ----------
    # Calcul des percentiles de la série nettoyée.
    p90 = float(s.quantile(0.90))
    p10 = float(s.quantile(0.10))
    p50 = float(s.quantile(0.50))
    p99 = float(s.quantile(0.99))

    # Calcul de l'énergie totale en kWh.
    total_kwh = _kwh_from_wmin(s)

    # Soirée (18-23) : extraction des données de soirée.
    evening = df_period.between_time("18:00", "23:00")["Aggregate"].dropna()
    # Calcul de l'énergie consommée en soirée.
    evening_kwh = _kwh_from_wmin(evening) if len(evening) else 0.0
    # Calcul du ratio de consommation en soirée.
    ratio_evening = 100 * _safe_ratio(evening_kwh, total_kwh)

    # Base load "adaptatif" : on compare p10 vs p50
    # Calcul du ratio de base load.
    base_ratio = 100 * _safe_ratio(p10, p50)  # ex: si p10=300W et médiane=600W => 50%

    # ---------- Indicateurs journaliers ----------
    # Calcul de la consommation quotidienne en kWh.
    daily_kwh = _daily_kwh(df_period).dropna()

    # si la période couvre plusieurs jours => on compare un jour max à la médiane
    # Si au moins 2 jours, calculer les indicateurs journaliers.
    if len(daily_kwh) >= 2:
        day_max = float(daily_kwh.max())
        day_median = float(daily_kwh.median())
        day_max_ratio = 100 * _safe_ratio(day_max - day_median, day_median)  # % au-dessus médiane
        day_max_date = daily_kwh.idxmax().strftime("%Y-%m-%d")
    else:
        # Sinon, définir les valeurs à NaN.
        day_max = day_median = day_max_ratio = np.nan
        day_max_date = None
        
    # ---------- Indicateurs modèle ----------
    aligned = _align_true_pred(y_true, y_pred)
    if len(aligned) >= 60:
        resid = aligned["pred"] - aligned["true"]
        bias = float(resid.mean())
        resid_std = float(resid.std())

        # biais en % de la médiane (plus robuste)
        bias_pct = 100 * _safe_ratio(abs(bias), p50)

        # jours consécutifs sous/sur-estimés
        daily_true = aligned["true"].resample("D").sum() / (1000 * 60)
        daily_pred = aligned["pred"].resample("D").sum() / (1000 * 60)
        daily_diff = (daily_pred - daily_true).dropna()

        under = daily_diff < 0
        over = daily_diff > 0

        def longest_streak(mask: pd.Series) -> int:
            # longest consecutive True streak
            streak = best = 0
            for v in mask.values:
                if v:
                    streak += 1
                    best = max(best, streak)
                else:
                    streak = 0
            return best

        under_streak = longest_streak(under)
        over_streak = longest_streak(over)
    else:
        bias = 0.0
        resid_std = 0.0
        bias_pct = 0.0
        under_streak = 0
        over_streak = 0

    # =========================================================
    # A) ALERTE PIC ELEVÉ (adaptatif)
    # =========================================================
    # Idée: si p99 est très éloigné de p90 => pics "très extrêmes"
    # Calcul de l'indice de pic.
    spike_index = _safe_ratio(p99 - p90, p90) * 100  # % au-dessus de p90

    # Si l'indice de pic est très élevé, ajouter une alerte critique.
    if spike_index >= 35:
        alerts.append(Alert(
            "critical",
            "Pics très élevés détectés",
            f"Les pics extrêmes sont importants : p90 ≈ **{p90:.0f} W** et p99 ≈ **{p99:.0f} W** "
            f"(+{spike_index:.0f}% au-dessus de p90). "
            "Cela indique probablement des usages simultanés d’appareils énergivores.",
            metric="spike_index",
            value=float(spike_index),
        ))
    # Sinon, si l'indice est élevé, ajouter une alerte d'avertissement.
    elif spike_index >= 20:
        alerts.append(Alert(
            "warning",
            "Pics élevés",
            f"Pics notables : p90 ≈ **{p90:.0f} W** et p99 ≈ **{p99:.0f} W** "
            f"(+{spike_index:.0f}% au-dessus de p90). "
            "Essayez de ne pas cumuler plusieurs gros appareils en même temps.",
            metric="spike_index",
            value=float(spike_index),
        ))
    # Sinon, ajouter une alerte d'information.
    else:
        alerts.append(Alert(
            "info",
            "Pics sous contrôle",
            f"Les pics restent modérés : p90 ≈ **{p90:.0f} W**, p99 ≈ **{p99:.0f} W**.",
            metric="spike_index",
            value=float(spike_index),
        ))
        
    # =========================================================
    # B) ALERTE BASE LOAD ÉLEVÉE (adaptatif)
    # =========================================================
    # Base ratio = p10 / médiane (plus il est haut, plus la base est lourde)
    if base_ratio >= 65:
        alerts.append(Alert(
            "critical",
            "Charge de base très élevée",
            f"La charge de base est très forte : p10 ≈ **{p10:.0f} W** "
            f"(≈ {base_ratio:.0f}% de la consommation typique). "
            "Cela suggère des consommations permanentes (veilles, box, chauffe-eau, frigo…).",
            metric="base_ratio",
            value=float(base_ratio),
        ))
    elif base_ratio >= 45:
        alerts.append(Alert(
            "warning",
            "Charge de base élevée",
            f"Charge de base notable : p10 ≈ **{p10:.0f} W** "
            f"(≈ {base_ratio:.0f}% de la consommation typique). "
            "Un audit des appareils en veille peut réduire la facture sans changer le confort.",
            metric="base_ratio",
            value=float(base_ratio),
        ))
    else:
        alerts.append(Alert(
            "info",
            "Charge de base correcte",
            f"Charge de base raisonnable : p10 ≈ **{p10:.0f} W** (≈ {base_ratio:.0f}% de la médiane).",
            metric="base_ratio",
            value=float(base_ratio),
        ))

    # =========================================================
    # C) ALERTE SOIRÉE TROP LOURDE
    # =========================================================
    if ratio_evening >= 65:
        alerts.append(Alert(
            "critical",
            "Consommation très concentrée le soir",
            f"Entre 18h–23h, la consommation représente **{ratio_evening:.1f}%** de l’énergie totale. "
            "C’est très élevé → possible cumul d’appareils (cuisson + lavage + chauffe-eau…).",
            metric="ratio_evening",
            value=float(ratio_evening),
        ))
    elif ratio_evening >= 50:
        alerts.append(Alert(
            "warning",
            "Soirée énergivore",
            f"Entre 18h–23h, la consommation représente **{ratio_evening:.1f}%** de l’énergie totale. "
            "Essayez d’étaler certains usages (lave-linge, chauffe-eau, etc.).",
            metric="ratio_evening",
            value=float(ratio_evening),
        ))
    else:
        alerts.append(Alert(
            "info",
            "Soirée équilibrée",
            f"Entre 18h–23h : **{ratio_evening:.1f}%** de l’énergie → niveau correct.",
            metric="ratio_evening",
            value=float(ratio_evening),
        ))

    # =========================================================
    # D) ALERTE JOUR ANORMALEMENT HAUT (si multi-jours)
    # =========================================================
    if day_max_date is not None and not np.isnan(day_max_ratio):
        if day_max_ratio >= 40:
            alerts.append(Alert(
                "critical",
                "Journée anormalement élevée",
                f"Le **{day_max_date}** est à **{day_max:.2f} kWh**, soit **+{day_max_ratio:.0f}%** au-dessus de la médiane "
                f"({day_median:.2f} kWh).",
                metric="day_max_ratio",
                value=float(day_max_ratio),
            ))
        elif day_max_ratio >= 20:
            alerts.append(Alert(
                "warning",
                "Journée au-dessus de la normale",
                f"Le **{day_max_date}** est à **{day_max:.2f} kWh**, soit **+{day_max_ratio:.0f}%** au-dessus de la médiane "
                f"({day_median:.2f} kWh).",
                metric="day_max_ratio",
                value=float(day_max_ratio),
            ))
        else:
            alerts.append(Alert(
                "info",
                "Aucune journée extrême",
                "Aucune journée ne dépasse fortement la médiane de la période.",
                metric="day_max_ratio",
                value=float(day_max_ratio),
            ))

    # =========================================================
    # E) ALERTE MODELE : biais / séries sous-estimées
    # =========================================================
    # On utilise bias_pct (en % de médiane) pour être robuste
    if bias_pct >= 20:
        alerts.append(Alert(
            "warning",
            "Biais important du modèle",
            f"Le modèle présente un biais moyen d’environ **{bias:.1f} W** "
            f"(≈ **{bias_pct:.0f}%** de la médiane). "
            "Les alertes basées sur la prédiction sont à interpréter avec prudence.",
            metric="bias_pct",
            value=float(bias_pct),
        ))
    else:
        alerts.append(Alert(
            "info",
            "Biais modèle faible",
            f"Biais moyen ≈ **{bias:.1f} W** (≈ {bias_pct:.0f}% de la médiane).",
            metric="bias_pct",
            value=float(bias_pct),
        ))

    if under_streak >= 3:
        alerts.append(Alert(
            "warning",
            "Sous-prédiction plusieurs jours",
            f"Le modèle a **sous-estimé {under_streak} jours consécutifs** (énergie journalière).",
            metric="under_streak",
            value=float(under_streak),
        ))
    if over_streak >= 3:
        alerts.append(Alert(
            "warning",
            "Sur-prédiction plusieurs jours",
            f"Le modèle a **sur-estimé {over_streak} jours consécutifs** (énergie journalière).",
            metric="over_streak",
            value=float(over_streak),
        ))

    # (Option) Ajout d’un résumé d’énergie
    alerts.append(Alert(
        "info",
        "Résumé énergie période",
        f"Énergie totale sur la période : **{total_kwh:.2f} kWh**.",
        metric="total_kwh",
        value=float(total_kwh),
    ))

    return alerts


# ---------------------------
# 4) RENDER STREAMLIT (PREMIUM)
# ---------------------------
def render_alerts(
    alerts: List[Alert],
    title: str = "⚠️ Alertes automatiques",
    collapsible: bool = True,
):
    if not alerts:
        st.info("Aucune alerte générée.")
        return

    st.subheader(title)

    # Séparation par niveau
    crit = [a for a in alerts if a.level == "critical"]
    warn = [a for a in alerts if a.level == "warning"]
    info = [a for a in alerts if a.level == "info"]

    # ---------------------------
    # KPI Résumé
    # ---------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 Critiques", len(crit))
    c2.metric("🟠 Avertissements", len(warn))
    c3.metric("ℹ️ Infos", len(info))

    st.markdown("")

    # ---------------------------
    # CSS cartes premium
    # ---------------------------
    st.markdown(
        """
        <style>
        .alert-card {
            padding: 0.9rem 1.1rem;
            border-radius: 0.75rem;
            margin-bottom: 0.7rem;
            border-left: 6px solid;
            background: rgba(255,255,255,0.65);
            box-shadow: 0 6px 18px rgba(15,23,42,0.12);
        }
        .alert-critical { border-color: #dc2626; }
        .alert-warning  { border-color: #f59e0b; }
        .alert-info     { border-color: #0ea5e9; }

        .alert-title {
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .alert-meta {
            font-size: 0.75rem;
            opacity: 0.7;
            margin-top: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------
    # Helper d’affichage
    # ---------------------------
    def _render_group(group, css_class, icon):
        for a in group:
            meta = ""
            if a.metric and a.value is not None:
                meta = f"<div class='alert-meta'>🔎 {a.metric} = {a.value:.2f}</div>"

            st.markdown(
                f"""
                <div class="alert-card {css_class}">
                    <div class="alert-title">{icon} {a.title}</div>
                    <div>{a.message}</div>
                    {meta}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---------------------------
    # AFFICHAGE PAR PRIORITÉ
    # ---------------------------
    if crit:
        if collapsible:
            with st.expander("🔴 Alertes critiques (à traiter en priorité)", expanded=True):
                _render_group(crit, "alert-critical", "🚨")
        else:
            _render_group(crit, "alert-critical", "🚨")

    if warn:
        if collapsible:
            with st.expander("🟠 Avertissements", expanded=True):
                _render_group(warn, "alert-warning", "⚠️")
        else:
            _render_group(warn, "alert-warning", "⚠️")

    if info:
        if collapsible:
            with st.expander("ℹ️ Informations", expanded=False):
                _render_group(info, "alert-info", "ℹ️")
        else:
            _render_group(info, "alert-info", "ℹ️")
