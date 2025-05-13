# main.py
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import requests

SUPABASE_URL = "https://oiymijqkfjxuwxxdofmq.supabase.co"
SUPABASE_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9peW1panFrZmp4dXd4eGRvZm1xIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDY4MDEwNzksImV4cCI6MjA2MjM3NzA3OX0.SESgl6jpKX5SW2k9oHTf0TH1H7m5fGY9L8SEb86TUV0"

AUTH_HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json"
}

app = FastAPI()

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class SignUpData(BaseModel):
    email: EmailStr
    password: str

ALLOWED_DOMAINS = ["school.edu", "college.edu", "avalialearning.com","gmail.com"]

# Routes
@app.post("/signup")
def signup_user(data: SignUpData):
    domain = data.email.split("@")[1]
    if domain not in ALLOWED_DOMAINS:
        raise HTTPException(status_code=400, detail="Please use an official email ID")

    payload = {
        "email": data.email,
        "password": data.password
    }
    res = requests.post(f"{SUPABASE_URL}/auth/v1/signup", headers=AUTH_HEADERS, json=payload)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Signup failed"))

    return {"message": "Signup successful. Please check your email to verify."}


@app.post("/login")
def login_user(data: SignUpData):
    payload = {
        "email": data.email,
        "password": data.password
    }
    res = requests.post(f"{SUPABASE_URL}/auth/v1/token?grant_type=password", headers=AUTH_HEADERS, json=payload)
    if res.status_code != 200:
        raise HTTPException(status_code=res.status_code, detail=res.json().get("msg", "Login failed"))

    return res.json()
@app.get("/")
def read_root():
    return {"message": "Math Agent Backend is running!"}
