"""Expense approval agent workflow (ADK 2.0 Graph API).

The workflow processes a Pub/Sub‑style JSON payload, extracts the expense fields,
applies a $100 threshold, runs a LLM risk‑assessment when needed, pauses for a
human‑in‑the‑loop decision, and finally records the outcome.
"""

import json
import base64
from typing import Dict, Any
import re
from google.adk.workflow import Graph, FunctionNode, Edge, RequestInput
from google.adk import Agent
from google.adk.tools import llm

# ---------------------------------------------------------------------------
# Configuration – keep in sync with config.py
# ---------------------------------------------------------------------------
THRESHOLD = 100  # dollars
MODEL = "gemini-3.1-flash-lite"

# ---------------------------------------------------------------------------
# Helper functions (each will become a FunctionNode)
# ---------------------------------------------------------------------------
def parse_event(event: str) -> Dict[str, Any]:
    """Parse the incoming Pub/Sub event.

    The event may be a raw JSON string (local testing) or a Pub/Sub envelope
    where the payload is base64‑encoded under ``event[data]``.
    """
    try:
        payload = json.loads(event)
    except json.JSONDecodeError:
        raise ValueError("Event is not valid JSON")

    if isinstance(payload, dict) and "data" in payload:
        decoded = base64.b64decode(payload["data"]).decode("utf-8")
        expense = json.loads(decoded)
    else:
        expense = payload

    required = ["amount", "submitter", "category", "description", "date"]
    for k in required:
        if k not in expense:
            raise KeyError(f"Missing required expense field: {k}")
    return expense
def security_check(expense: Dict[str, Any]) -> Dict[str, Any]:
    """Redact PII and detect prompt‑injection.

    • SSNs (###‑##‑####) → "[REDACTED_SSN]"
    • Credit‑card numbers (13‑16 digits, spaces/dashes) → "[REDACTED_CC]"
    • Injection keywords (auto approve, bypass, ignore rules, …) set
      ``_injection_detected = True`` and route straight to human review.

    The function mutates ``expense`` in‑place, adds two metadata keys:
        ``_redacted_categories`` – list of redacted types
        ``_injection_detected``   – bool flag used downstream
    """
    description: str = expense.get("description", "")
    redacted: list[str] = []

    # SSN patterns
    ssn_regex = re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b\d{9}\b")
    if ssn_regex.search(description):
        description = ssn_regex.sub("[REDACTED_SSN]", description)
        redacted.append("ssn")

    # Credit‑card patterns (13‑16 digits, ignore spaces/dashes)
    cc_regex = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    if cc_regex.search(description):
        description = cc_regex.sub("[REDACTED_CC]", description)
        redacted.append("credit_card")

    # Simple injection‑keyword heuristic
    injection_keywords = ["auto approve", "bypass", "ignore rules", "override", "approve instantly"]
    injection_detected = any(kw.lower() in description.lower() for kw in injection_keywords)

    expense["description"] = description
    expense["_redacted_categories"] = redacted
    expense["_injection_detected"] = injection_detected
    return expense
def auto_approve(expense: Dict[str, Any]) -> Dict[str, Any]:
    """Auto‑approve path for expenses below the threshold.

    Returns a result dict that downstream nodes can recognise as "approved".
    """
    return {"status": "approved", "method": "auto", "expense": expense}

def risk_assess(expense: Dict[str, Any]) -> str:
    """Call the LLM to produce a risk judgement.

    The LLM receives a concise prompt describing the expense and must answer
    with either ``"high"`` or ``"low"`` risk.  The raw response string is returned.
    """
    prompt = (
        f"You are a finance risk analyst. Evaluate the following expense and "
        f"answer with ONLY the word high or low to indicate risk level.\n"
        f"Amount: ${expense[amount]:.2f}\n"
        f"Submitter: {expense[submitter]}\n"
        f"Category: {expense[category]}\n"
        f"Description: {expense[description]}\n"
        f"Date: {expense[date]}"
    )
    response = llm.generate(prompt, model=MODEL)
    return response.strip().lower()

def human_review(expense: Dict[str, Any], risk: str) -> str:
    """Placeholder – actual input will be supplied by a RequestInput node.
    """
    raise RuntimeError("human_review should be provided by RequestInput")

def record_outcome(expense: Dict[str, Any], decision: str) -> Dict[str, Any]:
    """Record the final decision.

    In production you would persist to a database or publish a Pub/Sub message.
    Here we simply return a summary dict.
    """
    return {"status": decision, "expense": expense}

# ---------------------------------------------------------------------------
# Build the graph
# ---------------------------------------------------------------------------
graph = Graph(name="expense_approval")

node_parse = FunctionNode(func=parse_event, name="parse_event")
node_decide = FunctionNode(
    func=lambda expense: "auto" if expense["amount"] < THRESHOLD else "review",
    name="decide_path",
)
node_auto = FunctionNode(func=auto_approve, name="auto_approve")
node_llm = FunctionNode(func=risk_assess, name="risk_assess")
node_human = RequestInput(
    prompt="A high‑risk expense needs your approval. Reply with approve or reject.",
    name="human_review",
)
node_record = FunctionNode(func=record_outcome, name="record_outcome")

for n in [node_parse, node_decide, node_auto, node_llm, node_human, node_record]:
    graph.add_node(n)

graph.add_edge(Edge(source=node_parse, target=node_security))
# After security, branch based on injection flag
graph.add_edge(Edge(source=node_security, target=node_human, condition=lambda exp: exp.get('_injection_detected', False)))
# Clean payload proceeds to normal decision path
graph.add_edge(Edge(source=node_security, target=node_decide, condition=lambda exp: not exp.get('_injection_detected', False)))
graph.add_edge(Edge(source=node_decide, target=node_auto, condition=lambda out: out == "auto"))
graph.add_edge(Edge(source=node_decide, target=node_llm, condition=lambda out: out == "review"))
graph.add_edge(Edge(source=node_llm, target=node_human))

def merge(expense, decision):
    return decision

node_merge = FunctionNode(func=merge, name="merge_expense_and_decision")
graph.add_node(node_merge)

graph.add_edge(Edge(source=node_human, target=node_merge))
graph.add_edge(Edge(source=node_parse, target=node_merge))
graph.add_edge(Edge(source=node_merge, target=node_record))

expense_agent = Agent(
    name="expense_approval_agent",
    graph=graph,
    instruction="Process expense reports, auto‑approve under $100, otherwise run risk LLM and wait for human approval.",
    model=MODEL,
)

if __name__ == "__main__":
    expense_agent.run()
