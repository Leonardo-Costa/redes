"""Pydantic extraction schema for incident analysis."""
from enum import Enum
from pydantic import BaseModel, Field


class BaselCategory(str, Enum):
    internal_fraud = "internal_fraud"
    external_fraud = "external_fraud"
    employment_practices = "employment_practices"
    clients_products_practices = "clients_products_practices"
    damage_physical_assets = "damage_physical_assets"
    business_disruption_systems = "business_disruption_systems"
    execution_delivery_process = "execution_delivery_process"
    unclear = "unclear"


class ProductDomain(str, Enum):
    credit_card = "credit_card"
    mortgage = "mortgage"
    checking_savings = "checking_savings"
    student_loan = "student_loan"
    auto_loan = "auto_loan"
    debt_collection = "debt_collection"
    credit_reporting = "credit_reporting"
    money_transfers = "money_transfers"
    other = "other"


class RootCauseType(str, Enum):
    process_failure = "process_failure"
    system_error = "system_error"
    human_error = "human_error"
    fraud_external = "fraud_external"
    fraud_internal = "fraud_internal"
    third_party_failure = "third_party_failure"
    policy_gap = "policy_gap"
    communication_failure = "communication_failure"
    unclear = "unclear"


class FinancialImpact(str, Enum):
    none = "none"
    low = "low"        # < $100
    medium = "medium"  # $100-$10k
    high = "high"      # > $10k
    unclear = "unclear"


class DetectionStage(str, Enum):
    customer_reported = "customer_reported"
    internal_audit = "internal_audit"
    regulatory = "regulatory"
    automated_monitoring = "automated_monitoring"
    unclear = "unclear"


class EntityMention(BaseModel):
    entity_type: str = Field(description="One of: product, channel, process, error_code, actor, system")
    name: str = Field(description="The entity name as it appears in the text")
    evidence_span: str = Field(description="Brief quote from the narrative supporting this entity")


class Relation(BaseModel):
    source: str = Field(description="The causing or preceding entity/event")
    relation_type: str = Field(description="One of: cause_of, observed_with, impacts, precedes, resolved_by")
    target: str = Field(description="The resulting or co-occurring entity/event")
    evidence_span: str = Field(description="Brief quote supporting this relation")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in this relation (0-1)")


class IncidentExtraction(BaseModel):
    """Structured extraction of a financial incident/complaint narrative."""

    one_sentence_summary: str = Field(
        description="Single sentence summarizing what happened, focusing on the core incident"
    )
    root_cause_summary: str = Field(
        description="1-2 sentences describing the likely root cause of the issue"
    )
    customer_impact_summary: str = Field(
        description="1-2 sentences describing the impact on the customer"
    )

    basel_category: BaselCategory = Field(
        description="Basel II operational risk event type that best fits this incident"
    )
    product_domain: ProductDomain = Field(
        description="Primary financial product or domain involved"
    )
    root_cause_type: RootCauseType = Field(
        description="Primary root cause category"
    )
    financial_impact: FinancialImpact = Field(
        description="Estimated financial impact level"
    )
    detection_stage: DetectionStage = Field(
        description="How the issue was detected"
    )

    third_party_involved: bool = Field(description="Was a third party (vendor, partner) involved?")
    automated_system_involved: bool = Field(description="Was an automated system or algorithm involved?")
    customer_facing: bool = Field(description="Did this directly affect customer experience?")
    regulatory_implication: bool = Field(description="Does this have regulatory reporting implications?")
    suggests_recurring_pattern: bool = Field(description="Does this appear to be part of a recurring issue?")

    affected_systems: list[str] = Field(
        default_factory=list,
        description="Names of affected systems, platforms or channels (e.g. 'mobile app', 'ACH system')"
    )
    keywords: list[str] = Field(
        default_factory=list,
        max_length=10,
        description="Up to 10 domain-specific keywords or phrases for indexing"
    )

    entities: list[EntityMention] = Field(
        default_factory=list,
        description="Named entities extracted from the narrative (products, systems, actors)"
    )
    causal_relations: list[Relation] = Field(
        default_factory=list,
        description="Causal or co-occurrence relations extracted from the narrative"
    )
