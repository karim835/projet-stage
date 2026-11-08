"""Point d'entrée de l'API TEACHIUM AI Tutor.

    React (Vite)  ──HTTP/REST──▶  FastAPI  ──▶  Services IA (K-Means, Decision Tree)
                                     │
                                     └──────▶  PostgreSQL hébergé sur Neon
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import admin, auth, courses, dashboard, learners, ml, quizzes, tutor
from app.core.config import settings
from app.db.database import check_connection
from app.schemas.tutor import HealthResponse
from app.services.profile_service import artifacts_status
from app.services.tutor_service import get_engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("teachium")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Démarrage de %s v%s", settings.app_name, settings.app_version)
    if settings.database_configured:
        ok, message = check_connection()
        logger.info("Base de données : %s", message)
        if not ok:
            logger.warning(
                "L'API démarre malgré tout : les routes ML sans état restent utilisables, "
                "les routes nécessitant la base renverront une erreur 503 explicite."
            )
    else:
        logger.warning(
            "DATABASE_URL absente. Copiez backend/.env.example vers backend/.env et "
            "renseignez la chaîne de connexion Neon."
        )
    if not settings.jwt_secret:
        logger.warning(
            "JWT_SECRET absent : une clé éphémère est utilisée, toutes les sessions "
            "seront invalidées au redémarrage."
        )
    status_ml = artifacts_status()
    logger.info(
        "Modèles ML — classificateur:%s clustering:%s scaler:%s",
        status_ml["profile_classifier"],
        status_ml["cluster_model"],
        status_ml["scaler"],
    )
    yield
    logger.info("Arrêt de l'API TEACHIUM AI Tutor")


app = FastAPI(
    title=settings.app_name,
    description=(
        "API REST du système de tutorat intelligent TEACHIUM.\n\n"
        "**Chaîne de traitement** : données apprenant → prétraitement → K-Means + Arbre de "
        "décision → profil pédagogique → moteur de recommandation → explication de l'AI Tutor.\n\n"
        "Les données sont persistées dans PostgreSQL hébergé sur **Neon**."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Gestion d'erreurs : jamais de trace Python renvoyée au client -----------


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Transforme les erreurs Pydantic en messages lisibles côté interface."""
    details = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error.get("loc", []) if part not in ("body", "query", "path"))
        details.append(f"{field or 'requête'} : {error.get('msg', 'valeur invalide')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Données invalides. " + " ; ".join(details)},
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_handler(request: Request, exc: SQLAlchemyError):
    logger.error("Erreur base de données sur %s : %s", request.url.path, exc.__class__.__name__)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": (
                "La base de données est momentanément indisponible. "
                "Vérifiez la variable DATABASE_URL (Neon) et votre connexion Internet."
            )
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Erreur non gérée sur %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Une erreur interne est survenue. L'équipe technique a été notifiée."},
    )


# --- Routes de base ---------------------------------------------------------


@app.get("/", tags=["Système"], summary="Racine de l'API")
def root():
    return {
        "message": "TEACHIUM AI Tutor API is running",
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Système"], summary="État de santé du système")
def health():
    db_ok, db_message = check_connection() if settings.database_configured else (False, "DATABASE_URL absente.")
    ml_status = artifacts_status()
    models_ok = ml_status["profile_classifier"] and ml_status["cluster_model"] and ml_status["scaler"]
    return HealthResponse(
        status="ok" if (db_ok and models_ok) else "degraded",
        database={
            "configured": settings.database_configured,
            "connected": db_ok,
            "target": settings.safe_database_target(),
            "message": db_message,
        },
        models={**ml_status, "all_loaded": models_ok},
        tutor_engine=get_engine().name,
        version=settings.app_version,
    )


# --- Routeurs ---------------------------------------------------------------

app.include_router(auth.router)
app.include_router(learners.router)
app.include_router(quizzes.router)
app.include_router(courses.router)
app.include_router(tutor.router)
app.include_router(ml.router)
app.include_router(dashboard.router)
app.include_router(admin.router)
