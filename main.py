import os
import requests
from uuid import uuid4
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# Environment (filled directly for deployment)
SUPABASE_URL = "https://oiymijqkfjxuwxxdofmq.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9peW1panFrZmp4dXd4eGRvZm1xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY4MDEwNzksImV4cCI6MjA2MjM3NzA3OX0.SESgl6jpKX5SW2k9oHTf0TH1H7m5fGY9L8SEb86TUV0"
SUPABASE_SERVICE_KEY = SUPABASE_ANON_KEY
REDIRECT_URL = "http://localhost:5173"

# Headers for Supabase REST
ANON_HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}
SERVICE_HEADERS = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Allowed sign-up domains
ALLOWED_DOMAINS = ["school.edu", "college.edu"]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class SignUpData(BaseModel):
    email: EmailStr
    password: str

class LoginData(BaseModel):
    email: EmailStr
    password: str

class PracticeStart(BaseModel):
    user_id: str

class PracticeAnswer(BaseModel):
    user_id: str
    question_id: int
    answer: str
    time_taken: Optional[int] = None

# Health check
@app.get("/")
def read_root():
    return {"message": "Math Agent Backend is running!"}

# Signup route
@app.post("/signup")
def signup_user(data: SignUpData):
    domain = data.email.split("@")[1]
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail="Please use an official email ID")
    payload = {"email": data.email, "password": data.password}
    url = f"{SUPABASE_URL}/auth/v1/signup?redirect_to={REDIRECT_URL}"
    res = requests.post(url, headers=ANON_HEADERS, json=payload)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Signup failed"))
    return {"message": "Signup successful. Please check your email to verify."}

# Login route
@app.post("/login")
def login_user(data: LoginData):
    payload = {"email": data.email, "password": data.password}
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    res = requests.post(url, headers=ANON_HEADERS, json=payload)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Login failed"))
    return res.json()

# Practice start route
@app.post("/quiz/practice/start")
def start_practice(data: PracticeStart):
    url = (
        f"{SUPABASE_URL}/rest/v1/questions"
        "?select=id,prompt,option_a,option_b,option_c,option_d,correct,difficulty"
        "&order=random()&limit=1"
    )
    res = requests.get(url, headers=ANON_HEADERS)
    if res.status_code != 200 or not res.json():
        raise HTTPException(status_code=500, detail="Could not fetch question")
    question = res.json()[0]
    session_id = str(uuid4())
    return {"session_id": session_id, "question": question}

# Practice answer route
@app.post("/quiz/practice/answer")
def answer_practice(data: PracticeAnswer):
    url_q = (
        f"{SUPABASE_URL}/rest/v1/questions"
        f"?select=id,correct,difficulty&id=eq.{data.question_id}"
    )
    res_q = requests.get(url_q, headers=ANON_HEADERS)
    if res_q.status_code != 200 or not res_q.json():
        raise HTTPException(status_code=404, detail="Question not found")
    q = res_q.json()[0]
    is_correct = data.answer == q["correct"]

    payload = {
        "user_id": data.user_id,
        "question_id": data.question_id,
        "correct": is_correct,
        "time_taken_s": data.time_taken or 0,
    }
    res_ins = requests.post(
        f"{SUPABASE_URL}/rest/v1/user_progress",
        headers=SERVICE_HEADERS,
        json=payload,
    )
    if res_ins.status_code not in (200, 201):
        raise HTTPException(status_code=res_ins.status_code, detail="Failed to record progress")

    diff = q["difficulty"]
    next_diff = max(1, min(5, diff + (1 if is_correct else -1)))

    url_n = (
        f"{SUPABASE_URL}/rest/v1/questions"
        f"?select=id,prompt,option_a,option_b,option_c,option_d,correct,difficulty"
        f"&difficulty=eq.{next_diff}&order=random()&limit=1"
    )
    res_n = requests.get(url_n, headers=ANON_HEADERS)
    if not res_n.json():
        url_f = (
            f"{SUPABASE_URL}/rest/v1/questions"
            "?select=id,prompt,option_a,option_b,option_c,option_d,correct,difficulty"
            "&order=random()&limit=1"
        )
        res_n = requests.get(url_f, headers=ANON_HEADERS)
    next_q = res_n.json()[0] if res_n.json() else None

    return {
        "correct": is_correct,
        "correct_answer": q["correct"],
        "next_question": next_q,
    }
