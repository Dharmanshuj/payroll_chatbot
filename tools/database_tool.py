from langchain.tools import tool
from typing import Optional

from database.db import get_connection

from security.validator import validate_query
from security.filter import filter_records
from security.masking import apply_masking
from security.audit_logger import log_tool_usage, log_security_event

@tool
def get_all_employees_data():
    """Query data for all employees. ONLY allowed for ADMIN user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT empno, name, dept, designation, net_pay
        FROM employee
    """)
    rows = cursor.fetchall()
    records = [{"empno": r[0], "name": r[1], "dept": r[2], "designation": r[3], "net_pay": r[4]} for r in rows]
    conn.close()
    return records


@tool
def admin_get_monthly_metrics(month: Optional[int] = None, year: Optional[int] = None):
    """Admin tool to get attendance and salary payments for all employees across a given month."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # If no month/year is specified, fetch the most recent global month deployed
    if month and year:
        query = """
            SELECT e.empno, e.name, a.total_days, a.present_days, a.absent_days, s.final_salary, a.month, a.year
            FROM employee e
            LEFT JOIN attendance a ON e.empno = a.empno AND a.month = %s AND a.year = %s
            LEFT JOIN salary_payment s ON a.id = s.attendance_id
        """
        cursor.execute(query, (month, year))
    elif year:
        query = """
            SELECT e.empno, e.name, a.total_days, a.present_days, a.absent_days, s.final_salary, a.month, a.year
            FROM employee e
            LEFT JOIN attendance a ON e.empno = a.empno AND a.year = %s
            LEFT JOIN salary_payment s ON a.id = s.attendance_id
        """
        cursor.execute(query, (year,))
    else:
        query = """
            SELECT e.empno, e.name, a.total_days, a.present_days, a.absent_days, s.final_salary, a.month, a.year
            FROM employee e
            LEFT JOIN attendance a ON e.empno = a.empno AND a.year = 2026
            LEFT JOIN salary_payment s ON a.id = s.attendance_id
        """
        cursor.execute(query)
            
    rows = cursor.fetchall()
    
    records = []
    for r in rows:
        records.append({
            "empno": r[0],
            "name": r[1],
            "total_days": r[2],
            "present_days": r[3],
            "absent_days": r[4],
            "inhand_net_pay": r[5],
            "month": r[6],
            "year": r[7]
        })
    conn.close()
    return records

@tool
def get_employee_by_id(emp_id: str):
    """Query employee by ID and return sanitized JSON record.
    emp_id is taken as input which is str and is employee id"""

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            name,
            dept,
            designation,
            bank_name,
            account_no,
            basic_salary,
            hra,
            conveyance,
            medical,
            special,
            gross_salary,
            epf,
            health_insurance,
            professional_tax,
            tds,
            total_deductions,
            net_pay
        FROM employee
        WHERE empno = %s
        """,
        (emp_id,)
    )

    r = cursor.fetchone()

    if not r:
        log_security_event("Unauthorized access attempt to employee data", details={"emp_id": emp_id})
        return "Employee not found."

    record = {
        "name": r[0],
        "department": r[1],
        "designation": r[2],
        "bank_name": r[3],
        "account_no": r[4],
        "basic_salary": r[5],
        "hra": r[6],
        "conveyance": r[7],
        "medical": r[8],
        "special": r[9],
        "gross_salary": r[10],
        "epf": r[11],
        "health_insurance": r[12],
        "professional_tax": r[13],
        "tds": r[14],
        "total_deductions": r[15],
        "net_pay": r[16]

    }

    #record = validate_query(record)
    record = filter_records([record])[0]

    record = apply_masking(record)

    # log_tool_usage("query_employee_by_id", details={"emp_id": emp_id})

    conn.close()

    return record

@tool
def get_attendance(emp_id: str, month: Optional[int] = None, year: Optional[int] = None):
    """
    Get attendance for employee for a specific month or year.
    """
    conn = get_connection()
    cursor = conn.cursor()

    if month and year:
        cursor.execute(
            """
            SELECT id, total_days, present_days, absent_days, month, year
            FROM attendance
            WHERE empno = %s AND month = %s AND year = %s
            """,
            (emp_id, month, year)
        )
    else:
        cursor.execute(
            """
            SELECT id, total_days, present_days, absent_days, month, year
            FROM attendance
            WHERE empno = %s
            ORDER BY year DESC, month DESC
            LIMIT 1
            """,
            (emp_id,)
        )

    r = cursor.fetchone()
    conn.close()

    if not r:
        return None

    return {
        "attendance_id": r[0],
        "total_days": r[1],
        "present_days": r[2],
        "absent_days": r[3],
        "month_recorded": r[4],
        "year_recorded": r[5]
    }
    
@tool
def get_salary_payment(attendance_id: int):
    """
    Fetch final in-hand salary based on attendance ID.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT final_salary
f        FROM salary_payment
        WHERE attendance_id = %s
        """,
        (attendance_id,)
    )

    r = cursor.fetchone()
    conn.close()

    if not r:
        return None

    return {
        "final_salary": r[0]
    }

@tool
def get_all_attendance_for_employee(emp_id: str, year: Optional[int] = None):
    """
    Get all attendance records for an employee across all months for a specific year.
    """
    conn = get_connection()
    cursor = conn.cursor()

    if year:
        cursor.execute(
            """
            SELECT id, total_days, present_days, absent_days, month, year
            FROM attendance
            WHERE empno = %s AND year = %s
            ORDER BY year DESC, month DESC
            """,
            (emp_id, year)
        )
    else:
        cursor.execute(
            """
            SELECT id, total_days, present_days, absent_days, month, year
            FROM attendance
            WHERE empno = %s
            ORDER BY year DESC, month DESC
            """,
            (emp_id,)
        )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    records = []
    for r in rows:
        records.append({
            "attendance_id": r[0],
            "total_days": r[1],
            "present_days": r[2],
            "absent_days": r[3],
            "month": r[4],
            "year": r[5]
        })

    return records
