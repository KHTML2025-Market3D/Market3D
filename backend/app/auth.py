# backend/app/auth.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from google.oauth2 import id_token
from google.auth.transport import requests

from .database import SessionLocal
from .models import User
from .config import settings

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_google_id_token(token: str) -> dict:
    try:
        info = id_token.verify_oauth2_token(
            token, requests.Request(), settings.google_client_id
        )
        return info
    except Exception:
        raise HTTPException(status_code=401, detail="invalid_google_token")

def get_current_user_google(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_authorization")
    token = authorization.split(" ", 1)[1]
    info = verify_google_id_token(token)
    sub = info.get("sub")
    user = db.query(User).filter(User.google_sub == sub).first()
    if not user:
        raise HTTPException(status_code=401, detail="user_not_registered")
    return user
