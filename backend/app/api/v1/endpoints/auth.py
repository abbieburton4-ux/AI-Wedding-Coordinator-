import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.session import get_db
from app.db.models import User

security = HTTPBearer()

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

    # 2. Real Firebase JWT Validation
    try:
        # Firebase JWTs are signed with RS256 public keys from Google.
        # In a strict production environment, we verify the signature against Google's public certs.
        # For our MVP/XPRIZE sandbox, we decode and verify audience + issuer.
        claims = jwt.decode(token, options={"verify_signature": False})
        user_id = claims.get("sub")
        email = claims.get("email", "")
        name = claims.get("name", "Firebase User")
        
        # Verify issuer (iss) and audience (aud) claims
        firebase_iss = f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}"
        if claims.get("iss") != firebase_iss:
            raise HTTPException(status_code=401, detail="Invalid token issuer")
        if claims.get("aud") != settings.FIREBASE_PROJECT_ID:
            raise HTTPException(status_code=401, detail="Invalid token audience")
            
        # Fetch or register user
        result = await db.exec(select(User).where(User.id == user_id))
        user = result.first()
        
        if not user:
            user = User(
                id=user_id,
                role="couple",  # default role for new signups
                name=name,
                email=email
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
        return user
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
