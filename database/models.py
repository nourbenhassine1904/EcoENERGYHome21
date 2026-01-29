# database/models.py
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship

from database.db import Base


# ==========================
# TABLE USERS (auth réelle)
# ==========================
class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=True)

    # mot de passe hashé (JAMAIS en clair)
    password_hash = Column(String(255), nullable=False)

    # rôles simples : "admin" | "user"
    role = Column(String(20), default="user", nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 1 user -> N predictions
    predictions = relationship(
        "Prediction",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<UserDB id={self.id} username={self.username} role={self.role}>"


# ==========================
# TABLE PREDICTIONS
# ==========================
class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)

    # Période analysée
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Infos modèle
    horizon = Column(Integer, nullable=True)

    # Résultats (énergie + métriques)
    total_kwh = Column(Float, nullable=True)
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)
    r2 = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ✅ Qui a lancé la prédiction ?
    # nullable=True => anciennes prédictions (avant ajout users) peuvent rester NULL
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    user = relationship("UserDB", back_populates="predictions")

    # Relations
    alerts = relationship(
        "AlertDB",
        back_populates="prediction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recommendations = relationship(
        "RecommendationDB",
        back_populates="prediction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Prediction id={self.id} start={self.start_date} end={self.end_date} user_id={self.user_id}>"


# ==========================
# TABLE ALERTS
# ==========================
class AlertDB(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)

    level = Column(String(20), nullable=False)  # "critical" | "warning" | "info"
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # (optionnel) détails de métrique
    metric = Column(String(80), nullable=True)
    value = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction = relationship("Prediction", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<AlertDB id={self.id} level={self.level} prediction_id={self.prediction_id}>"


# ==========================
# TABLE RECOMMENDATIONS
# ==========================
class RecommendationDB(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)

    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)  # ex: "general", "weather", "tariff"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    prediction_id = Column(Integer, ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False, index=True)
    prediction = relationship("Prediction", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<RecommendationDB id={self.id} category={self.category} prediction_id={self.prediction_id}>"


# (Optionnel) Index utile si vous filtrez souvent par dates + user
Index("ix_predictions_user_created", Prediction.user_id, Prediction.created_at)
