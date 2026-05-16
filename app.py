from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import html
import json
import re
import time

import httpx
import streamlit as st
import yaml


try:
    BACKEND_URL = st.secrets.get("BACKEND_URL", "http://localhost:8000")
except Exception:
    BACKEND_URL = "http://localhost:8000"
CACHE_DIR = Path("data")

SPINNER_MESSAGES = [
    "🔍 Scout is searching the web for intelligence...",
    "⚡ Challenger is finding the flaws...",
    "🎯 Strategist is synthesizing both perspectives...",
    "🏛️ Decision Gate is making the call...",
]


st.set_page_config(
    page_title="PROMETHEUS — Decision Intelligence",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)


SESSION_DEFAULTS = {
    "analysis_running": False,
    "selected_scenario": "Custom question",
    "question_text": "",
    "cache_notice": "",
    "scout_text": "",
    "challenger_text": "",
    "strategist_text": "",
    "decision_text": "",
    "disagreements": [],
    "final_result": None,
}

for key, value in SESSION_DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

        :root {
            --prom-bg: #09090B;
            --prom-panel: rgba(12, 12, 13, 0.75);
            --prom-panel-soft: #151515;
            --prom-line: #2A2A2A;
            --prom-text: #FFFFFF;
            --prom-muted: #A3A3A3;
            --prom-amber: #F59E0B;
            --prom-blue: #3B82F6;
            --prom-orange: #F97316;
            --prom-green: #22C55E;
            --prom-purple: #A855F7;
            --prom-red: #EF4444;
        }

        html, body, [class*="css"] {
            font-family: "Outfit", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
            background: radial-gradient(
                ellipse 140% 45% at 50% -5%,
                rgba(245, 158, 11, 0.07) 0%,
                rgba(245, 158, 11, 0.02) 35%,
                #09090B 65%
            ) !important;
            background-attachment: fixed !important;
        }

        .block-container {
            max-width: 1480px;
            padding-top: 2rem;
            padding-bottom: 4rem;
        }

        h1, h2, h3 { letter-spacing: 0; }

        div[data-testid="stButton"] > button {
            min-height: 3rem;
            border-radius: 8px;
            border: 1px solid rgba(245, 158, 11, 0.55);
            background: linear-gradient(135deg, #F59E0B 0%, #FBBF24 50%, #F59E0B 100%) !important;
            background-size: 200% 100% !important;
            color: #111111;
            font-weight: 800 !important;
            letter-spacing: 1.5px !important;
            box-shadow:
                0 0 0 1px rgba(245, 158, 11, 0.4),
                0 0 28px rgba(245, 158, 11, 0.2),
                0 4px 12px rgba(0, 0, 0, 0.4) !important;
            transition: background-position 0.4s ease, box-shadow 0.2s ease, transform 0.15s ease !important;
        }

        div[data-testid="stButton"] > button:hover {
            background-position: 100% 0 !important;
            box-shadow:
                0 0 0 1px rgba(245, 158, 11, 0.6),
                0 0 44px rgba(245, 158, 11, 0.35),
                0 6px 20px rgba(0, 0, 0, 0.5) !important;
            border-color: #F59E0B;
            transform: translateY(-2px) !important;
        }

        div[data-testid="stButton"] > button:active {
            transform: translateY(1px) scale(0.99);
        }

        .prom-subtitle {
            color: var(--prom-muted);
            margin-top: -0.4rem;
            font-size: 1.02rem;
        }

        .prom-header {
            text-align: center;
            padding: 20px 0 10px 0;
        }

        .prom-header h1 {
            font-size: 2.8rem;
            background: linear-gradient(
                160deg,
                #FBBF24 0%,
                #F59E0B 35%,
                #D97706 70%,
                #B45309 100%
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            filter: drop-shadow(0 0 28px rgba(245, 158, 11, 0.4));
            letter-spacing: 6px;
            margin: 0;
            font-weight: 900;
            line-height: 1.05;
        }

        .prom-header p {
            color: #9CA3AF;
            font-size: 1rem;
            margin: 4px 0 0 0;
            letter-spacing: 2px;
            font-weight: 700;
        }

        .agent-panel {
            border-radius: 10px;
            padding: 22px 26px;
            border: 2px solid;
            background: rgba(12, 12, 13, 0.75) !important;
            backdrop-filter: blur(16px) saturate(180%);
            -webkit-backdrop-filter: blur(16px) saturate(180%);
            box-shadow:
                0 0 0 1px rgba(255, 255, 255, 0.04),
                0 6px 36px rgba(0, 0, 0, 0.45),
                inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
            transition: box-shadow 0.25s ease, transform 0.25s ease;
        }

        .agent-row {
            display: grid;
            grid-template-columns: 56px 1fr auto;
            align-items: center;
            gap: 18px;
            margin-bottom: 14px;
        }

        .agent-index {
            font-family: "JetBrains Mono", monospace;
            font-size: 2.4rem;
            font-weight: 700;
            line-height: 1;
            letter-spacing: -0.02em;
            color: rgba(255, 255, 255, 0.10);
            text-align: left;
        }

        .agent-index.scout       { color: rgba(59, 130, 246, 0.22); }
        .agent-index.challenger  { color: rgba(249, 115, 22, 0.22); }
        .agent-index.strategist  { color: rgba(34, 197, 94, 0.22); }
        .agent-index.decision-gate { color: rgba(168, 85, 247, 0.22); }

        .agent-meta { display: flex; flex-direction: column; gap: 2px; }
        .agent-name {
            font-size: 1.15rem;
            font-weight: 800;
            letter-spacing: 0.4px;
            line-height: 1.15;
        }
        .agent-name.scout       { color: #3B82F6; }
        .agent-name.challenger  { color: #F97316; }
        .agent-name.strategist  { color: #22C55E; }
        .agent-name.decision-gate { color: #A855F7; }

        .agent-sub {
            color: #A3A3A3;
            font-size: 0.82rem;
            letter-spacing: 0.3px;
        }

        .pipeline-connector {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            margin: 14px 0;
        }

        .pipeline-arrow {
            width: 2px;
            height: 30px;
            border-radius: 1px;
            background: linear-gradient(
                180deg,
                rgba(245, 158, 11, 0.0) 0%,
                rgba(245, 158, 11, 0.55) 45%,
                rgba(245, 158, 11, 0.55) 55%,
                rgba(245, 158, 11, 0.0) 100%
            );
        }

        .pipeline-arrow::after {
            content: "";
            display: block;
            width: 0;
            height: 0;
            margin: -1px auto 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid rgba(245, 158, 11, 0.55);
            transform: translateY(2px);
        }

        .pipeline-label {
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            color: rgba(245, 158, 11, 0.75);
        }

        .pipeline-label .pipe-faded {
            color: rgba(255, 255, 255, 0.35);
            font-weight: 600;
        }

        .exchange-callout {
            margin: 18px 0;
            padding: 20px 24px 8px;
            border-radius: 10px;
            background: rgba(20, 20, 22, 0.55);
            border: 1px dashed rgba(245, 158, 11, 0.22);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
        }

        .exchange-callout-title {
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            color: rgba(245, 158, 11, 0.9);
            margin-bottom: 2px;
        }

        .exchange-callout-sub {
            color: #A3A3A3;
            font-size: 0.86rem;
            margin-bottom: 10px;
        }

        .agent-panel.scout { border-color: #3B82F6; }
        .agent-panel.challenger { border-color: #F97316; }
        .agent-panel.strategist { border-color: #22C55E; }
        .agent-panel.decision-gate { border-color: #A855F7; }

        .agent-panel:hover {
            box-shadow:
                0 0 0 1px rgba(255, 255, 255, 0.07),
                0 8px 40px rgba(0, 0, 0, 0.6),
                inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
            transform: translateY(-1px);
        }

        .agent-panel.scout:hover {
            box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.25), 0 0 20px rgba(59, 130, 246, 0.08), 0 8px 32px rgba(0, 0, 0, 0.5) !important;
        }
        .agent-panel.challenger:hover {
            box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.25), 0 0 20px rgba(249, 115, 22, 0.08), 0 8px 32px rgba(0, 0, 0, 0.5) !important;
        }
        .agent-panel.strategist:hover {
            box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.25), 0 0 20px rgba(34, 197, 94, 0.08), 0 8px 32px rgba(0, 0, 0, 0.5) !important;
        }
        .agent-panel.decision-gate:hover {
            box-shadow: 0 0 0 1px rgba(168, 85, 247, 0.25), 0 0 20px rgba(168, 85, 247, 0.08), 0 8px 32px rgba(0, 0, 0, 0.5) !important;
        }

        .agent-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 4px;
        }

        .agent-title {
            font-size: 1.1rem;
            font-weight: 800;
            line-height: 1.2;
        }

        .agent-title.scout { color: #3B82F6; }
        .agent-title.challenger { color: #F97316; }
        .agent-title.strategist { color: #22C55E; }
        .agent-title.decision-gate { color: #A855F7; }

        .agent-caption {
            color: #A3A3A3;
            font-size: 0.85rem;
            margin-bottom: 14px;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border-radius: 999px;
            padding: 3px 9px;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.02em;
            color: #0F0F0F;
        }

        .status-idle { background: #737373; color: #FFFFFF; }
        @keyframes prom-pulse {
            0%, 100% {
                opacity: 1;
                box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.6);
            }
            50% {
                opacity: 0.85;
                box-shadow: 0 0 0 6px rgba(245, 158, 11, 0);
            }
        }

        .status-running {
            background: #F59E0B;
            color: #111111;
            animation: prom-pulse 1.4s ease-in-out infinite !important;
        }
        .status-scout {
            background: #3B82F6;
            color: #FFFFFF;
            box-shadow: 0 0 0 1px rgba(59, 130, 246, 0.4), 0 0 12px rgba(59, 130, 246, 0.25);
        }
        .status-challenger {
            background: #F97316;
            color: #111111;
            box-shadow: 0 0 0 1px rgba(249, 115, 22, 0.4), 0 0 12px rgba(249, 115, 22, 0.25);
        }
        .status-strategist {
            background: #22C55E;
            color: #111111;
            box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.4), 0 0 12px rgba(34, 197, 94, 0.25);
        }
        .status-decision {
            background: #A855F7;
            color: #FFFFFF;
            box-shadow: 0 0 0 1px rgba(168, 85, 247, 0.4), 0 0 12px rgba(168, 85, 247, 0.25);
        }
        .status-complete {
            background: #22C55E;
            color: #111111;
            box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.4), 0 0 12px rgba(34, 197, 94, 0.25);
        }

        .panel-output {
            max-height: 460px;
            overflow-y: auto;
            padding: 16px 18px;
            border-radius: 6px !important;
            background: rgba(7, 7, 8, 0.8) !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            color: #D4D4D4;
            font-size: 0.92rem;
            line-height: 1.6;
            min-height: 96px;
            scrollbar-width: thin;
            scrollbar-color: rgba(245, 158, 11, 0.25) transparent;
        }

        .panel-output strong { color: #FFFFFF; }

        .panel-output::-webkit-scrollbar { width: 4px; }
        .panel-output::-webkit-scrollbar-track { background: transparent; }
        .panel-output::-webkit-scrollbar-thumb {
            background: rgba(245, 158, 11, 0.3);
            border-radius: 999px;
        }

        .empty-output {
            color: #737373;
            font-style: italic;
        }

        .decision-verdict-card {
            margin: 24px 0;
            border: 3px solid;
            border-radius: 12px;
            padding: 32px;
            background: rgba(10, 10, 11, 0.9) !important;
            backdrop-filter: blur(20px) !important;
            -webkit-backdrop-filter: blur(20px) !important;
            text-align: center;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.045);
            transition: box-shadow 0.5s ease !important;
        }

        .decision-verdict {
            font-size: 5rem !important;
            font-weight: 900;
            line-height: 1;
            letter-spacing: 4px !important;
            margin-bottom: 10px;
            font-family: "JetBrains Mono", monospace;
            text-shadow: 0 0 60px currentColor !important;
        }

        .decision-confidence {
            color: #D4D4D4;
            font-size: 1.1rem;
            font-weight: 700;
        }

        .confidence-track {
            width: min(560px, 100%);
            height: 12px;
            margin: 14px auto 0;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow:
                inset 0 1px 2px rgba(0, 0, 0, 0.5),
                inset 0 0 0 1px rgba(255, 255, 255, 0.02);
        }

        .confidence-fill {
            height: 100%;
            border-radius: 999px;
        }

        .decision-rule {
            height: 1px;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.12) 50%,
                transparent 100%
            );
            margin: 24px 0;
        }

        .decision-rationale {
            color: #E5E5E5;
            max-width: 760px;
            margin: 0 auto 18px;
            line-height: 1.65;
            text-align: left;
        }

        .decision-condition {
            color: #BDBDBD;
            margin-top: 8px;
            font-size: 0.95rem;
            max-width: 760px;
            margin-left: auto;
            margin-right: auto;
            text-align: left;
        }

        .threat-score {
            color: #EF4444;
            font-family: "JetBrains Mono", monospace;
            font-weight: 800;
        }

        .opportunity-score {
            color: #22C55E;
            font-family: "JetBrains Mono", monospace;
            font-weight: 800;
        }

        .metric-card {
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            border-radius: 8px;
            padding: 16px;
            background: rgba(14, 14, 15, 0.8) !important;
            backdrop-filter: blur(8px) !important;
            -webkit-backdrop-filter: blur(8px) !important;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3) !important;
        }

        .score-label {
            font-weight: 850;
            margin-bottom: 8px;
        }

        .score-track {
            height: 8px;
            margin-top: 14px;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.04);
            box-shadow:
                inset 0 1px 2px rgba(0, 0, 0, 0.5),
                inset 0 0 0 1px rgba(255, 255, 255, 0.02);
        }

        .score-fill {
            height: 100%;
            border-radius: 999px;
        }

        .score-fill.threat {
            background: #EF4444;
        }

        .score-fill.opportunity {
            background: #22C55E;
        }

        .recommendation-card {
            border-left: 3px solid #F59E0B;
            padding: 12px 16px;
            margin: 8px 0;
            background: rgba(20, 20, 22, 0.72);
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            border-radius: 0 8px 8px 0;
            box-shadow:
                inset 1px 0 0 rgba(245, 158, 11, 0.18),
                0 1px 0 rgba(255, 255, 255, 0.025),
                0 2px 12px rgba(0, 0, 0, 0.25);
            transition: box-shadow 0.2s ease, transform 0.2s ease;
        }

        .recommendation-card:hover {
            box-shadow:
                inset 1px 0 0 rgba(245, 158, 11, 0.35),
                0 1px 0 rgba(255, 255, 255, 0.04),
                0 4px 18px rgba(0, 0, 0, 0.35),
                0 0 20px rgba(245, 158, 11, 0.06);
            transform: translateX(2px);
        }

        .recommendation-index {
            color: #F59E0B;
            font-weight: 800;
        }

        .cache-badge {
            color: #F59E0B;
            font-weight: 700;
        }

        [data-testid="stHorizontalBlock"] hr,
        .stDivider,
        hr {
            border: none !important;
            height: 1px !important;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(245, 158, 11, 0.2) 30%,
                rgba(245, 158, 11, 0.2) 70%,
                transparent 100%
            ) !important;
            margin: 12px 0 !important;
        }

        [data-testid="stSelectbox"] > div > div {
            background: rgba(14, 14, 15, 0.9) !important;
            border: 1px solid rgba(255, 255, 255, 0.07) !important;
            border-radius: 8px !important;
        }

        [data-testid="stTextArea"] textarea {
            background: rgba(9, 9, 11, 0.9) !important;
            border: 1px solid rgba(255, 255, 255, 0.07) !important;
            border-radius: 8px !important;
            color: #E5E5E5 !important;
        }

        [data-testid="stTextArea"] textarea:focus {
            border-color: rgba(245, 158, 11, 0.4) !important;
            box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.08) !important;
        }

        [data-baseweb="popover"] [role="listbox"],
        [data-baseweb="menu"] {
            background: rgba(14, 14, 15, 0.95) !important;
            backdrop-filter: blur(20px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(20px) saturate(160%) !important;
            border: 1px solid rgba(255, 255, 255, 0.07) !important;
            border-radius: 8px !important;
            box-shadow:
                0 12px 40px rgba(0, 0, 0, 0.55),
                0 0 0 1px rgba(245, 158, 11, 0.06) !important;
        }

        [data-baseweb="popover"] [role="option"]:hover,
        [data-baseweb="menu"] li:hover {
            background: rgba(245, 158, 11, 0.08) !important;
        }

        @keyframes prom-breathe {
            0%, 100% { opacity: 0.55; }
            50%      { opacity: 0.85; }
        }

        .empty-output {
            animation: prom-breathe 3.2s ease-in-out infinite;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600)
def fetch_scenarios() -> list[dict]:
    try:
        response = httpx.get(f"{BACKEND_URL}/scenarios", timeout=4)
        response.raise_for_status()
        scenarios = response.json()
    except Exception:
        scenarios = []

    try:
        with open("configs/scenarios.yaml", encoding="utf-8") as scenario_file:
            local_data = yaml.safe_load(scenario_file) or {}
        questions_by_id = {
            scenario["id"]: scenario.get("question", "")
            for scenario in local_data.get("scenarios", [])
        }
        return [
            {
                **scenario,
                "question": scenario.get("question") or questions_by_id.get(scenario.get("id"), ""),
            }
            for scenario in scenarios
        ]
    except Exception:
        return scenarios


@st.cache_data(ttl=60)
def fetch_history() -> list[dict]:
    try:
        response = httpx.get(f"{BACKEND_URL}/history", timeout=4)
        response.raise_for_status()
        return response.json()
    except Exception:
        return []


def clear_results() -> None:
    st.session_state.scout_text = ""
    st.session_state.challenger_text = ""
    st.session_state.strategist_text = ""
    st.session_state.decision_text = ""
    st.session_state.disagreements = []
    st.session_state.final_result = None
    st.session_state.cache_notice = ""


def sync_question_from_scenario() -> None:
    selected = st.session_state.selected_scenario
    if selected != "Custom question":
        scenario = st.session_state.scenario_by_label.get(selected)
        if scenario and scenario.get("question"):
            st.session_state.question_text = scenario["question"]


def markdown_to_panel_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    return escaped.replace("\n", "<br>")


def agent_header(agent_name: str, output_text: str) -> str:
    return f"{'✅' if output_text else '⬜'} {agent_name}"


AGENT_INDEX = {
    "scout": "01",
    "challenger": "02",
    "strategist": "03",
    "decision-gate": "04",
}


def render_agent_panel(
    placeholder,
    kind: str,
    agent_name: str,
    caption: str,
    status_label: str,
    status_class: str,
    output_text: str,
) -> None:
    output = output_text.strip() if output_text else "Waiting for analysis output."
    output_class = "panel-output" if output_text else "panel-output empty-output"
    index_label = AGENT_INDEX.get(kind, "")
    completion_mark = "✓" if output_text else "○"
    placeholder.markdown(
        f"""
        <div class="agent-panel {kind}">
            <div class="agent-row">
                <div class="agent-index {kind}">{index_label}</div>
                <div class="agent-meta">
                    <div class="agent-name {kind}">{completion_mark} &nbsp; {agent_name}</div>
                    <div class="agent-sub">{caption}</div>
                </div>
                <span class="status-badge {status_class}">{status_label}</span>
            </div>
            <div class="{output_class}">{markdown_to_panel_html(output)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


PIPELINE_CONNECTORS = {
    "scout-to-challenger": ("Scout's claims", "Challenger objects"),
    "challenger-to-disagree": ("Challenger's objections", "Disagreements surfaced"),
    "disagree-to-strategist": ("Resolved disagreements", "Strategist synthesizes"),
    "strategist-to-decision": ("Strategist's brief", "Decision Gate rules"),
}


def render_pipeline_connector(placeholder, key: str) -> None:
    from_label, to_label = PIPELINE_CONNECTORS[key]
    placeholder.markdown(
        f"""
        <div class="pipeline-connector">
            <div class="pipeline-label">
                <span class="pipe-faded">{html.escape(from_label)}</span>
                &nbsp;&nbsp;→&nbsp;&nbsp;
                {html.escape(to_label)}
            </div>
            <div class="pipeline-arrow"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_all_agent_panels(
    scout_placeholder,
    challenger_placeholder,
    strategist_placeholder,
    decision_placeholder,
    statuses: dict[str, tuple[str, str]] | None = None,
) -> None:
    statuses = statuses or {}
    render_agent_panel(
        scout_placeholder,
        "scout",
        "Scout",
        "Live web research via Google Search",
        *statuses.get("scout", ("● Idle", "status-idle")),
        st.session_state.scout_text,
    )
    render_agent_panel(
        challenger_placeholder,
        "challenger",
        "Challenger",
        "Adversarial critique",
        *statuses.get("challenger", ("● Idle", "status-idle")),
        st.session_state.challenger_text,
    )
    render_agent_panel(
        strategist_placeholder,
        "strategist",
        "Strategist",
        "Calibrated synthesis",
        *statuses.get("strategist", ("● Idle", "status-idle")),
        st.session_state.strategist_text,
    )
    render_agent_panel(
        decision_placeholder,
        "decision-gate",
        "Decision Gate",
        "Autonomous decision",
        *statuses.get("decision", ("● Idle", "status-idle")),
        st.session_state.decision_text,
    )


def format_scout_output(research: dict) -> str:
    lines = [f"**Market Position:** {research['market_position']}", ""]
    lines.append("**Key Facts:**")
    for fact in research["key_facts"]:
        lines.append(f"• {fact}")
    lines.append("")
    lines.append("**Recent Signals:**")
    for signal in research["recent_signals"]:
        lines.append(f"→ {signal}")
    return "\n".join(lines)


def format_challenger_output(critique: dict) -> str:
    lines = ["**Assumptions Challenged:**"]
    for assumption in critique["assumptions_challenged"]:
        lines.append(f"⚠ {assumption}")
    lines.append("")
    lines.append("**Gaps Identified:**")
    for gap in critique["gaps_identified"]:
        lines.append(f"✗ {gap}")
    lines.append("")
    lines.append("**Alternative Interpretations:**")
    for interpretation in critique["alternative_interpretations"]:
        lines.append(f"↔ {interpretation}")
    return "\n".join(lines)


def format_strategist_output(strategy: dict) -> str:
    lines = [
        f"**Threat Score:** {strategy['threat_score']}/10 — {strategy['threat_score_rationale']}",
        f"**Opportunity Score:** {strategy['opportunity_score']}/10 — {strategy['opportunity_score_rationale']}",
        "",
        "**Recommendations:**",
    ]
    for index, recommendation in enumerate(strategy["recommendations"], 1):
        lines.append(f"{index}. {recommendation}")
    lines.append("")
    lines.append(f"**Summary:** {strategy['executive_summary']}")
    return "\n".join(lines)


def format_decision_output(decision: dict) -> str:
    return (
        f"Decision: **{decision['decision']}** ({decision['confidence_pct']}% confidence)\n\n"
        f"{decision['rationale']}"
    )


def decision_colors(decision: str) -> tuple[str, str, str]:
    if decision == "GO":
        return "#22C55E", "#22C55E", "0 0 30px rgba(34, 197, 94, 0.3)"
    if decision == "NO-GO":
        return "#EF4444", "#EF4444", "0 0 30px rgba(239, 68, 68, 0.3)"
    return "#F59E0B", "#F59E0B", "0 0 30px rgba(245, 158, 11, 0.3)"


def render_disagreement_table(placeholder, result: dict) -> None:
    with placeholder.container():
        st.markdown(
            """
            <div class="exchange-callout">
                <div class="exchange-callout-title">⚔ Disagreement Exchange</div>
                <div class="exchange-callout-sub">Scout's claim → Challenger's objection → Strategist's resolution</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        disagreement_rows = [
            {
                "Scout claimed": row["scout_claim"],
                "Challenger objected": row["challenger_objection"],
                "Resolved as": row["strategist_resolution"],
            }
            for row in result["disagreements"]
        ]
        st.dataframe(disagreement_rows, use_container_width=True, hide_index=True)


def render_disagreement_placeholder(placeholder) -> None:
    placeholder.markdown(
        """
        <div class="exchange-callout">
            <div class="exchange-callout-title">⚔ Disagreement Exchange</div>
            <div class="exchange-callout-sub">Awaiting Challenger's objections to surface here</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_card(placeholder, result: dict) -> None:
    decision = result["decision"]
    border_color, text_color, glow = decision_colors(decision["decision"])
    confidence = max(0, min(100, int(decision["confidence_pct"])))
    placeholder.markdown(
        f"""
        <div class="decision-verdict-card" style="border-color: {border_color}; box-shadow: {glow}, inset 0 1px 0 rgba(255, 255, 255, 0.045);">
            <div class="decision-verdict" style="color: {text_color};">{html.escape(decision["decision"])}</div>
            <div class="decision-confidence">Confidence: {confidence}%</div>
            <div class="confidence-track">
                <div class="confidence-fill" style="width: {confidence}%; background: {text_color};"></div>
            </div>
            <div class="decision-rule"></div>
            <p class="decision-rationale">{html.escape(decision["rationale"])}</p>
            <div class="decision-condition"><strong>Primary condition:</strong> {html.escape(decision["primary_condition"])}</div>
            <div class="decision-condition"><strong>Revisit if:</strong> {html.escape(decision["revisit_trigger"])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_strategic_brief(placeholder, result: dict) -> None:
    strategy = result["strategy"]
    threat_pct = max(0, min(100, int(strategy["threat_score"]) * 10))
    opportunity_pct = max(0, min(100, int(strategy["opportunity_score"]) * 10))
    with placeholder.container():
        with st.expander("📊 Full Strategic Brief", expanded=True):
            left, right = st.columns(2)
            with left:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="score-label threat-score">⚠ Threat Level: {strategy['threat_score']}/10</div>
                        <p>{html.escape(strategy['threat_score_rationale'])}</p>
                        <div class="score-track"><div class="score-fill threat" style="width: {threat_pct}%;"></div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with right:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="score-label opportunity-score">✓ Opportunity Level: {strategy['opportunity_score']}/10</div>
                        <p>{html.escape(strategy['opportunity_score_rationale'])}</p>
                        <div class="score-track"><div class="score-fill opportunity" style="width: {opportunity_pct}%;"></div></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("#### Recommendations")
            for index, recommendation in enumerate(strategy["recommendations"], start=1):
                st.markdown(
                    f"""
                    <div class="recommendation-card">
                        <strong class="recommendation-index">Recommendation {index}</strong><br/>
                        {html.escape(recommendation)}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("#### Executive Summary")
            st.markdown(strategy["executive_summary"])


def store_result(result: dict) -> None:
    st.session_state.final_result = result
    st.session_state.scout_text = format_scout_output(result["research"])
    st.session_state.challenger_text = format_challenger_output(result["critique"])
    st.session_state.strategist_text = format_strategist_output(result["strategy"])
    st.session_state.decision_text = format_decision_output(result["decision"])
    st.session_state.disagreements = result["disagreements"]


def progressive_display(
    result: dict,
    scout_placeholder,
    challenger_placeholder,
    strategist_placeholder,
    decision_placeholder,
    disagreement_placeholder,
    verdict_placeholder,
    strategic_brief_placeholder,
) -> None:
    st.session_state.final_result = result

    st.session_state.scout_text = format_scout_output(result["research"])
    render_agent_panel(
        scout_placeholder,
        "scout",
        "Scout",
        "Live web research via Google Search",
        "✅ Complete",
        "status-scout",
        st.session_state.scout_text,
    )
    time.sleep(0.4)

    st.session_state.challenger_text = format_challenger_output(result["critique"])
    render_agent_panel(
        challenger_placeholder,
        "challenger",
        "Challenger",
        "Adversarial critique",
        "✅ Complete",
        "status-challenger",
        st.session_state.challenger_text,
    )
    time.sleep(0.4)

    st.session_state.disagreements = result["disagreements"]
    render_disagreement_table(disagreement_placeholder, result)
    time.sleep(0.4)

    st.session_state.strategist_text = format_strategist_output(result["strategy"])
    render_agent_panel(
        strategist_placeholder,
        "strategist",
        "Strategist",
        "Calibrated synthesis",
        "✅ Complete",
        "status-strategist",
        st.session_state.strategist_text,
    )
    time.sleep(0.4)

    st.session_state.decision_text = format_decision_output(result["decision"])
    render_agent_panel(
        decision_placeholder,
        "decision-gate",
        "Decision Gate",
        "Autonomous decision",
        "✅ Complete",
        "status-decision",
        st.session_state.decision_text,
    )
    render_decision_card(verdict_placeholder, result)
    render_strategic_brief(strategic_brief_placeholder, result)


def post_analysis(question: str) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}/analyze",
        json={"question": question},
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()


def run_live_analysis(question: str, spinner_placeholder) -> dict:
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(post_analysis, question)
        start = time.time()
        while not future.done():
            message = SPINNER_MESSAGES[int((time.time() - start) // 20) % len(SPINNER_MESSAGES)]
            spinner_placeholder.info(message)
            time.sleep(1)
        spinner_placeholder.empty()
        return future.result()


def load_cached_result(scenario_id: str) -> dict:
    cache_path = CACHE_DIR / f"cache_{scenario_id}.json"
    with cache_path.open() as cache_file:
        return json.load(cache_file)


def truncate_question(question: str) -> str:
    return f"{question[:60]}..." if len(question) > 60 else question


def format_history_decision(decision: str) -> str:
    prefixes = {
        "GO": "✅ GO",
        "NO-GO": "❌ NO-GO",
        "MONITOR": "🟡 MONITOR",
    }
    return prefixes.get(decision, decision)


def format_confidence(confidence) -> str:
    if confidence in ("", None):
        return ""
    return f"{confidence}%"


def format_created_at(created_at: str) -> str:
    if not created_at:
        return ""
    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(created_at.split("+")[0], date_format).strftime("%b %d, %Y %H:%M")
        except ValueError:
            continue
    return created_at


st.markdown(
    """
    <div class="prom-header">
        <h1>PROMETHEUS</h1>
        <p>AUTONOMOUS COMPETITIVE DECISION INTELLIGENCE</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.divider()


scenarios = fetch_scenarios()
scenario_options = ["Custom question"] + [scenario["label"] for scenario in scenarios]
scenario_by_label = {scenario["label"]: scenario for scenario in scenarios}
st.session_state.scenario_by_label = scenario_by_label

if st.session_state.selected_scenario not in scenario_options:
    st.session_state.selected_scenario = "Custom question"

selected_scenario = st.selectbox(
    "Scenario",
    options=scenario_options,
    key="selected_scenario",
    on_change=sync_question_from_scenario,
)
selected_scenario_data = scenario_by_label.get(selected_scenario)

cache_clicked = False
if selected_scenario_data:
    cache_clicked = st.button(
        "⚡ Load cached result (instant)",
        disabled=st.session_state.analysis_running,
        use_container_width=True,
    )

st.text_area(
    label="Decision question",
    key="question_text",
    height=80,
    placeholder='e.g. "Should I compete with OpenAI in enterprise AI?"',
)

run_clicked = st.button(
    "⚡ Run Analysis",
    type="primary",
    disabled=st.session_state.analysis_running,
    use_container_width=True,
)
st.caption("Analysis runs 4 autonomous agents — typically 90–120 seconds.")

pending_action = None
pending_result = None
question = st.session_state.question_text.strip()

if cache_clicked and selected_scenario_data:
    try:
        clear_results()
        pending_result = load_cached_result(selected_scenario_data["id"])
        st.session_state.cache_notice = "⚡ Loaded from cache — instant result"
        pending_action = "cache"
    except FileNotFoundError:
        st.warning(f"No cache file found for {selected_scenario_data['id']}. Run a live analysis instead.")
    except Exception as exc:
        st.error(f"Cached result failed to load: {exc}")

if run_clicked:
    if not question:
        st.warning("Enter a decision question.")
    else:
        clear_results()
        st.session_state.analysis_running = True
        pending_action = "live"

if st.session_state.cache_notice:
    st.caption(f"<span class='cache-badge'>{st.session_state.cache_notice}</span>", unsafe_allow_html=True)


st.divider()

scout_placeholder = st.empty()
connector_scout_to_challenger = st.empty()
challenger_placeholder = st.empty()
connector_challenger_to_disagree = st.empty()
disagreement_placeholder = st.empty()
connector_disagree_to_strategist = st.empty()
strategist_placeholder = st.empty()
connector_strategist_to_decision = st.empty()
decision_placeholder = st.empty()
verdict_placeholder = st.empty()
strategic_brief_placeholder = st.empty()
spinner_placeholder = st.empty()

render_pipeline_connector(connector_scout_to_challenger, "scout-to-challenger")
render_pipeline_connector(connector_challenger_to_disagree, "challenger-to-disagree")
render_pipeline_connector(connector_disagree_to_strategist, "disagree-to-strategist")
render_pipeline_connector(connector_strategist_to_decision, "strategist-to-decision")

if pending_action:
    render_all_agent_panels(
        scout_placeholder,
        challenger_placeholder,
        strategist_placeholder,
        decision_placeholder,
        {
            "scout": ("● Running", "status-running"),
            "challenger": ("● Running", "status-running"),
            "strategist": ("● Running", "status-running"),
            "decision": ("● Running", "status-running"),
        },
    )
    render_disagreement_placeholder(disagreement_placeholder)
else:
    status = ("✅ Complete", "status-complete") if st.session_state.final_result else ("● Idle", "status-idle")
    render_all_agent_panels(
        scout_placeholder,
        challenger_placeholder,
        strategist_placeholder,
        decision_placeholder,
        {
            "scout": status,
            "challenger": status,
            "strategist": status,
            "decision": status if st.session_state.final_result else ("● Idle", "status-idle"),
        },
    )
    if not st.session_state.final_result:
        render_disagreement_placeholder(disagreement_placeholder)

if pending_action == "live":
    try:
        result = run_live_analysis(question, spinner_placeholder)
        fetch_history.clear()
        progressive_display(
            result,
            scout_placeholder,
            challenger_placeholder,
            strategist_placeholder,
            decision_placeholder,
            disagreement_placeholder,
            verdict_placeholder,
            strategic_brief_placeholder,
        )
    except Exception as exc:
        st.error(f"Analysis failed: {exc}. Try loading a cached scenario instead.")
        st.session_state.analysis_running = False
        st.stop()
    st.session_state.analysis_running = False

elif pending_action == "cache" and pending_result:
    progressive_display(
        pending_result,
        scout_placeholder,
        challenger_placeholder,
        strategist_placeholder,
        decision_placeholder,
        disagreement_placeholder,
        verdict_placeholder,
        strategic_brief_placeholder,
    )

elif st.session_state.final_result:
    render_disagreement_table(disagreement_placeholder, st.session_state.final_result)
    render_decision_card(verdict_placeholder, st.session_state.final_result)
    render_strategic_brief(strategic_brief_placeholder, st.session_state.final_result)


st.divider()
with st.expander("📋 Analysis History", expanded=False):
    history_rows = fetch_history()
    if history_rows:
        table_rows = [
            {
                "When": format_created_at(row.get("created_at", "")),
                "Question": truncate_question(row.get("question", "")),
                "Decision": format_history_decision(row.get("decision", "")),
                "Confidence": format_confidence(row.get("confidence_pct", "")),
                "Threat": row.get("threat_score", ""),
                "Opp": row.get("opportunity_score", ""),
            }
            for row in history_rows
        ]
        st.dataframe(table_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("No analyses yet.")

st.markdown("---")
st.caption(
    "PROMETHEUS · Built for AI Agent Olympics @ Milan AI Week 2026 · "
    "Gemini 2.5 Flash + Google Search Grounding · Deployed on Vultr Cloud"
)
