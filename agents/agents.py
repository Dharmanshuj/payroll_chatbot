import os
import json
import logging
import operator
from typing import TypedDict, Annotated

from google.genai.errors import ServerError
from langchain_core.exceptions import ModelRateLimitError
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from langchain_core.runnables.config import RunnableConfig

# ── Tools (via Spring Boot MCP Server) ────────────────────────────────────────
from tools.document_tool import search_documents
from tools.mcp_tool import (
    get_all_employees_salary_information,
    get_employee_by_id,
    get_attendance,
    get_salary_payment,
    get_all_employees_data,
    admin_get_monthly_metrics,
    get_all_attendance_for_employee,
)


logger = logging.getLogger(__name__)

# ── LLM ──────────────────────────────────────────────────────────────────────
# Pinned to a specific dated model rather than a "-latest" alias on purpose:
# gemini-flash-latest previously auto-shifted to gemini-3.8-flash, whose free-tier
# quota is only 20 requests/day. gemini-3.5-flash-lite gives 500/day (still plenty
# capable for this app's structured tool-calling), and won't change under us again
# without an explicit edit here.
_base_llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=os.environ.get("GEMINI_API_KEY"),
)

# ServerError covers Gemini's transient 5xx responses (e.g. 503 UNAVAILABLE
# "model is currently experiencing high demand"). Retry a few times with
# exponential backoff before letting it surface as a user-facing failure.
# Applied per call-site (rather than wrapping _base_llm directly) because
# Runnable.with_retry() drops .bind_tools(), which payroll_logic/admin_logic need.
_RETRY_KWARGS = dict(
    retry_if_exception_type=(ServerError,),
    wait_exponential_jitter=True,
    stop_after_attempt=4,
)
_base_llm_retry = _base_llm.with_retry(**_RETRY_KWARGS)

# Payroll tools (served by Spring Boot via MCP)
PAYROLL_TOOLS = [
    get_employee_by_id,
    get_attendance,
    get_salary_payment,
    get_all_attendance_for_employee,
    search_documents
]

# Admin tools (served by Spring Boot via MCP)
ADMIN_TOOLS = [
    get_all_employees_data,
    get_all_employees_salary_information,
    admin_get_monthly_metrics,
]

# Policy tool
POLICY_TOOLS = [
    search_documents,
]

def _extract_text(content) -> str:
    """
    Normalize an AIMessage.content value into plain text.

    Older Gemini models returned a plain string. Newer ones (e.g.
    gemini-flash-latest) can return a list of content blocks instead, e.g.
    [{"type": "text", "text": "...", "extras": {...}}], so calling .strip()
    directly on .content breaks with "'list' object has no attribute 'strip'".
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(block["text"])
        return "".join(parts)
    return str(content) if content else ""


# ── Shared State ──────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    query: str
    emp_id: str
    final_answer: str
    next_node: str
    messages: Annotated[list, operator.add]


# ── Supervisor ────────────────────────────────────────────────────────────────
async def supervisor(state: AgentState):
    """Routes the query to the correct specialist node."""
    query = state["query"].lower()
    recent_history = state.get("messages", [])[-4:]
    history_text = "\n".join(
        [f"{type(m).__name__}: {_extract_text(m.content)[:150]}" for m in recent_history]
    )

    prompt = f"""
You are an intelligent HR Agent Router.
Analyze the user's query and categorize their intent into exactly ONE of the following categories:

- policy_node  : Questions about company rules, HR policies, handbooks, time off, leave, benefits, or HOW salary components/calculations are determined.
- admin_node   : Requests to view data, salaries, or records for ALL employees or everyone.
- payroll_node : Questions about the user's personal profile (name, role, etc.), personal attendance, present/absent days, specific salary, personal payslips, deductions, or compensation.

Recent Conversation History:
{history_text}

User Query: "{query}"

Respond with ONLY the exact category name. No quotes, no extra text.
"""
    response = await _base_llm_retry.ainvoke([HumanMessage(content=prompt)])
    route = _extract_text(response.content).strip().strip('"').strip("'").lower()

    valid_routes = ["policy_node", "admin_node", "payroll_node"]
    if route in valid_routes:
        return {"next_node": route}

    # Fallback
    if state["emp_id"] == "ADMIN":
        return {"next_node": "admin_node"}
    return {"next_node": "payroll_node"}


# ── Agentic Payroll Node ──────────────────────────────────────────────────────
PAYROLL_SYSTEM_PROMPT = """You are an intelligent HR and Payroll Assistant.

The current demo year is 2026.

You have access to the following tools. Use them autonomously to answer the user's question:

- get_employee_by_id()                  → Employee profile (name, role, salary components, bank details, etc.)
- get_attendance(month, year)           → Attendance for a specific month
- get_salary_payment(attendance_id)     → Actual salary paid for a specific attendance record
- get_all_attendance_for_employee(year) → All attendance records for the year
- search_documents(query)               → Search the HR handbook for company policies

## Salary Structure Logic (If asked for exact calculations)
- Basic Salary is the foundation.
- HRA = 50% of Basic (Metro) or 40% of Basic (Non-Metro).
- EPF = 12% of Basic.
- Conveyance & Medical = Fixed amounts, or 5% of Basic.
- Special Allowance = Balancing figure to reach target gross.
- Gross = Basic + HRA + Conveyance + Medical + Special.
- Total Deductions = EPF + Health Insurance + PT (~200) + TDS.
- Per Day Salary = Gross / Total Days.
- Earned Salary = Per Day Salary * Present Days.
- Final Net Salary = Earned Salary - Total Deductions.

## Decision Logic
1. ALWAYS start by calling `get_employee_by_id` to get the employee's profile.
2. If the user asks about a SPECIFIC month → call `get_attendance` then `get_salary_payment`.
3. If the user asks about all months or YTD → call `get_all_attendance_for_employee`, then call `get_salary_payment` for each record.
4. If asked to show exact calculations, use the Employee details and the Salary Structure Logic to lay out the math step by step.
5. Combine all retrieved data and give a clear, professional answer. 
6. ALWAYS address the user in the second person ("You", "Your"). Do NOT use "I" or "My" when referring to the user's data (e.g., say "You earned" instead of "I earned").
7. If the user asks a follow-up question, or asks you to repeat or clarify something, use the conversation history to provide conversational continuity.

Be concise. Do not reveal raw tool outputs. Format numbers with ₹ prefix.
"""

async def payroll_logic(state: AgentState, config: RunnableConfig):
    """
    Agentic payroll node: the LLM decides which tools to call and loops
    until it has sufficient information to produce a final answer.
    """
    emp_id = state["emp_id"]

    # Build the ReAct agent graph on-the-fly (lightweight, no extra state)
    llm_with_tools = _base_llm.bind_tools(PAYROLL_TOOLS).with_retry(**_RETRY_KWARGS)
    agent = create_react_agent(llm_with_tools, PAYROLL_TOOLS)

    # Note: emp_id is injected via the graph config so tools can read it automatically.
    enriched_query = f"User question: {state['query']}"

    messages = [
        SystemMessage(content=PAYROLL_SYSTEM_PROMPT),
        *state.get("messages", []),
        HumanMessage(content=enriched_query),
    ]

    result = await agent.ainvoke({"messages": messages}, config)

    # The final AIMessage is the last message in the result
    final_message = result["messages"][-1]
    answer = _extract_text(final_message.content).strip() or "I'm sorry, I couldn't formulate a proper response based on the available data."

    return {
        "final_answer": answer,
        "messages": [
            HumanMessage(content=state["query"]),
            AIMessage(content=answer),
        ],
    }


# ── Agentic Admin Node ────────────────────────────────────────────────────────
ADMIN_SYSTEM_PROMPT = """You are an HR Admin Dashboard Assistant.

The current demo year is 2026.

You have access to the following tools. Use them to answer the admin's question:

- get_all_employees_data()                          → Base info for all employees
- get_all_employees_salary_information()            → Comprehensive salary structure for all employees
- admin_get_monthly_metrics(month, year)            → Attendance + salary metrics for all employees

## Decision Logic
1. For questions about salary structure, salary breakdown, or compensation → call `get_all_employees_salary_information`.
2. For questions about ALL employees' general info (name, dept, designation) → call `get_all_employees_data`.
3. For questions about a specific month's payroll/attendance → call `admin_get_monthly_metrics(month, year)`.
4. For broad year-level questions → call `admin_get_monthly_metrics(month=None, year=<year>)`.
5. Combine data and provide a clear, tabular summary when there are multiple employees.
6. If the user asks to clarify or repeat a previous response, use the conversation history.

Be concise and professional.
"""

async def admin_logic(state: AgentState, config: RunnableConfig):
    """
    Agentic admin node: only accessible by ADMIN. LLM chooses tools autonomously.
    """
    if state["emp_id"] != "ADMIN":
        return {"final_answer": "Unauthorized Access. Only the ADMIN can query data for all employees."}

    llm_with_tools = _base_llm.bind_tools(ADMIN_TOOLS).with_retry(**_RETRY_KWARGS)
    agent = create_react_agent(llm_with_tools, ADMIN_TOOLS)

    messages = [
        SystemMessage(content=ADMIN_SYSTEM_PROMPT),
        *state.get("messages", []),
        HumanMessage(content=state["query"]),
    ]

    result = await agent.ainvoke({"messages": messages}, config)
    final_message = result["messages"][-1]
    answer = _extract_text(final_message.content).strip() or "I'm sorry, the admin query returned no text response."

    return {
        "final_answer": answer,
        "messages": [
            HumanMessage(content=state["query"]),
            AIMessage(content=answer),
        ],
    }


# ── Policy Node (RAG — no tool loop needed) ───────────────────────────────────
async def policy_logic(state: AgentState, config: RunnableConfig):
    """
    Retrieves information on how the salary components are determined/calculated and relevant HR policy documents via RAG and answers the question.
    """
    docs = search_documents.func(state["query"])

    prompt = f"""You are an HR Policy Assistant. Use the retrieved policy documents below to answer the user's question. Refers the data as policies rather than documents

Documents:
{docs}

Question:
{state['query']}

Instructions:
- Answer strictly based on the provided documents.
- If the documents don't contain the answer, politely say so.
"""
    past_messages = state.get("messages", [])
    response = await _base_llm_retry.ainvoke(past_messages + [HumanMessage(content=prompt)], config)
    answer = _extract_text(response.content)

    return {
        "final_answer": answer,
        "messages": [
            HumanMessage(content=state["query"]),
            AIMessage(content=answer),
        ],
    }


# ── Graph Construction ────────────────────────────────────────────────────────
memory = MemorySaver()

def create_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor)
    workflow.add_node("payroll_node", payroll_logic)
    workflow.add_node("admin_node", admin_logic)
    workflow.add_node("policy_node", policy_logic)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges(
        "supervisor",
        lambda state: state["next_node"],
        {
            "payroll_node": "payroll_node",
            "admin_node": "admin_node",
            "policy_node": "policy_node",
        },
    )
    workflow.add_edge("payroll_node", END)
    workflow.add_edge("admin_node", END)
    workflow.add_edge("policy_node", END)

    return workflow.compile(checkpointer=memory)


# ── Entry Point ───────────────────────────────────────────────────────────────
async def run_salary_agent(query: str, emp_id: str, session_id: str):
    graph = create_graph()
    initial_state = {
        "query": query,
        "emp_id": emp_id,
        "final_answer": "",
        "next_node": "",
        "messages": [],
    }
    config = {"configurable": {"thread_id": session_id, "emp_id": emp_id}}

    try:
        async for event in graph.astream(initial_state, config):
            for node_name, output in event.items():
                if "final_answer" in output:
                    ans = output["final_answer"]
                    if not ans or not str(ans).strip():
                        yield "I apologize, but I received an empty response. Please try again."
                    else:
                        yield str(ans)
    except ServerError:
        logger.exception("Gemini API unavailable after retries (emp_id=%s)", emp_id)
        yield "The AI service is currently experiencing high demand. Please try again in a moment."
    except ModelRateLimitError:
        logger.exception("Gemini API quota exhausted (emp_id=%s)", emp_id)
        yield "The AI service has reached its usage quota for now (this project is on Gemini's free tier, capped at 20 requests/day per model). Please try again later, or upgrade the Gemini API plan to raise the limit."
    except Exception:
        logger.exception("Unhandled error in run_salary_agent (emp_id=%s)", emp_id)
        yield "An internal server error occurred while analyzing your request. Please try again."
