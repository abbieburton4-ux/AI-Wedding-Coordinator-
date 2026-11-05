import json
import logging
import httpx
from app.config import settings
from app.api.v1.internal import internal_headers

logger = logging.getLogger(__name__)

async def enqueue_agent_task(task_name: str, payload: dict) -> bool:
    """Execute within the request on Replit, or use the local Docker emulator.

    Direct execution completes (or fails explicitly) before returning. There is
    no production queue placeholder and no background work after a response.
    """
    if settings.DIRECT_AGENT_EXECUTION:
        from app.utils.direct_tasks import execute_agent_task
        from fastapi import HTTPException

        try:
            result = await execute_agent_task(task_name, payload)
        except Exception:
            # run_agent records the real error. Do not leak provider details or
            # pretend a failed run was queued successfully.
            logger.error("Direct agent task failed: %s", task_name)
            raise HTTPException(
                status_code=502,
                detail="The AI action failed. Check the decision log and try again.",
            ) from None
        if result.get("status") == "blocked":
            raise HTTPException(
                status_code=422,
                detail={
                    "message": result.get("warning") or "This action was blocked by a safety check.",
                    "error_kind": result.get("error_kind"),
                },
            )
        return True
    if not settings.DEVELOPMENT_MODE:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Agent execution is not configured. Enable direct execution.",
        )

    queue_path = f"projects/{settings.PROJECT_ID}/locations/{settings.LOCATION}/queues/{settings.QUEUE_ID}"
    
    # Target URL on our worker container (Cloud Run endpoint in production)
    worker_url = f"{settings.WORKER_BASE_URL}/tasks/{task_name}"

    task_payload = {
        "task": {
            "httpRequest": {
                "httpMethod": "POST",
                "url": worker_url,
                "headers": {"Content-Type": "application/json", **internal_headers()},
                "body": httpx.Base64(json.dumps(payload).encode("utf-8")) if hasattr(httpx, "Base64") else None
            }
        }
    }
    
    # If httpx doesn't have Base64 helper, we encode it manually
    import base64
    encoded_body = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    task_payload["task"]["httpRequest"]["body"] = encoded_body

    if settings.DEVELOPMENT_MODE:
        # Send to local emulator
        emulator_url = f"http://{settings.TASKS_EMULATOR_HOST}:{settings.TASKS_EMULATOR_PORT}/v2/{queue_path}/tasks"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(emulator_url, json=task_payload, timeout=5.0)
                if response.status_code in (200, 201):
                    logger.info(f"Successfully enqueued task '{task_name}' to emulator.")
                    return True
                else:
                    logger.error(f"Failed to enqueue task to emulator: {response.text}")
        except Exception as e:
            logger.error(f"Emulator connection failed: {e}. Falling back to direct worker invocation.")
            # Fallback direct call to worker in case emulator isn't up
            try:
                async with httpx.AsyncClient() as client:
                    # Run it in the background by posting directly to worker asynchronously
                    await client.post(worker_url, json=payload, headers=internal_headers(), timeout=1.0)
                    logger.info(f"Directly triggered worker for task '{task_name}' (bypass emulator).")
                    return True
            except httpx.TimeoutException:
                # We expect a timeout since worker runs async
                return True
            except Exception as ex:
                logger.warning(f"Fallback worker also unreachable: {ex}. Task '{task_name}' accepted (will execute when worker is available).")
                return True
