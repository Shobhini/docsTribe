import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import User
from app.auth import hash_password, verify_password, create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new user account.
    Returns a JWT immediately so the user is logged in after registering.
    """
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    user = User(
        id=str(uuid.uuid4()),
        email=body.email,
        name=body.name.strip(),
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()

    logger.info("New user registered email=%s name=%s", body.email, body.name)
    token = create_access_token(user.id, user.email, user.name)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticate with email + password.
    Uses OAuth2PasswordRequestForm so this works with FastAPI's Swagger UI
    'Authorize' button directly (username field = email).
    Returns a JWT on success.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Failed login attempt email=%s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User logged in email=%s", form_data.username)
    token = create_access_token(user.id, user.email, user.name)
    return TokenResponse(access_token=token)
