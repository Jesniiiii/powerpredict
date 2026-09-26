"""
routers/auth.py

Registration, login, and current-user endpoints. Login uses FastAPI's
standard OAuth2PasswordRequestForm (form field is called "username" even
though we're using email - that's the OAuth2 spec's naming, not a mistake).

Expected location: src/api/routers/auth.py
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from src.api.database.mongo_client import get_user_by_email, create_user
from src.api.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = "viewer"  # "admin" | "engineer" | "viewer" - expand as needed


@router.post("/register")
def register(payload: RegisterRequest):
    if get_user_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed = hash_password(payload.password)
    user_id = create_user(payload.email, hashed, role=payload.role, full_name=payload.full_name)
    return {"id": user_id, "email": payload.email, "role": payload.role}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # OAuth2PasswordRequestForm names the field "username" per spec - we treat it as email
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token({"sub": user["email"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "role": current_user["role"],
        "full_name": current_user.get("full_name"),
    }