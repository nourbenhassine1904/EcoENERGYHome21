# database/crud.py
from __future__ import annotations

from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from passlib.context import CryptContext

from database.db import SessionLocal
from database.models import UserDB, Prediction, AlertDB, RecommendationDB


# =========================================================
# CONFIG PASSWORD HASH
# =========================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =========================================================
# Helpers
# =========================================================
def _get_db() -> Session:
    return SessionLocal()


def _filter_model_kwargs(model_cls, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Garde uniquement les clés présentes dans les colonnes du modèle.
    Utile si on ajoute des colonnes plus tard (user_id, etc.).
    """
    if not hasattr(model_cls, "__table__"):
        return data
    allowed = set(model_cls.__table__.columns.keys())
    return {k: v for k, v in data.items() if k in allowed}


# =========================================================
# USERS (Auth réelle)
# =========================================================
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_username(username: str) -> Optional[UserDB]:
    db = _get_db()
    try:
        return db.query(UserDB).filter(UserDB.username == username).first()
    finally:
        db.close()


def get_user_by_email(email: str) -> Optional[UserDB]:
    db = _get_db()
    try:
        return db.query(UserDB).filter(UserDB.email == email).first()
    finally:
        db.close()


def get_user_by_identifier(identifier: str) -> Optional[UserDB]:
    """
    identifier = username OU email
    """
    db = _get_db()
    try:
        return (
            db.query(UserDB)
            .filter(or_(UserDB.username == identifier, UserDB.email == identifier))
            .first()
        )
    finally:
        db.close()


def create_user(
    username: str,
    password: str,
    role: str = "user",
    email: Optional[str] = None,
    is_active: bool = True,
) -> UserDB:
    db = _get_db()
    try:
        # check username unique
        if db.query(UserDB).filter(UserDB.username == username).first():
            raise ValueError("Nom d'utilisateur déjà utilisé.")

        # check email unique (si fourni)
        if email and db.query(UserDB).filter(UserDB.email == email).first():
            raise ValueError("Email déjà utilisé.")

        user = UserDB(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=(role or "user").lower(),
            is_active=is_active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def authenticate_user(identifier: str, password: str) -> Optional[UserDB]:
    user = get_user_by_identifier(identifier)
    if user is None:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def list_users(limit: int = 50) -> List[UserDB]:
    db = _get_db()
    try:
        return db.query(UserDB).order_by(desc(UserDB.created_at)).limit(limit).all()
    finally:
        db.close()


def set_user_active(user_id: int, is_active: bool) -> None:
    db = _get_db()
    try:
        u = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not u:
            return
        u.is_active = bool(is_active)
        db.commit()
    finally:
        db.close()


# =========================================================
# CREATE (Predictions / Alerts / Recos)
# =========================================================
def save_prediction(data: Dict[str, Any]) -> Prediction:
    db = _get_db()
    try:
        data_clean = _filter_model_kwargs(Prediction, data)
        pred = Prediction(**data_clean)
        db.add(pred)
        db.commit()
        db.refresh(pred)
        return pred
    finally:
        db.close()


def save_alert(
    prediction_id: int,
    level: str,
    title: str,
    message: str,
    metric: Optional[str] = None,
    value: Optional[float] = None,
) -> AlertDB:
    db = _get_db()
    try:
        alert = AlertDB(
            prediction_id=prediction_id,
            level=level,
            title=title,
            message=message,
            metric=metric,
            value=value,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    finally:
        db.close()


def save_recommendation(
    prediction_id: int,
    content: str,
    category: str = "general",
) -> RecommendationDB:
    db = _get_db()
    try:
        rec = RecommendationDB(
            prediction_id=prediction_id,
            content=content,
            category=category,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec
    finally:
        db.close()


# =========================================================
# READ (Historique)
# =========================================================
def list_predictions(limit: int = 10) -> List[Prediction]:
    db = _get_db()
    try:
        return (
            db.query(Prediction)
            .order_by(desc(Prediction.created_at))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def list_predictions_for_user(user_id: int, limit: int = 50) -> List[Prediction]:
    db = _get_db()
    try:
        return (
            db.query(Prediction)
            .filter(Prediction.user_id == user_id)
            .order_by(desc(Prediction.created_at))
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def get_prediction(prediction_id: int) -> Optional[Prediction]:
    db = _get_db()
    try:
        return db.query(Prediction).filter(Prediction.id == prediction_id).first()
    finally:
        db.close()


def get_alerts_for_prediction(prediction_id: int) -> List[AlertDB]:
    db = _get_db()
    try:
        return (
            db.query(AlertDB)
            .filter(AlertDB.prediction_id == prediction_id)
            .order_by(desc(AlertDB.created_at))
            .all()
        )
    finally:
        db.close()


def get_recommendations_for_prediction(prediction_id: int) -> List[RecommendationDB]:
    db = _get_db()
    try:
        return (
            db.query(RecommendationDB)
            .filter(RecommendationDB.prediction_id == prediction_id)
            .order_by(desc(RecommendationDB.created_at))
            .all()
        )
    finally:
        db.close()


def latest_prediction() -> Optional[Prediction]:
    db = _get_db()
    try:
        return db.query(Prediction).order_by(desc(Prediction.created_at)).first()
    finally:
        db.close()


# =========================================================
# EXPORTS
# =========================================================
def export_predictions_dataframe(limit: int = 200):
    import pandas as pd

    db = _get_db()
    try:
        preds = (
            db.query(Prediction)
            .order_by(desc(Prediction.created_at))
            .limit(limit)
            .all()
        )
        rows = []
        for p in preds:
            rows.append(
                {
                    "id": p.id,
                    "created_at": p.created_at,
                    "start_date": p.start_date,
                    "end_date": p.end_date,
                    "horizon": p.horizon,
                    "total_kwh": p.total_kwh,
                    "mae": p.mae,
                    "rmse": p.rmse,
                    "mape": p.mape,
                    "r2": p.r2,
                    "user_id": getattr(p, "user_id", None),
                }
            )
        return pd.DataFrame(rows)
    finally:
        db.close()


def export_prediction_details(prediction_id: int) -> dict:
    db = _get_db()
    try:
        p = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not p:
            return {}

        alerts = (
            db.query(AlertDB)
            .filter(AlertDB.prediction_id == prediction_id)
            .order_by(desc(AlertDB.created_at))
            .all()
        )
        recos = (
            db.query(RecommendationDB)
            .filter(RecommendationDB.prediction_id == prediction_id)
            .order_by(desc(RecommendationDB.created_at))
            .all()
        )

        return {
            "prediction": {
                "id": p.id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
                "horizon": p.horizon,
                "total_kwh": p.total_kwh,
                "mae": p.mae,
                "rmse": p.rmse,
                "mape": p.mape,
                "r2": p.r2,
                "user_id": getattr(p, "user_id", None),
            },
            "alerts": [
                {
                    "id": a.id,
                    "level": a.level,
                    "title": a.title,
                    "message": a.message,
                    "metric": getattr(a, "metric", None),
                    "value": getattr(a, "value", None),
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in alerts
            ],
            "recommendations": [
                {
                    "id": r.id,
                    "content": r.content,
                    "category": r.category,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in recos
            ],
        }
    finally:
        db.close()
