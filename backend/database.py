"""SQLite persistence helpers for PROMETHEUS."""

import json
import os
from pathlib import Path

import aiosqlite

from backend.models import AnalysisResult


def _db_path() -> str:
    return os.getenv("DB_PATH", "./data/prometheus.db")


async def init_db() -> None:
    """Create PROMETHEUS database tables if they do not exist."""
    db_path = _db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                threat_score INTEGER,
                opportunity_score INTEGER,
                recommendations TEXT,
                executive_summary TEXT,
                decision TEXT,
                confidence_pct INTEGER,
                primary_condition TEXT,
                revisit_trigger TEXT,
                decision_rationale TEXT,
                disagreements TEXT,
                duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                analysis_id TEXT,
                agent_name TEXT NOT NULL,
                output TEXT NOT NULL,
                duration_seconds REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        await db.commit()


async def save_analysis(result: AnalysisResult) -> None:
    """Persist a completed analysis summary."""
    async with aiosqlite.connect(_db_path()) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO analyses (
                id,
                question,
                threat_score,
                opportunity_score,
                recommendations,
                executive_summary,
                decision,
                confidence_pct,
                primary_condition,
                revisit_trigger,
                decision_rationale,
                disagreements,
                duration_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                result.id,
                result.question,
                result.strategy.threat_score,
                result.strategy.opportunity_score,
                json.dumps(result.strategy.recommendations),
                result.strategy.executive_summary,
                result.decision.decision,
                result.decision.confidence_pct,
                result.decision.primary_condition,
                result.decision.revisit_trigger,
                result.decision.rationale,
                json.dumps([row.model_dump() for row in result.disagreements]),
                result.total_duration_seconds,
            ),
        )
        await db.commit()


async def get_recent_analyses(limit: int = 10) -> list[dict]:
    """Return recent analyses ordered by newest first."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM analyses
            ORDER BY created_at DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

    return [dict(row) for row in rows]
