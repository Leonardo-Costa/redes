"""Anthropic native tool-calling agent for the OpRisk POC."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy.orm import Session

from src.models import AgentSession
from src.ui import tools as T

load_dotenv()

AGENT_MODEL = os.getenv("EXTRACTION_MODEL", "claude-sonnet-4-6")

TOOL_DEFS = [
    {
        "name": "semantic_search",
        "description": "Semantic vector search across incidents. Returns ranked list by similarity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text search query"},
                "facet": {
                    "type": "string",
                    "enum": ["summary", "root_cause", "impact"],
                    "description": "Which embedding facet to search",
                },
                "k": {"type": "integer", "description": "Number of results (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "filter_incidents",
        "description": "Filter incidents by date range, product, severity, or cluster.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "ISO date string (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "ISO date string (YYYY-MM-DD)"},
                "product": {
                    "type": "string",
                    "enum": ["credit_card", "mortgage", "checking_savings", "student_loan",
                             "auto_loan", "debt_collection", "credit_reporting", "money_transfers", "other"],
                },
                "financial_impact": {"type": "string", "enum": ["none", "low", "medium", "high", "unclear"]},
                "cluster_id": {"type": "integer"},
                "facet": {"type": "string", "enum": ["summary", "root_cause", "impact"]},
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
    {
        "name": "temporal_signal",
        "description": "Get temporal trend signal for a cluster (growing/shrinking/emerging/stable).",
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_id": {"type": "integer"},
                "facet": {"type": "string", "enum": ["summary", "root_cause", "impact"]},
            },
            "required": ["cluster_id"],
        },
    },
    {
        "name": "cluster_summary",
        "description": "Get cluster metadata, label, and sample incidents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "cluster_id": {"type": "integer"},
                "facet": {"type": "string", "enum": ["summary", "root_cause", "impact"]},
            },
            "required": ["cluster_id"],
        },
    },
    {
        "name": "causal_lookup",
        "description": "Find causal/co-occurrence relations involving a named entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity name to look up"},
                "relation_type": {
                    "type": "string",
                    "enum": ["cause_of", "observed_with", "impacts", "precedes", "resolved_by"],
                    "description": "Filter by relation type (optional)",
                },
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["entity"],
        },
    },
    {
        "name": "get_incident",
        "description": "Get full detail for a single incident by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "integer"},
            },
            "required": ["incident_id"],
        },
    },
]

SYSTEM_PROMPT = """You are an operational risk analyst assistant for a financial services firm.
You have access to a database of processed customer complaint incidents.
Use the provided tools to answer questions about incident patterns, root causes, and trends.
Always cite specific incident IDs when referencing data. Be precise and analytical."""


def _make_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    token_file = os.getenv("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
    if token_file and Path(token_file).exists() and (not api_key or api_key.startswith("sk-ant-...")):
        token = Path(token_file).read_text().strip()
        return anthropic.Anthropic(
            auth_token=token,
            default_headers={"anthropic-beta": "oauth-2025-04-20"},
        )
    return anthropic.Anthropic()


def _dispatch_tool(name: str, inputs: dict, session: Session) -> str:
    if name == "semantic_search":
        result = T.semantic_search(session, **inputs)
    elif name == "filter_incidents":
        result = T.filter_incidents(session, **inputs)
    elif name == "temporal_signal":
        result = T.temporal_signal(session, **inputs)
    elif name == "cluster_summary":
        result = T.cluster_summary(session, **inputs)
    elif name == "causal_lookup":
        result = T.causal_lookup(session, **inputs)
    elif name == "get_incident":
        result = T.get_incident(session, **inputs)
    else:
        result = {"error": f"Unknown tool: {name}"}
    return json.dumps(result, default=str)


def run_agent(
    user_message: str,
    session: Session,
    session_id: str = "default",
    max_iterations: int = 10,
) -> tuple[str, list[int]]:
    """Run agent loop; returns (final_response_text, cited_incident_ids)."""
    client = _make_client()
    messages = [{"role": "user", "content": user_message}]
    tool_call_log = []
    cited_ids: set[int] = set()

    for _ in range(max_iterations):
        response = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFS,
            messages=messages,
        )

        assistant_content = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        messages.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "end_turn":
            final_text = " ".join(
                b["text"] for b in assistant_content if b.get("type") == "text"
            )
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                tool_call_log.append({"tool": block.name, "input": block.input})
                result_str = _dispatch_tool(block.name, block.input, session)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })
                # Extract cited incident IDs from result
                try:
                    data = json.loads(result_str)
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "id" in item:
                                cited_ids.add(int(item["id"]))
                    elif isinstance(data, dict) and "id" in data:
                        cited_ids.add(int(data["id"]))
                except Exception:
                    pass

            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = " ".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            break
    else:
        final_text = "Agent reached maximum iterations without a final answer."

    # Audit log
    try:
        audit = AgentSession(
            session_id=session_id,
            user_message=user_message[:2000],
            tool_calls=json.dumps(tool_call_log),
            assistant_response=final_text[:4000],
            incident_ids_cited=list(cited_ids) or None,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        session.add(audit)
        session.commit()
    except Exception as e:
        logger.warning(f"Failed to write agent audit log: {e}")

    return final_text, list(cited_ids)
