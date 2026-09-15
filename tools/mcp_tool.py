"""
MCP Tool wrappers for the AI Agent.

Connects to the Spring Boot MCP server (via Streamable HTTP) and calls tools.
Each call runs in a dedicated daemon thread to avoid blocking application shutdown.
"""
import json
import asyncio
import concurrent.futures
import logging
import os
from typing import Optional

from langchain.tools import tool
from mcp.client.streamable_http import streamable_http_client
from mcp.client.session import ClientSession
from langchain_core.runnables.config import RunnableConfig

logger = logging.getLogger(__name__)

# ── Spring Boot MCP Server URL ───────────────────────────────────────────────
SPRING_MCP_URL = os.getenv("SPRING_MCP_URL", "http://localhost:8080/mcp")
MCP_OPERATION_TIMEOUT_SECONDS = int(os.getenv("MCP_OPERATION_TIMEOUT_SECONDS", "20"))
MCP_THREAD_TIMEOUT_SECONDS = int(os.getenv("MCP_THREAD_TIMEOUT_SECONDS", "25"))

# Thread pool with daemon=True to allow the process to exit even if threads are hanging
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# Hack to make ThreadPoolExecutor threads daemon-like for easier shutdown
# (ThreadPoolExecutor threads are not daemon by default and will block sys.exit)
def _daemon_executor_submit(fn, *args, **kwargs):
    def wrapper():
        return fn(*args, **kwargs)
    return _executor.submit(wrapper)


async def _call_mcp_tool(name: str, args: dict) -> str:
    """Connect to Spring Boot MCP server, call a tool, return the text result."""
    try:
        async with asyncio.timeout(MCP_OPERATION_TIMEOUT_SECONDS):
            async with streamable_http_client(SPRING_MCP_URL) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, args)
                    if result.content:
                        return result.content[0].text
                    return json.dumps({"error": "No result returned."})
    except asyncio.TimeoutError:
        logger.error(
            "MCP tool '%s' timed out after %ss (SPRING_MCP_URL=%s)",
            name, MCP_OPERATION_TIMEOUT_SECONDS, SPRING_MCP_URL,
        )
        return json.dumps({"error": f"MCP tool call timed out ({MCP_OPERATION_TIMEOUT_SECONDS}s). Is Spring Boot running?"})
    except Exception as e:
        logger.exception(
            "MCP tool '%s' failed (SPRING_MCP_URL=%s): %s",
            name, SPRING_MCP_URL, e,
        )
        return json.dumps({"error": f"MCP tool call failed: {str(e)}"})


def _run_in_thread(name: str, args: dict) -> str:
    """Run the async MCP call in a fresh event loop on a separate thread."""
    return asyncio.run(_call_mcp_tool(name, args))


def _run(name: str, args: dict) -> dict:
    """Call an MCP tool from any context (sync or async). Returns parsed JSON."""
    future = _executor.submit(_run_in_thread, name, args)
    try:
        raw = future.result(timeout=MCP_THREAD_TIMEOUT_SECONDS)
    except concurrent.futures.TimeoutError:
        logger.error(
            "MCP tool '%s' thread timed out after %ss", name, MCP_THREAD_TIMEOUT_SECONDS
        )
        return {"error": "Technical Timeout: The MCP thread took too long to respond."}
    except Exception as e:
        logger.exception("MCP tool '%s' thread failed: %s", name, e)
        return {"error": f"Technical Error: {str(e)}"}
        
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw_response": raw}


# ── Payroll Tools ────────────────────────────────────────────────────────────

@tool
def get_employee_by_id(config: RunnableConfig):
    """Query your employee profile and return sanitized JSON record. Do not pass any arguments."""
    emp_id = config.get("configurable", {}).get("emp_id")
    if not emp_id:
        return json.dumps({"error": "Employee ID not found in context."})
    return _run("get_employee_by_id", {"empId": emp_id})


@tool
def get_attendance(config: RunnableConfig, month: Optional[int] = None, year: Optional[int] = None):
    """Get your attendance for a specific month or year."""
    emp_id = config.get("configurable", {}).get("emp_id")
    if not emp_id:
        return json.dumps({"error": "Employee ID not found in context."})
    args = {"empId": emp_id, "month": month or 0, "year": year or 0}
    return _run("get_attendance", args)


@tool
def get_salary_payment(attendance_id: int):
    """Fetch final in-hand salary based on attendance ID."""
    return _run("get_salary_payment", {"attendanceId": attendance_id})


@tool
def get_all_attendance_for_employee(config: RunnableConfig, year: Optional[int] = None):
    """Get all your attendance records across all months for a specific year."""
    emp_id = config.get("configurable", {}).get("emp_id")
    if not emp_id:
        return json.dumps({"error": "Employee ID not found in context."})
    args = {"empId": emp_id, "year": year or 0}
    return _run("get_all_attendance_for_employee", args)


# ── Admin Tools ──────────────────────────────────────────────────────────────

@tool
def get_all_employees_data():
    """Query basic details for all employees. ONLY allowed for ADMIN user."""
    return _run("get_all_employees_data", {})

@tool
def get_all_employees_salary_information():
    """Admin tool to get comprehensive salary information for all employees. ONLY allowed for ADMIN user."""
    return _run("get_all_employees_salary_information", {})

@tool
def admin_get_monthly_metrics(month: Optional[int] = None, year: Optional[int] = None):
    """Admin tool to get attendance and salary payments for all employees across a given month. ONLY allowed for ADMIN user."""
    args = {"month": month or 0, "year": year or 0}
    return _run("admin_get_monthly_metrics", args)
