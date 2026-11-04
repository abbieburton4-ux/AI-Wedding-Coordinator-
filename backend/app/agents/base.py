import os
import hashlib
from google import genai
from app.config import settings

def get_client() -> genai.Client:
    """Returns the Google GenAI SDK client."""
    key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY is not set in environment or config.")
    # NOTE: google-genai's http_options timeout is in MILLISECONDS. The original
    # 30.0 meant 30ms (every call ConnectTimeout/ReadTimeout). 90000 = 90s: the
    # gemini-2.5-pro intake_planner generation (full budget + timeline) measures
    # ~36s, so 30s was too tight and surfaced as 504 DEADLINE_EXCEEDED.
    return genai.Client(api_key=key, http_options={"timeout": 90000})

# Pro gives the best planning/reasoning quality, but the Gemini *free tier* has
# a hard quota of 0 for gemini-2.5-pro — every call 429s with RESOURCE_EXHAUSTED.
# So default to Flash (which has free-tier quota and runs the whole flow), and
# let a paid key opt back into Pro via env:
#   GEMINI_PLANNING_MODEL=gemini-2.5-pro
PLANNING_MODEL = os.environ.get("GEMINI_PLANNING_MODEL", "gemini-2.5-flash")
FAST_MODEL = os.environ.get("GEMINI_FAST_MODEL", "gemini-2.5-flash")

def model_for(agent_name: str) -> str:
    """Resolves the correct model for each agent.

    Planning/matching agents use PLANNING_MODEL; extraction uses FAST_MODEL.
    Both default to Flash so the stack works on a free-tier key out of the box.
    """
    if agent_name in ("intake_planner", "venue_matcher", "supplier_matcher"):
        return PLANNING_MODEL
    return FAST_MODEL

def get_prompt_version(system_instruction: str) -> str:
    """Generates a prompt version hash from the instruction content."""
    sha = hashlib.sha256(system_instruction.encode("utf-8")).hexdigest()[:8]
    return f"v1.0-{sha}"
