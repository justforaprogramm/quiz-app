from fastapi import FastAPI
from workers import AsgiWorker

app = FastAPI()

@app.get("/")
def read_root():
    # Hier stand vermutlich noch "-ts" drin, ändern wir zu Python!
    return {"status": "online", "project": "quiz-app"}

@app.get("/quiz")
def get_quiz():
    return [
        {
            "id": 1, 
            "question": "Welches Protokoll nutzt Cloudflare standardmäßig?", 
            "options": ["HTTP/3", "FTP", "SMTP"], 
            "answer": "HTTP/3"
        }
    ]

worker = AsgiWorker(app)