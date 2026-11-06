import uuid
import time
import json
import logging
from functools import wraps
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import AgentDecisionLog
from app.agents.privacy import load_personal_terms, scrub
from app.config import settings

logger = logging.getLogger(__name__)

def run_agent(agent_name: str, decision_type: str):
    """Decorator to orchestrate agent runs and handle decision logs.
    
    Guarantees:
    1. A pending AgentDecisionLog row is created before execution.
    2. The agent logic executes within a nested database transaction (savepoint).
    3. If execution fails, DB mutations are rolled back, but the log is updated to 'error' and saved.
    4. Schema validation failures or guardrail blocks update the log status accordingly.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(db: AsyncSession, wedding_id: str, *args, **kwargs):
            decision_id = str(uuid.uuid4())
            start_time = time.time()
            
            # Extract orchestration headers if present
            parent_decision_id = kwargs.pop("parent_decision_id", None)
            booking_id = kwargs.pop("booking_id", None)
            user_id = kwargs.pop("user_id", None)
            trigger = kwargs.pop("trigger", "couple_action")
            
            # The log keeps no guest or party personal details (rule 3, PD-008). If they
            # can't be loaded, the row is still written, without input, and the agent's
            # own model call fails the same check and records the error.
            try:
                terms = await load_personal_terms(db, wedding_id)
            except Exception:
                await db.rollback()
                terms = None

            def safe(value, generic=True):
                return scrub(value, terms, generic) if terms is not None else value

            logged_input = (safe(kwargs) if terms is not None
                            else {"input_withheld": "personal-data check unavailable"})

            # Create pending audit log row
            log = AgentDecisionLog(
                id=decision_id,
                agent_id=agent_name,
                wedding_id=wedding_id,
                user_id=user_id,
                booking_id=booking_id,
                parent_decision_id=parent_decision_id,
                trigger=trigger,
                decision_type=decision_type,
                status="pending",
                input_payload=logged_input
            )
            db.add(log)
            await db.commit()
            
            try:
                # Execute agent logic in a nested transaction (savepoint)
                # If an exception occurs, nested transaction rolls back inner changes automatically
                async with db.begin_nested():
                    result = await func(db, wedding_id, *args, **kwargs)
                
                # Extract structured result components
                if isinstance(result, tuple) and len(result) >= 2:
                    result_dict = result[0]
                    confidence_score = result[1]
                    model_id = result[2] if len(result) > 2 else "unknown"
                    prompt_version = result[3] if len(result) > 3 else "v1.0"
                    api_calls = result[4] if len(result) > 4 else []
                    follow_ups = result[5] if len(result) > 5 else []
                    # Optional (input, output) token counts, measured from the response;
                    # agents that don't pass them leave both columns empty.
                    tokens = result[6] if len(result) > 6 else (None, None)
                else:
                    result_dict = result
                    confidence_score = result_dict.get("confidence_score")
                    model_id = "unknown"
                    prompt_version = "v1.0"
                    api_calls = []
                    follow_ups = []
                    tokens = (None, None)

                latency = int((time.time() - start_time) * 1000)
                
                # Check for custom guardrail/block signals in result
                if result_dict.get("status") == "blocked":
                    log.status = "blocked_by_guardrail"
                    log.error_kind = result_dict.get("error_kind", "guardrail_violation")
                    log.error_message = safe(result_dict.get("warning"))
                else:
                    log.status = "success"
                
                log.model_id = model_id
                log.prompt_version = prompt_version
                log.output_payload = safe(result_dict, generic=False)
                log.confidence_score = confidence_score
                log.latency_ms = latency
                log.tokens_input, log.tokens_output = tokens
                log.external_api_calls = api_calls
                log.follow_up_actions = follow_ups
                log.rationale_summary = safe(result_dict.get("rationale_summary", ""), generic=False)
                
                db.add(log)
                await db.commit()
                return result_dict
                
            except Exception as e:
                # The agent failed inside the savepoint, which leaves the session in a
                # rollback-pending state. Roll back to a clean transaction first —
                # otherwise this error-log UPDATE is silently dropped (the pending row
                # was already committed above, so rollback doesn't lose it).
                await db.rollback()
                latency = int((time.time() - start_time) * 1000)
                # Some exceptions (notably httpx timeouts) have an empty str(); fall
                # back to repr() so error_message is never blank.
                # Database and validation errors can quote the values involved.
                error_message = safe(str(e) or repr(e))
                logger.error("Agent %s failed: %s", agent_name, error_message,
                             exc_info=settings.DEVELOPMENT_MODE)

                log.status = "error"
                log.error_kind = type(e).__name__
                log.error_message = error_message
                log.latency_ms = latency

                db.add(log)
                await db.commit()
                raise e
                
        return wrapper
    return decorator
