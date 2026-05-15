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
            --prom-bg: #0F0F0F;
            --prom-panel: #111111;
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
            background: #F59E0B;
            color: #111111;
            font-weight: 800;
            transition: transform 160ms ease, filter 160ms ease;
        }

        div[data-testid="stButton"] > button:hover {
            filter: brightness(1.06);
            border-color: #F59E0B;
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
            color: #F59E0B;
            letter-spacing: 4px;
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
            border-radius: 8px;
            padding: 16px;
            border: 2px solid;
            background: #111111;
            min-height: 360px;
            height: 100%;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.035);
        }

        .agent-panel.scout { border-color: #3B82F6; }
        .agent-panel.challenger { border-color: #F97316; }
        .agent-panel.strategist { border-color: #22C55E; }
        .agent-panel.decision-gate { border-color: #A855F7; }

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
        .status-running { background: #F59E0B; color: #111111; }
        .status-scout { background: #3B82F6; color: #FFFFFF; }
        .status-challenger { background: #F97316; color: #111111; }
        .status-strategist { background: #22C55E; color: #111111; }
        .status-decision { background: #A855F7; color: #FFFFFF; }
        .status-complete { background: #22C55E; color: #111111; }

        .panel-output {
            max-height: 300px;
            overflow-y: auto;
            padding: 12px;
            border-radius: 8px;
            background: #0F0F0F;
            border: 1px solid #262626;
            color: #D4D4D4;
            font-size: 0.9rem;
            line-height: 1.55;
            min-height: 214px;
        }

        .panel-output strong { color: #FFFFFF; }

        .empty-output {
            color: #737373;
            font-style: italic;
        }

        .decision-verdict-card {
            margin: 24px 0;
            border: 3px solid;
            border-radius: 12px;
            padding: 32px;
            background: #111111;
            text-align: center;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.045);
        }

        .decision-verdict {
            font-size: 4rem;
            font-weight: 900;
            line-height: 1;
            margin-bottom: 10px;
            font-family: "JetBrains Mono", monospace;
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
            background: #262626;
            border: 1px solid #333333;
        }

        .confidence-fill {
            height: 100%;
            border-radius: 999px;
        }

        .decision-rule {
            height: 1px;
            background: #2A2A2A;
            margin: 24px 0;
        }

        .decision-rationale {
            color: #E5E5E5;
            max-width: 960px;
            margin: 0 auto 18px;
            line-height: 1.65;
        }

        .decision-condition {
            color: #BDBDBD;
            margin-top: 8px;
            font-size: 0.95rem;
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
            border: 1px solid #2A2A2A;
            border-radius: 8px;
            padding: 16px;
            background: #111111;
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
            background: #262626;
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
            background: #1A1A1A;
            border-radius: 0 8px 8px 0;
        }

        .recommendation-index {
            color: #F59E0B;
            font-weight: 800;
        }

        .cache-badge {
            color: #F59E0B;
            font-weight: 700;
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
    title = agent_header(agent_name, output_text)
    placeholder.markdown(
        f"""
        <div class="agent-panel {kind}">
            <div class="agent-header">
                <div class="agent-title {kind}">{title}</div>
                <span class="status-badge {status_class}">{status_label}</span>
            </div>
            <div class="agent-caption">{caption}</div>
            <div class="{output_class}">{markdown_to_panel_html(output)}</div>
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
        st.markdown("### ⚔️ Where They Disagreed")
        st.caption("Scout's claim → Challenger's objection → Strategist's resolution")
        disagreement_rows = [
            {
                "Scout claimed": row["scout_claim"],
                "Challenger objected": row["challenger_objection"],
                "Resolved as": row["strategist_resolution"],
            }
            for row in result["disagreements"]
        ]
        st.dataframe(disagreement_rows, use_container_width=True, hide_index=True)


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

    st.session_state.disagreements = result["disagreements"]
    render_disagreement_table(disagreement_placeholder, result)
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

panel_1, panel_2, panel_3, panel_4 = st.columns([1, 1, 1, 1])
with panel_1:
    scout_placeholder = st.empty()
with panel_2:
    challenger_placeholder = st.empty()
with panel_3:
    strategist_placeholder = st.empty()
with panel_4:
    decision_placeholder = st.empty()

disagreement_placeholder = st.empty()
verdict_placeholder = st.empty()
strategic_brief_placeholder = st.empty()
spinner_placeholder = st.empty()

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
