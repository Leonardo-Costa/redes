"""Tests for extraction schema and template filling."""
import pytest
from src.extract.schema import (
    IncidentExtraction,
    BaselCategory,
    ProductDomain,
    RootCauseType,
    FinancialImpact,
    DetectionStage,
)
from src.ingest.synthetic import generate_synthetic_dataset, _fill_template, TEMPLATES


# ── schema validation ──────────────────────────────────────────────────────────

def test_incident_extraction_schema():
    """IncidentExtraction accepts valid data."""
    data = IncidentExtraction(
        one_sentence_summary="Test summary.",
        root_cause_summary="Root cause.",
        customer_impact_summary="Customer was affected.",
        basel_category=BaselCategory.execution_delivery_process,
        product_domain=ProductDomain.credit_card,
        root_cause_type=RootCauseType.process_failure,
        financial_impact=FinancialImpact.medium,
        detection_stage=DetectionStage.customer_reported,
        third_party_involved=False,
        automated_system_involved=True,
        customer_facing=True,
        regulatory_implication=False,
        suggests_recurring_pattern=False,
        affected_systems=["payment processor"],
        keywords=["unauthorized charge", "dispute"],
        entities=[],
        causal_relations=[],
    )
    assert data.basel_category == BaselCategory.execution_delivery_process
    assert data.financial_impact == FinancialImpact.medium


def test_enum_values_are_strings():
    """All enum values are strings (for DB storage)."""
    assert isinstance(BaselCategory.execution_delivery_process.value, str)
    assert isinstance(ProductDomain.mortgage.value, str)
    assert isinstance(RootCauseType.system_error.value, str)


def test_unclear_enums_exist():
    """'unclear' variant exists on ambiguous enums."""
    assert BaselCategory.unclear
    assert RootCauseType.unclear
    assert FinancialImpact.unclear
    assert DetectionStage.unclear


# ── synthetic data ─────────────────────────────────────────────────────────────

def test_synthetic_generates_correct_count():
    df = generate_synthetic_dataset(n=100, seed=42)
    assert len(df) == 100


def test_synthetic_has_required_columns():
    df = generate_synthetic_dataset(n=50, seed=1)
    for col in ["cfpb_id", "narrative", "date_received", "cfpb_product", "cfpb_issue"]:
        assert col in df.columns, f"Missing column: {col}"


def test_synthetic_narratives_are_non_empty():
    df = generate_synthetic_dataset(n=50, seed=1)
    assert (df["narrative"].str.len() > 50).all()


def test_synthetic_cfpb_ids_unique():
    df = generate_synthetic_dataset(n=200, seed=42)
    assert df["cfpb_id"].nunique() == 200


def test_synthetic_product_distribution():
    df = generate_synthetic_dataset(n=1000, seed=42)
    counts = df["cfpb_product"].value_counts(normalize=True)
    # Credit card should be the largest at ~22%
    assert counts.index[0] == "Credit card or prepaid card"
    assert counts.iloc[0] > 0.15


def test_fill_template_replaces_placeholders():
    """No leftover {placeholder} tokens after filling."""
    for product, templates in TEMPLATES.items():
        for tmpl in templates:
            filled = _fill_template(tmpl)
            # Check no unresolved {...} remain that look like template keys
            import re
            remaining = re.findall(r'\{[a-z_]+\}', filled)
            assert not remaining, f"Unfilled placeholders in {product}: {remaining}"


def test_synthetic_date_range():
    df = generate_synthetic_dataset(n=200, seed=42)
    import pandas as pd
    dates = pd.to_datetime(df["date_received"])
    assert dates.min().year >= 2021
    assert dates.max().year <= 2024
