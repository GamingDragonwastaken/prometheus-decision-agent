"""Shared data models for PROMETHEUS."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ResearchBrief(BaseModel):
    question: str
    key_facts: list[str]
    market_position: str
    recent_signals: list[str]
    raw_narrative: str


class CritiqueBrief(BaseModel):
    assumptions_challenged: list[str]
    gaps_identified: list[str]
    alternative_interpretations: list[str]
    raw_narrative: str


class DisagreementRow(BaseModel):
    scout_claim: str
    challenger_objection: str
    strategist_resolution: str


class StrategicBrief(BaseModel):
    question: str
    threat_score: int
    opportunity_score: int
    threat_score_rationale: str
    opportunity_score_rationale: str
    recommendations: list[str]
    executive_summary: str
    timestamp: datetime


class DecisionBrief(BaseModel):
    decision: str
    confidence_pct: int
    primary_condition: str
    secondary_condition: str
    revisit_trigger: str
    rationale: str


class AnalysisRequest(BaseModel):
    question: str
    scenario_id: Optional[str] = None


class AnalysisResult(BaseModel):
    id: str
    question: str
    research: ResearchBrief
    critique: CritiqueBrief
    disagreements: list[DisagreementRow]
    strategy: StrategicBrief
    decision: DecisionBrief
    total_duration_seconds: float
