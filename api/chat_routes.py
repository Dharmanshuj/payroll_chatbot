from database.db import get_connection
from dotenv import load_dotenv
load_dotenv()
import os
import uuid
from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from database.db import get_connection

from agents.agents import run_salary_agent
from services.security_service import get_current_user
from services.auth_services import hash_password, verify_password, create_access_token

router = APIRouter()

# Admin login credentials come from the environment (see .env), not hardcoded here.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# --- Schemas ---
class QueryRequest(BaseModel):
    query: str  

class UserCredentials(BaseModel):
    empno: str
    password: str

# --- Endpoints ---
@router.get("/debug-routes")
def get_routes():
    return [route.path for route in router.routes]

@router.post("/login")
# Change the argument to use OAuth2PasswordRequestForm
async def login(credentials: OAuth2PasswordRequestForm = Depends()):
    # ADMIN login (credentials sourced from ADMIN_USERNAME / ADMIN_PASSWORD in the environment)
    if (
        ADMIN_USERNAME
        and ADMIN_PASSWORD
        and credentials.username == ADMIN_USERNAME
        and credentials.password == ADMIN_PASSWORD
    ):
        token = create_access_token("ADMIN", "Administrator")
        return {"access_token": token, "token_type": "bearer"}

    conn = get_connection()
    users_db = conn.cursor()

    users_db.execute(
        "SELECT empno, name, hashed_password FROM employee WHERE empno = %s",
        (credentials.username,)
    )

    user = users_db.fetchone()
    conn.close()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid employee ID")

    empno, name, hashed_password_db = user

    if not hashed_password_db:
        raise HTTPException(status_code=400, detail="User not registered")

    if not verify_password(credentials.password, hashed_password_db):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(empno, name)

    return {"access_token": token, "token_type": "bearer"}

    # # Swagger sends 'username' and 'password' inside the 'credentials' object
    # user = users_db.get(credentials.username)
    
    # if not user or not verify_password(credentials.password, user["hashed_password"]):
    #     raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # # Generate token using the stored emp_id
    # token = create_access_token(user["emp_id"], credentials.username)
    
    # return {"access_token": token, "token_type": "bearer"}

@router.post("/ask-me/stream")
async def ask_payroll_stream(
    request: QueryRequest, 
    user: dict = Depends(get_current_user)
):
    import json
    
    # if request.employee_id != user.get("empno"):
    #     raise HTTPException(status_code=403, detail="Unauthorized access to this employee ID")

    empno = user.get("empno")
    if not empno:
        raise HTTPException(status_code=401, detail="Unable to determine employee number from token")

    session_id = empno
    
    async def stream_generator():
        async for chunk in run_salary_agent(request.query, empno, session_id):
            payload = json.dumps({"text": chunk})
            yield f"data: {payload}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
