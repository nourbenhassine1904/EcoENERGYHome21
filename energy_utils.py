# energy_utils.py
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import streamlit as st   # pour @st.cache_data

# -----------------------------
# CHEMINS DES FICHIERS
# -----------------------------
BASE_DIR = Path(__file__).parent  # dossier où se trouve ce .py

MODEL_PATH   = BASE_DIR / "models/RandomForest_house21.joblib"
META_PATH    = BASE_DIR / "models/model_meta_house21.json"
DATA_PATH    = BASE_DIR / "data/processed/House_21_1min_clean.csv"
COMPARE_PATH = BASE_DIR / "reports/model_compare_house21.csv"


# -----------------------------
# CHARGEMENT MODÈLE + DONNÉES
# -----------------------------
def load_model_and_data():
    """
    Charge le modèle RandomForest, le meta (horizon + features)
    et les données nettoyées House 21.
    """
    if not MODEL_PATH.exists() or not META_PATH.exists() or not DATA_PATH.exists():
        raise FileNotFoundError(
            "Modèle ou données introuvables. Vérifiez les dossiers `models/` et `data/processed/`."
        )

    model = joblib.load(MODEL_PATH)
    meta = json.load(open(META_PATH, "r", encoding="utf-8"))
    H = int(meta["horizon_min"])
    feat_cols = meta["features"]

    df = pd.read_csv(DATA_PATH, parse_dates=["Time"], index_col="Time").sort_index()
    return model, meta, H, feat_cols, df


# -----------------------------
# MÉTRIQUES & FEATURE ENGINEERING
# -----------------------------
def evaluate(y_true, y_pred):
    """
    Calcule les métriques de performance :
    - MAE, RMSE, MAPE, R²
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)

    mae = np.mean(np.abs(y_true - y_pred))
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    mape = np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + 1e-9))) * 100

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - ss_res / (ss_tot + 1e-9)

    return {"MAE": mae, "RMSE": rmse, "MAPE%": mape, "R2": r2}


def build_features(frame: pd.DataFrame, horizon_min: int, feat_list):
    """
    Reconstruit les features exactement comme dans le notebook 2,
    sans fuite temporelle.
    """
    df = frame.copy()
    TARGET = "Aggregate"

    # Caractéristiques temporelles
    df["hour"]       = df.index.hour
    df["dow"]        = df.index.dayofweek
    df["month"]      = df.index.month
    df["is_weekend"] = (df["dow"] >= 5).astype(int)

    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"]  = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"]  = np.cos(2 * np.pi * df["dow"] / 7)

    # Lags 1..60 de la cible
    for k in range(1, 61):
        df[f"agg_lag_{k}"] = df[TARGET].shift(k)

    # Rolling windows
    df["agg_rollmean_5"]  = df[TARGET].shift(1).rolling(5,  min_periods=3).mean()
    df["agg_rollstd_5"]   = df[TARGET].shift(1).rolling(5,  min_periods=3).std()
    df["agg_rollmean_15"] = df[TARGET].shift(1).rolling(15, min_periods=5).mean()
    df["agg_rollmean_60"] = df[TARGET].shift(1).rolling(60, min_periods=10).mean()

    # Cible à horizon H (utile pour évaluer sur une période)
    df["target"] = df[TARGET].shift(-horizon_min)

    # Garder seulement les colonnes du modèle
    df_model = df[feat_list + ["target"]].dropna()
    X = df_model[feat_list]
    y = df_model["target"]
    return X, y


def make_recos(daily_true, daily_pred):
    """
    Génère des recommandations textuelles simples à partir
    des consommations journalières (vraies vs prédites).
    """
    recos = []

    # 1) jours les plus énergivores
    if len(daily_true) > 0:
        top_days = daily_true.sort_values(ascending=False).head(3)
        txt = ", ".join([d.strftime("%d/%m") for d in top_days.index])
        recos.append(
            f"🔍 Les jours les plus énergivores sur la période sont : **{txt}**. "
            "Essayez d’identifier quels appareils sont utilisés ces jours-là."
        )

    # 2) sous / sur-prédiction moyenne
    if len(daily_true) > 0:
        diff = daily_pred - daily_true
        bias = diff.mean()
        if bias > 0:
            recos.append(
                "📈 Le modèle a tendance à **sur-estimer** légèrement la consommation. "
                "Les recommandations sont donc prudentes (plutôt conservatrices)."
            )
        else:
            recos.append(
                "📉 Le modèle a tendance à **sous-estimer** légèrement la consommation. "
                "Il reste utile pour détecter les gros pics, mais attention aux valeurs absolues."
            )

    # 3) pic max
    if len(daily_true) > 0:
        peak = daily_true.max()
        recos.append(
            f"⚡ Le maximum de consommation journalière sur la période atteint **{peak:.1f} kWh**. "
            "Pensez à décaler l’usage des gros appareils (four, lave-linge, sèche-linge) "
            "en dehors de ces jours très chargés."
        )

    if not recos:
        recos.append("Aucune recommandation spécifique pour cette période.")

    return recos


@st.cache_data
def load_model_comparison():
    """Charge le tableau de comparaison des modèles (Baseline, RandomForest, XGBoost...)."""
    try:
        df = pd.read_csv(COMPARE_PATH, index_col=0)
        return df
    except FileNotFoundError:
        return None


def style_fig(fig):
    """
    Style Plotly global + couleurs cohérentes (Vrai vs Prédit) sur toutes les pages.
    """
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.9)",
        font=dict(color="#0f172a"),
        margin=dict(l=40, r=20, t=60, b=40),
        legend_title_text=""
    )

    # 🎨 Palette globale (choisis 2 couleurs bien différentes)
    # (Tu peux changer ces 2 couleurs si tu veux)
    TRUE_COLOR = "#2563eb"   # bleu
    PRED_COLOR = "#f97316"   # orange

    color_map = {
        "Vrai": TRUE_COLOR,
        "Prédit": PRED_COLOR,
        "Vrai (kWh)": TRUE_COLOR,
        "Prédit (kWh)": PRED_COLOR,
    }

    # Appliquer la couleur selon le nom de trace
    def _apply_trace_color(trace):
        name = getattr(trace, "name", None)
        if not name or name not in color_map:
            return

        c = color_map[name]

        # Line charts
        if hasattr(trace, "line"):
            trace.line.color = c

        # Bar charts
        if getattr(trace, "type", "") == "bar":
            trace.marker.color = c

    fig.for_each_trace(_apply_trace_color)
    return fig

