import jwt
from functools import lru_cache
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.db.session import get_db
from app.db.models import User, WeddingMember
from app.api.v1.access import bootstrap_emails, link_memberships

security = HTTPBearer()
router = APIRouter()

# Google's public JWKS for Firebase ID tokens (RS256). PyJWKClient caches the
# keys; the network fetch only happens for real Firebase tokens, so local dev
# (which uses mock- tokens) never touches the network.
FIREBASE_JWKS_URL = (
    "https://www.googleapis.com/service_accounts/v1/jwks/"
    "securetoken@system.gserviceaccount.com"
)


@lru_cache(maxsize=1)
def _firebase_jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(FIREBASE_JWKS_URL)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """FastAPI dependency to authenticate requests.
    
    In development mode with ALLOW_MOCK_AUTH enabled, passing a token starting
    with 'mock-' (e.g. 'mock-couple_1') bypasses Firebase verification and returns
    or creates the corresponding user in the database.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization Header",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    token = credentials.credentials
    
    # 1. Local Development Mock Bypass
    if settings.DEVELOPMENT_MODE and settings.ALLOW_MOCK_AUTH and token.startswith("mock-"):
        user_id = token.replace("mock-", "")
        
        # Look up user in DB
        result = await db.exec(select(User).where(User.id == user_id))
        user = result.first()
        
        if not user:
            # Auto-create mock user to prevent FK violations during debug
            role = "planner" if "planner" in user_id else "couple"
            user = User(
                id=user_id,
                role=role,
                name=f"Mock {role.capitalize()} ({user_id})",
                email=f"{user_id}@mock.venueflow.ie",
                phone="+353870000000"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
        return user

    # 2. HS256 tokens are ours (Firebase tokens are RS256), so they never fall through
    #    to Firebase. Accepted only with a configured JWT_SECRET, a signature that
    #    matches, an expiry, and an existing user; the role comes from the database.
    try:
        alg = jwt.get_unverified_header(token).get("alg")
    except jwt.PyJWTError:
        raise _unauthorized()
    if alg == "HS256":
        if not settings.JWT_SECRET:
            raise _unauthorized()
        try:
            claims = jwt.decode(
                token, settings.JWT_SECRET, algorithms=["HS256"],
                options={"require": ["exp", "sub"]},
            )
        except jwt.PyJWTError:
            raise _unauthorized()
        result = await db.exec(select(User).where(User.id == claims["sub"]))
        user = result.first()
        if not user:
            raise _unauthorized()
        return user

    # 3. Firebase ID token (RS256), verified against Google's public keys for the
    #    couple's own project. With no project configured, Firebase sign-in is off.
    if not settings.FIREBASE_PROJECT_ID:
        raise _unauthorized()
    try:
        firebase_iss = f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}"
        signing_key = _firebase_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.FIREBASE_PROJECT_ID,
            issuer=firebase_iss,
        )
    except Exception:
        raise _unauthorized()

    user_id = claims.get("sub")
    if not user_id:
        raise _unauthorized()
    email = (claims.get("email") or "").strip().lower()
    email_verified = bool(claims.get("email_verified"))
    name = claims.get("name") or email or "Firebase User"

    # No self sign-up (PD-002): a new account is created only for a verified
    # email that's on a wedding's access list or in ACCESS_BOOTSTRAP_EMAILS.
    result = await db.exec(select(User).where(User.id == user_id))
    user = result.first()
    if not user:
        # Verified first, so an unconfirmed account can't probe who is on the list.
        if not email_verified:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=EMAIL_NOT_VERIFIED)
        if not await _email_is_allowed(db, email):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_ON_LIST)
        user = User(id=user_id, role="couple", name=name, email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if email_verified and await link_memberships(db, user, email):
        await db.commit()

    return user


NOT_ON_LIST = (
    "This account isn't on the wedding's access list yet. "
    "Ask the couple to add you, then sign in again."
)
EMAIL_NOT_VERIFIED = (
    "This email address hasn't been confirmed yet. "
    "Please sign in with Google using the address the couple added."
)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired sign-in. Please sign in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _email_is_allowed(db: AsyncSession, email: str) -> bool:
    if not email:
        return False
    if email in bootstrap_emails():
        return True
    result = await db.exec(select(WeddingMember.id).where(WeddingMember.email == email))
    return result.first() is not None


@router.get("/me")
async def read_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile + role.

    The frontend calls this right after sign-in to decide which workspace to route
    to (couple -> /wedding, planner -> /planner, admin -> /admin).
    """
    return {
        "id": current_user.id,
        "role": current_user.role,
        "name": current_user.name,
        "email": current_user.email,
    }


class PlannerLoginPayload(BaseModel):
    email: str


@router.post("/planner")
async def planner_login(
    payload: PlannerLoginPayload,
    db: AsyncSession = Depends(get_db)
):
    """Legacy planner login for local development only.

    It has no password, so it exists only when mock sign-in is on.
    """
    if not (settings.DEVELOPMENT_MODE and settings.ALLOW_MOCK_AUTH):
        raise HTTPException(status_code=404, detail="Not found")
    result = await db.exec(select(User).where(User.email == payload.email))
    user = result.first()
    
    if not user:
        if settings.DEVELOPMENT_MODE and settings.ALLOW_MOCK_AUTH:
            # Auto-onboard the pilot planner to streamline distribution
            user_id = payload.email.split("@")[0] + "_planner"
            user = User(
                id=user_id,
                role="planner",
                name=f"Pilot Planner ({payload.email.split('@')[0]})",
                email=payload.email,
                phone="+353871111111"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            raise HTTPException(status_code=404, detail="Planner profile not found. Contact administration.")
            
    if user.role != "planner":
        raise HTTPException(status_code=403, detail="Access denied. User role is not planner.")
    
    token = f"mock-{user.id}"

    return {
        "token": token,
        "role": "planner",
        "name": user.name
    }
