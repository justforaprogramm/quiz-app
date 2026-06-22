from fastapi import FastAPI
from workers import AsgiWorker

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the Quiz App API on the Edge!"}

@app.get("/quiz")
def get_quiz():
    return [
        {"id": 1, "question": "What is 2+2?", "options": ["3", "4", "5"], "answer": "4"}
    ]

# Crucial for Cloudflare Workers to handle the request routing
worker = AsgiWorker(app)
