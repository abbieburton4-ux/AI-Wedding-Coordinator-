from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import User, Wedding, AgentDecisionLog
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/")
async def get_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Calculates operational metrics, telemetry, and funnel statistics for the system."""
    if current_user.role not in ("admin", "planner"):
        raise HTTPException(status_code=403, detail="Not authorized to access operational dashboard metrics.")
        
    # Get total weddings
    total_w_res = await db.exec(select(func.count(Wedding.id)))
    total_weddings = total_w_res.one()
    
    # Get total decisions executed
    total_d_res = await db.exec(select(func.count(AgentDecisionLog.id)))
    total_decisions = total_d_res.one()
    
    # Get total blocked by guardrails
    total_b_res = await db.exec(select(func.count(AgentDecisionLog.id)).where(AgentDecisionLog.status == "blocked_by_guardrail"))
    total_blocked = total_b_res.one()
    
    # Get average confidence score
    avg_c_res = await db.exec(select(func.avg(AgentDecisionLog.confidence_score)).where(AgentDecisionLog.confidence_score != None))
    avg_confidence = avg_c_res.one() or 0.0
    
    # Compute conversion funnels
    intake_res = await db.exec(select(func.count(Wedding.id)).where(Wedding.status == "intake"))
    planning_res = await db.exec(select(func.count(Wedding.id)).where(Wedding.status == "planning"))
    booked_res = await db.exec(select(func.count(Wedding.id)).where(Wedding.status == "booked"))
    
    n_intake = intake_res.one()
    n_planning = planning_res.one()
    n_booked = booked_res.one()
    
    # Conversions
    total_funnel = n_intake + n_planning + n_booked
    intake_to_planning = (n_planning + n_booked) / total_funnel if total_funnel > 0 else 0.0
    planning_to_booked = n_booked / (n_planning + n_booked) if (n_planning + n_booked) > 0 else 0.0
    
    return {
        "total_weddings": total_weddings,
        "total_decisions_executed": total_decisions,
        "total_blocked_by_guardrails": total_blocked,
        "avg_confidence_score": round(float(avg_confidence), 2),
        "conversions": {
            "intake_to_planning": round(intake_to_planning, 2),
            "planning_to_booked": round(planning_to_booked, 2)
        }
    }
