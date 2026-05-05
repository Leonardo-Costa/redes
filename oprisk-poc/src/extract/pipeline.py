"""Batch LLM extraction pipeline using instructor + anthropic."""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import instructor
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

load_dotenv()

from src.db import get_engine, get_session_factory
from src.extract.schema import IncidentExtraction
from src.models import Incident, EntityMention, Entity, Relation

MODEL = os.getenv("EXTRACTION_MODEL", "claude-sonnet-4-6")
CONCURRENCY = int(os.getenv("EXTRACTION_CONCURRENCY", "5"))

SYSTEM_PROMPT = """You are an expert in operational risk management and financial services compliance.
Analyze the customer complaint narrative and extract structured information.
Be concise and precise. Focus on the operational risk perspective, not the customer service one.
If information is not present in the narrative, use the most appropriate 'unclear' or empty value."""


def _make_anthropic_client() -> anthropic.Anthropic:
    """Build Anthropic client, falling back to OAuth bearer token if no API key."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key and not api_key.startswith("sk-ant-..."):
        return anthropic.Anthropic(api_key=api_key)
    token_file = os.getenv("CLAUDE_SESSION_INGRESS_TOKEN_FILE", "")
    if token_file and Path(token_file).exists():
        token = Path(token_file).read_text().strip()
        logger.info("Using OAuth bearer token from CLAUDE_SESSION_INGRESS_TOKEN_FILE")
        return anthropic.Anthropic(
            auth_token=token,
            default_headers={"anthropic-beta": "oauth-2025-04-20"},
        )
    return anthropic.Anthropic()


client = instructor.from_anthropic(_make_anthropic_client())


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    reraise=True,
)
def extract_one(narrative: str) -> IncidentExtraction:
    return client.chat.completions.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Narrative:\n{narrative[:3000]}"}],
        response_model=IncidentExtraction,
    )


def run_extraction(session: Session, batch_size: int = 50) -> dict:
    """Extract all unprocessed incidents using thread-pool concurrency."""
    stmt = select(Incident).where(Incident.one_sentence_summary.is_(None))
    incidents = session.scalars(stmt).all()
    logger.info(f"Found {len(incidents)} incidents to extract (concurrency={CONCURRENCY})")

    cost_tracker = {"processed": 0, "failed": 0, "start_time": time.time()}

    def _extract_task(incident: Incident) -> tuple[Incident, IncidentExtraction | None]:
        try:
            result = extract_one(incident.narrative)
            return incident, result
        except Exception as e:
            logger.warning(f"Extraction failed for incident {incident.id}: {e}")
            return incident, None

    for i in tqdm(range(0, len(incidents), batch_size), desc="Extracting"):
        batch = incidents[i : i + batch_size]
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
            futures = {pool.submit(_extract_task, inc): inc for inc in batch}
            for future in as_completed(futures):
                incident, result = future.result()
                if result is not None:
                    _apply_extraction(incident, result, session)
                    cost_tracker["processed"] += 1
                else:
                    cost_tracker["failed"] += 1
        session.commit()
        logger.debug(f"Committed batch {i // batch_size + 1}")

    elapsed = time.time() - cost_tracker["start_time"]
    logger.success(
        f"Extraction complete: {cost_tracker['processed']} ok, "
        f"{cost_tracker['failed']} failed in {elapsed:.1f}s"
    )
    _log_cost(cost_tracker)
    return cost_tracker


def _apply_extraction(incident: Incident, result: IncidentExtraction, session: Session) -> None:
    incident.one_sentence_summary = result.one_sentence_summary
    incident.root_cause_summary = result.root_cause_summary
    incident.customer_impact_summary = result.customer_impact_summary
    incident.basel_category = result.basel_category.value
    incident.product_domain = result.product_domain.value
    incident.root_cause_type = result.root_cause_type.value
    incident.financial_impact = result.financial_impact.value
    incident.detection_stage = result.detection_stage.value
    incident.third_party_involved = result.third_party_involved
    incident.automated_system_involved = result.automated_system_involved
    incident.customer_facing = result.customer_facing
    incident.regulatory_implication = result.regulatory_implication
    incident.suggests_recurring_pattern = result.suggests_recurring_pattern
    incident.affected_systems = result.affected_systems or []
    incident.keywords = result.keywords or []

    # Entity mentions
    for em in result.entities:
        mention = EntityMention(
            incident_id=incident.id,
            entity_type=em.entity_type,
            raw_name=em.name,
            evidence_span=em.evidence_span,
        )
        session.add(mention)

    # Relations
    for rel in result.causal_relations:
        r = Relation(
            incident_id=incident.id,
            relation_type=rel.relation_type,
            source_entity_raw=rel.source,
            target_entity_raw=rel.target,
            evidence_span=rel.evidence_span,
            confidence=rel.confidence,
        )
        session.add(r)


def _log_cost(tracker: dict) -> None:
    cost_path = Path("extraction_cost.json")
    entry = {
        "date": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "processed": tracker["processed"],
        "failed": tracker["failed"],
        "elapsed_s": round(time.time() - tracker["start_time"], 1),
    }
    history = json.loads(cost_path.read_text()) if cost_path.exists() else []
    history.append(entry)
    cost_path.write_text(json.dumps(history, indent=2))


if __name__ == "__main__":
    engine = get_engine()
    SessionFactory = get_session_factory(engine)
    with SessionFactory() as session:
        run_extraction(session)
