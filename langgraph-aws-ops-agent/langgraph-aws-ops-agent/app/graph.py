import os
from typing import Any

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_mcp_adapters.client import MultiServerMCPClient


SYSTEM_PROMPT = """You are an AWS SRE incident investigation agent.

Your job is to investigate EC2, CloudWatch and EKS/Kubernetes incidents using
the available MCP tools.

Rules:
1. Use evidence before making conclusions.
2. Prefer checking multiple relevant signals.
3. Never invent metrics, logs, pod states, events or AWS resources.
4. Distinguish observed evidence from hypotheses.
5. If a requested target is not configured, say what information is missing.
6. For EKS incidents, inspect cluster/nodes/pods/events/logs as appropriate.
7. For EC2 incidents, inspect instance state and CloudWatch metrics.
8. For CloudWatch incidents, inspect alarms, metrics and logs when available.
9. Give concrete next verification commands/checks.
10. Do not perform destructive changes. All tools are read-only.

Final incident reports should use:

## Summary
## Evidence
## Likely causes / hypotheses
## What is not yet proven
## Next troubleshooting steps
## Safe remediation options
"""


def mcp_connections() -> dict[str, dict[str, Any]]:
    return {
        "cloudwatch": {
            "url": os.getenv("CLOUDWATCH_MCP_URL", "http://localhost:8001/mcp"),
            "transport": "streamable_http",
        },
        "ec2": {
            "url": os.getenv("EC2_MCP_URL", "http://localhost:8002/mcp"),
            "transport": "streamable_http",
        },
        "eks": {
            "url": os.getenv("EKS_MCP_URL", "http://localhost:8003/mcp"),
            "transport": "streamable_http",
        },
    }


async def build_graph():
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required")

    client = MultiServerMCPClient(
        mcp_connections(),
        tool_name_prefix=True,
        handle_tool_errors=True,
    )

    tools = await client.get_tools()

    model = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        temperature=0,
        google_api_key=os.environ["GEMINI_API_KEY"],
    )

    model_with_tools = model.bind_tools(tools)

    def call_model(state: MessagesState):
        messages = state["messages"]
        if not messages or messages[0].type != "system":
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition, ["tools", END])
    builder.add_edge("tools", "agent")

    return builder.compile()
