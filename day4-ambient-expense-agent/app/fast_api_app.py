# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import os
import base64
import json
import logging
from collections.abc import AsyncIterator

import google.auth
from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.cloud import logging as google_cloud_logging

# Configure standard console logging
logging.basicConfig(level=logging.INFO)


from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

load_dotenv()
setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=False,
    lifespan=lifespan,
)
app.title = "day4-ambient-expense-agent"
app.description = "API for interacting with the Agent day4-ambient-expense-agent"


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logging.info(f"Feedback received: {feedback.model_dump()}")
    return {"status": "success"}


@app.post("/pubsub")
async def pubsub_handler(request: Request) -> dict:
    """Handle Pub/Sub push messages, normalize subscription name, and invoke the ADK runner.

    Expected Pub/Sub push request payload:
    {
        "message": {
            "data": "<base64-encoded JSON>",
            "subscription": "projects/.../subscriptions/<name>"
        }
    }
    """
    payload = await request.json()
    message = payload.get("message", {})
    data_b64 = message.get("data")
    subscription = message.get("subscription", "")
    sub_name = subscription.split('/')[-1] if subscription else "unknown"

    if not data_b64:
        logging.warning("Pub/Sub message missing data payload")
        return {"status": "error", "reason": "no data"}
    try:
        data_bytes = base64.b64decode(data_b64)
        event_payload = json.loads(data_bytes.decode())
    except Exception as e:
        logging.exception("Failed to decode Pub/Sub payload")
        return {"status": "error", "reason": str(e)}

    # Run the agent using the ADK runner attached to app state
    runner: Runner = app.state.runner
    try:
        result = await runner.run_async(event_payload)
        logging.info(f"Processed Pub/Sub event from {sub_name}")
        return {"status": "processed", "subscription": sub_name, "result": result}
    except Exception as e:
        logging.exception("Runner execution failed for Pub/Sub event")
        return {"status": "error", "reason": str(e)}

# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
