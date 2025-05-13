import os
import requests
from uuid import uuid4
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

# If you use a local .env for dev, uncomment the next two lines:
# from dotenv import load_dotenv
# load_dotenv()

# Environment (set these on Render or in your .env)
SUPABASE_URL         = os.getenv("SUPABASE_URL", "https://oiymijqkfjxuwxxdofmq.supabase.co")
SUPABASE_ANON_KEY    = os.getenv("SUPABASE_ANON_KEY", "<your-anon-key>")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "<your-service-role-key>")
REDIRECT_URL         = os.getenv("REDIRECT_URL", "http://localhost:5173")

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

# Health check at root
@app.get("/")
def read_root():
    return {"message": "Math Agent Backend is running!"}

# Sign-up via Supabase Auth
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

# Login via Supabase Auth
@app.post("/login")
def login_user(data: LoginData):
    payload = {"email": data.email, "password": data.password}
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    res = requests.post(url, headers=ANON_HEADERS, json=payload)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Login failed"))
    return res.json()

# Practice quiz: start a session and get one random question
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

# Practice quiz: record an answer, adjust difficulty, return next question
@app.post("/quiz/practice/answer")
def answer_practice(data: PracticeAnswer):
    # Fetch the original question to know correct answer & difficulty
    url_q = (
        f"{SUPABASE_URL}/rest/v1/questions"
        f"?select=id,correct,difficulty&id=eq.{data.question_id}"
    )
    res_q = requests.get(url_q, headers=ANON_HEADERS)
    if res_q.status_code != 200 or not res_q.json():
        raise HTTPException(status_code=404, detail="Question not found")
    q = res_q.json()[0]
    is_correct = data.answer == q["correct"]

    # Record progress
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

    # Compute next difficulty
    diff = q["difficulty"]
    next_diff = max(1, min(5, diff + (1 if is_correct else -1)))

    # Try to fetch a question at that difficulty, fallback to any random
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
