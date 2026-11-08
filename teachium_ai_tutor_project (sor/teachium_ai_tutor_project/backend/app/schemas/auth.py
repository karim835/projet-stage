"""Schémas Pydantic pour l'authentification et la gestion des comptes."""

from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["learner", "trainer", "administrator"]
CourseCategory = Literal["Python", "Data", "Web", "Management", "Communication"]


class RegisterInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, description="8 caractères minimum")
    # L'inscription publique ne crée jamais de compte privilégié. Les rôles
    # formateur/administrateur sont gérés uniquement depuis l'espace admin.
    role: Literal["learner"] = "learner"
    course_category: CourseCategory = Field(..., description="Filière principale de l'apprenant")

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Le nom doit contenir au moins 2 caractères.")
        return cleaned

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe est trop long (72 octets maximum).")
        if value.strip() != value:
            raise ValueError("Le mot de passe ne doit pas commencer ou finir par un espace.")
        return value


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: dt.datetime


class UserWithLearner(UserPublic):
    learner_id: Optional[int] = None
    student_id: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserWithLearner


class PasswordChangeInput(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=200)
    new_password: str = Field(..., min_length=8, max_length=72)


class UserUpdateInput(BaseModel):
    """Champs modifiables par un administrateur."""

    name: Optional[str] = Field(None, min_length=2, max_length=120)
    role: Optional[Role] = None
    is_active: Optional[bool] = None
