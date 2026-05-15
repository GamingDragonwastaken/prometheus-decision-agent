import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.orchestrator import run_analysis


SCENARIOS = [
    (
        "openai_market_entry",
        "Should I compete with OpenAI in the enterprise AI market in 2026, or find a different niche? What is the real risk of going head-to-head with them?",
    ),
    (
        "salesforce_vs_hubspot_italy",
        "Should an Italian mid-market company (50-500 employees) choose Salesforce or HubSpot as their CRM — and what is the real risk of getting this decision wrong?",
    ),
    (
        "tesla_threat_europe",
        "Should a European automotive executive treat Tesla as an existential threat in 2026, or is this competitor manageable? What should they do in the next 12 months?",
    ),
]


async def main():
    for scenario_id, question in SCENARIOS:
        print(f"\nRunning: {scenario_id}...")
        out_path = f"data/cache_{scenario_id}.json"
        if Path(out_path).exists():
            with open(out_path) as f:
                cached = json.load(f)
            decision = cached["decision"]
            print(f"  Decision: {decision['decision']} ({decision['confidence_pct']}%)")
            print(f"  Duration: {cached['total_duration_seconds']}s")
            print(f"  Saved: {out_path}")
            continue

        result = await run_analysis(question)
        with open(out_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)
        print(f"  Decision: {result.decision.decision} ({result.decision.confidence_pct}%)")
        print(f"  Duration: {result.total_duration_seconds}s")
        print(f"  Saved: {out_path}")


asyncio.run(main())
