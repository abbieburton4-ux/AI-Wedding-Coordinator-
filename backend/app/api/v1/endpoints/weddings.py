from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.db.models import User, Wedding, BudgetLine, TimelineItem, AgentDecisionLog
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

# Schema for creating a wedding profile
from pydantic import BaseModel
from typing import Optional
from datetime import date

class WeddingCreate(BaseModel):
    guest_count_estimate: int
    budget_total: float
    region: str
    ceremony_type: str
    style_notes: Optional[str] = None
    wedding_date: Optional[date] = None
    wedding_date_start: Optional[date] = None
    wedding_date_end: Optional[date] = None


@router.post("/", response_model=Wedding, status_code=status.HTTP_201_CREATED)
async def create_wedding(
    payload: WeddingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submits a couple's wedding profile (Intake Form).
    
    Creates the Wedding record in 'intake' status. After payment succeeds,
    status shifts to 'planning' and the AI agents generate timeline & budget.
    """
    wedding = Wedding(
        couple_user_id=current_user.id,
        guest_count_estimate=payload.guest_count_estimate,
        budget_total=payload.budget_total,
        region=payload.region,
        ceremony_type=payload.ceremony_type,
        style_notes=payload.style_notes,
        wedding_date=payload.wedding_date,
        wedding_date_start=payload.wedding_date_start,
        wedding_date_end=payload.wedding_date_end,
        status="intake"
    )
    
    db.add(wedding)
    await db.commit()
    await db.refresh(wedding)
    
    return wedding


@router.get("/", response_model=List[Wedding])
async def list_weddings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists weddings for the authenticated user.
    
    * Planners see all weddings they manage (`planner_user_id == current_user.id`).
    * Couples see weddings they own (`couple_user_id == current_user.id`).
    """
    if current_user.role == "planner":
        result = await db.exec(select(Wedding).where(Wedding.planner_user_id == current_user.id))
    else:
        result = await db.exec(select(Wedding).where(Wedding.couple_user_id == current_user.id))
        
    return result.all()


@router.get("/{wedding_id}", response_model=Wedding)
async def get_wedding(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Gets details for a specific wedding, verifying user access."""
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
        
    # Access control
    if wedding.couple_user_id != current_user.id and wedding.planner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this wedding")
        
    return wedding


@router.get("/{wedding_id}/budget", response_model=List[BudgetLine])
async def get_wedding_budget(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the budget allocations for a wedding."""
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
        
    if wedding.couple_user_id != current_user.id and wedding.planner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this wedding")
        
    budget_result = await db.exec(
        select(BudgetLine).where(BudgetLine.wedding_id == wedding_id).order_by(BudgetLine.allocated_amount.desc())
    )
    return budget_result.all()


@router.get("/{wedding_id}/timeline", response_model=List[TimelineItem])
async def get_wedding_timeline(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the timeline milestones for a wedding."""
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
        
    if wedding.couple_user_id != current_user.id and wedding.planner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this wedding")
        
    timeline_result = await db.exec(
        select(TimelineItem).where(TimelineItem.wedding_id == wedding_id).order_by(TimelineItem.due_at.asc())
    )
    return timeline_result.all()


@router.get("/{wedding_id}/logs", response_model=List[AgentDecisionLog])
async def get_wedding_agent_logs(
    wedding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches the XPRIZE-critical Agent Decision Logs for a wedding."""
    result = await db.exec(select(Wedding).where(Wedding.id == wedding_id))
    wedding = result.first()
    if not wedding:
        raise HTTPException(status_code=404, detail="Wedding not found")
        
    if wedding.couple_user_id != current_user.id and wedding.planner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this wedding")
        
    logs_result = await db.exec(
        select(AgentDecisionLog).where(AgentDecisionLog.wedding_id == wedding_id).order_by(AgentDecisionLog.timestamp.desc())
    )
    return logs_result.all()
