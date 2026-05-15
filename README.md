# PROMETHEUS — Autonomous Competitive Decision Agent

**[🔥 Live Demo](https://prometheus-decision-agent-xrvhtvpsfktvewy5kuyjp4.streamlit.app/)** | Built for AI Agent Olympics @ Milan AI Week 2026

---

## What It Does

PROMETHEUS produces an autonomous GO / NO-GO / MONITOR verdict for strategic competitive decisions. It takes a decision question, runs four specialized agents through research, critique, synthesis, and final decision-making, then returns calibrated confidence, conditions, and a revisit trigger. Scout researches the live market with Gemini and Google Search grounding; Challenger attacks weak assumptions; Strategist resolves disagreements; Decision Gate makes the call. The result is decision intelligence, not another long report.

---

## Why Four Agents Instead of One

A single LLM is too agreeable for high-stakes strategy. It can summarize evidence, but it has no built-in quality control loop, no adversarial pressure, and a tendency to make its first coherent answer sound more certain than it deserves.

PROMETHEUS separates the work into roles. Scout gathers recent facts, Challenger tests the brief for unsupported assumptions and gaps, Strategist reconciles the disagreement into actionable recommendations, and Decision Gate converts the intelligence into a verdict with calibrated confidence.

---

## The Pipeline

```text
Decision Question
       │
       ▼
  ┌─────────┐
  │  SCOUT  │ ← Gemini 2.5 Flash + Google Search grounding (live web)
  └────┬────┘
       │  ResearchBrief (5+ grounded facts)
       ▼
  ┌────────────┐
  │ CHALLENGER │ ← Gemini 2.5 Flash (no grounding — reasons on Scout's output)
  └─────┬──────┘
        │  CritiqueBrief (assumptions challenged, gaps, alternatives)
        ▼
  ┌─────────────┐
  │  STRATEGIST │ ← Resolves disagreements → Disagreement Table in UI
  └──────┬──────┘
         │  StrategicBrief + DisagreementRows
         ▼
  ┌───────────────┐
  │ DECISION GATE │ ← Confidence calibrated by Challenger's unresolved gaps
  └───────┬───────┘
          │
          ▼
   GO / NO-GO / MONITOR
   + confidence % + conditions + revisit trigger
```

---

## Demo Scenarios

| Decision Question | Verdict | Confidence |
|---|---:|---:|
| Should I compete with OpenAI in enterprise AI? | NO-GO | 65% |
| Salesforce or HubSpot for Italian mid-market? | MONITOR | 62% |
| Is Tesla an existential threat to European automakers? | GO | 88% |

All scenarios run the full 4-agent pipeline live — cached results available for instant demo replay.

---

## Tech Stack

| Component | Technology |
|---|---|
| Intelligence Engine | Gemini 2.5 Flash |
| Live Web Research | Google Search Grounding (Gemini API) |
| Backend API | FastAPI (Python 3.11) |
| Frontend | Streamlit |
| Database | SQLite (aiosqlite) |
| Backend Deployment | Vultr Cloud Compute (Ubuntu 24.04) |
| Frontend Deployment | Streamlit Community Cloud |
| Containerization | Docker + Docker Compose |

---

## Quick Start (Local)

```bash
git clone https://github.com/GamingDragonwastaken/prometheus-decision-agent
cd prometheus-decision-agent

# Install dependencies
pip install -r requirements.txt

# Set API key
cp .env.example .env
# Edit .env: add your GEMINI_API_KEY from aistudio.google.com

# Start backend
uvicorn backend.main:app --reload

# In a new terminal, start frontend
streamlit run app.py

# Open http://localhost:8501 — select a scenario and click Run Analysis
```

---

## Architecture Notes

Grounding is limited to Scout because live search belongs at the evidence-gathering boundary, not inside every reasoning step. Challenger has no grounding by design: it critiques Scout's brief, so it cannot silently replace the evidence base with new searches. Strategist resolves the strongest disagreements into a table the user can inspect. Decision Gate lowers confidence when Challenger identifies unresolved gaps, which prevents a fluent answer from becoming an overconfident verdict.

---

## Hackathon Context

AI Agent Olympics @ Milan AI Week 2026. Targeting Vultr Award (deployed on Vultr Cloud Compute) and Google Award (built on Gemini API with Google Search grounding).

Prize track: Vultr + Google (dual-track)
