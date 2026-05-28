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
from app.db.models import User

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

    # 2. HS256 JWT validation using JWT_SECRET
    jwt_secret = settings.JWT_SECRET or "dev-jwt-secret-key-change-me-in-production"
    try:
        claims = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = claims.get("sub")
        if user_id:
            result = await db.exec(select(User).where(User.id == user_id))
            user = result.first()
            
            if not user:
                role = claims.get("role", "couple")
                user = User(
                    id=user_id,
                    role=role,
                    name=claims.get("name", f"Pilot {role.capitalize()} ({user_id})"),
                    email=claims.get("email", f"{user_id}@venueflow.ie"),
                    phone="+353870000000"
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                
            return user
    except jwt.PyJWTError:
        # Not a valid HS256 JWT, fallback to Firebase validation
        pass

    # 3. Real Firebase JWT Validation — RS256 signature verified against Google's
    #    public keys (not just decoded). audience + issuer are enforced by jwt.decode.
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
        user_id = claims.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing subject")
        email = claims.get("email", "")
        name = claims.get("name") or email or "Firebase User"

        # Fetch or register user (new Firebase sign-ups default to the couple role)
        result = await db.exec(select(User).where(User.id == user_id))
        user = result.first()
        if not user:
            user = User(id=user_id, role="couple", name=name, email=email)
            db.add(user)
            await db.commit()
            await db.refresh(user)

        return user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
    """Minimal planner login endpoint returning long-lived bearer tokens for developer testing."""
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
    
    # Return a fast token
    if settings.ALLOW_MOCK_AUTH:
        token = f"mock-{user.id}"
    else:
        # Generate long-lived HS256 signed JWT for pilot planners
        import datetime
        jwt_secret = settings.JWT_SECRET or "dev-jwt-secret-key-change-me-in-production"
        token = jwt.encode(
            {
                "sub": user.id,
                "email": user.email,
                "role": user.role,
                "name": user.name,
                "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
            },
            jwt_secret,
            algorithm="HS256"
        )
        
    return {
        "token": token,
        "role": "planner",
        "name": user.name
    }
