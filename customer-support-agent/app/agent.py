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

import os
from typing import Any

import google.auth
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.models import Gemini
from google.adk.workflow import START, Workflow
from google.genai import types

# Setup Google Cloud / Gemini authentication
try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
except Exception:
    pass

if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# Configure Gemini model with retry options for resilience
model = Gemini(
    model="gemini-2.5-flash",
    retry_options=types.HttpRetryOptions(attempts=5),
)


def classify_query(node_input: Any) -> Event:
    """Classifies user queries into shipping-related or unrelated topics.

    Args:
        node_input: Input from the predecessor node or user message.

    Returns:
        Event containing the query and route selection ('shipping' or 'unrelated').
    """
    user_text = ""
    if isinstance(node_input, types.Content):
        user_text = " ".join([p.text for p in node_input.parts if p.text])
    else:
        user_text = str(node_input)

    text_lower = user_text.lower()
    shipping_keywords = [
        "ship",
        "track",
        "deliver",
        "return",
        "rate",
        "package",
        "parcel",
        "freight",
        "carrier",
        "post",
        "address",
        "label",
        "customs",
        "pickup",
        "weight",
        "box",
        "transit",
        "lost",
        "damaged",
        "refund",
        "exchange",
    ]

    if any(keyword in text_lower for keyword in shipping_keywords):
        return Event(output=user_text, route="shipping")
    return Event(output=user_text, route="unrelated")


# Agent node to answer shipping FAQs (rates, tracking, delivery, returns)
shipping_faq_agent = LlmAgent(
    name="shipping_faq_agent",
    model=model,
    instruction=(
        "You are an enthusiastic, super friendly, and helpful customer support representative for Global Express Logistics! 🚀📦 "
        "Your goal is to provide cheerful, clear, and actionable assistance for all shipping queries. "
        "When answering questions about shipping rates, be particularly playful and excited! 🤩 "
        "Always highlight our fantastic FREE SHIPPING threshold: FREE standard shipping on all orders over $50! 🎉 "
        "In addition to rates, gladly assist with package tracking 🚚, delivery schedules ⏰, address updates 📍, and hassle-free returns or exchanges 🔄."
    ),
)


# Agent node to politely decline unrelated questions
decline_agent = LlmAgent(
    name="decline_agent",
    model=model,
    instruction=(
        "You are a customer support representative for Global Express Logistics. "
        "Politely and professionally inform the customer that you are specialized exclusively in shipping services "
        "(such as rates, tracking, delivery, and returns). Decline to answer unrelated topics (e.g. general knowledge, "
        "coding, mathematics, trivia) and invite them to ask any shipping-related questions instead."
    ),
)


# ADK 2.0 Graph Workflow setup
root_agent = Workflow(
    name="customer_support_workflow",
    description="Customer support graph workflow that routes shipping queries to a shipping FAQ agent and politely declines unrelated queries.",
    edges=[
        (START, classify_query),
        (classify_query, {"shipping": shipping_faq_agent, "unrelated": decline_agent}),
    ],
)

app = App(
    root_agent=root_agent,
    name="customer-support-agent",
)
