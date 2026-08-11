"""LangGraph pipeline: 5 agents in sequence sharing IncidentState.

graph.stream(state, stream_mode="updates") yields {node_name: delta}
after each node completes. The FastAPI SSE endpoint maps each yield
directly to one event — no callbacks, no threading.
"""

from langgraph.graph import StateGraph, END
from agents.state import IncidentState
from agents.error_analyzer import error_analyzer_node
from agents.root_cause_investigator import root_cause_node
from agents.historical_pattern_agent import historical_pattern_node
from agents.fix_suggester import fix_suggester_node
from agents.report_writer import report_writer_node


def build_graph():
    g = StateGraph(IncidentState)

    g.add_node("error_analyzer", error_analyzer_node)
    g.add_node("root_cause_investigator", root_cause_node)
    g.add_node("historical_pattern", historical_pattern_node)
    g.add_node("fix_suggester", fix_suggester_node)
    g.add_node("report_writer", report_writer_node)

    g.add_edge("error_analyzer", "root_cause_investigator")
    g.add_edge("root_cause_investigator", "historical_pattern")
    g.add_edge("historical_pattern", "fix_suggester")
    g.add_edge("fix_suggester", "report_writer")
    g.add_edge("report_writer", END)

    g.set_entry_point("error_analyzer")

    return g.compile()