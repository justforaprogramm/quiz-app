import { Hono } from 'hono'

const app = new Hono()

// 1. Die Hauptseite liefert jetzt echtes HTML + CSS + JavaScript aus
app.get('/', (c) => {
  return c.html(`
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Quiz App</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #121212; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .quiz-card { background: #1e1e1e; padding: 2.5rem; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; max-width: 450px; width: 90%; }
            h2 { color: #f6821f; margin-bottom: 1.5rem; }
            .options-container { display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1.5rem; }
            button { background: #2a2a2a; color: white; border: 2px solid #3a3a3a; padding: 0.75rem 1rem; border-radius: 8px; cursor: pointer; font-size: 1rem; transition: all 0.2s ease; text-align: left; }
            button:hover { background: #f6821f; border-color: #f6821f; transform: translateY(-2px); }
            .score { margin-top: 1.5rem; font-size: 0.9rem; color: #888; }
        </style>
    </head>
    <body>
        <div class="quiz-card">
            <h2 id="question">Lade Quizfrage...</h2>
            <div class="options-container" id="options"></div>
            <div class="score" id="feedback">Wähle eine Antwort aus!</div>
        </div>

        <script>
            async function loadQuiz() {
                try {
                    // Holt sich die Fragen dynamisch von deinem /quiz Endpoint
                    const res = await fetch('/quiz');
                    const data = await res.json();
                    const quiz = data[0]; 

                    document.getElementById('question').innerText = quiz.question;
                    const optionsDiv = document.getElementById('options');
                    optionsDiv.innerHTML = '';
                    
                    quiz.options.forEach(opt => {
                        const btn = document.createElement('button');
                        btn.innerText = opt;
                        btn.onclick = () => {
                            const feedback = document.getElementById('feedback');
                            if(opt === quiz.answer) {
                                feedback.innerHTML = '<span style="color: #4caf50; font-weight: bold;">Richtig! 🎉</span>';
                            } else {
                                feedback.innerHTML = '<span style="color: #f44336; font-weight: bold;">Falsch! ❌ Versuchs nochmal.</span>';
                            }
                        };
                        optionsDiv.appendChild(btn);
                    });
                } catch (err) {
                    document.getElementById('question').innerText = 'Fehler beim Laden des Quiz :(';
                }
            }
            loadQuiz();
        </script>
    </body>
    </html>
  `)
})

// 2. Dein Daten-Endpoint bleibt genau so, wie er ist
app.get('/quiz', (c) => {
  return c.json([
    {
      id: 1,
      question: "Welches Protokoll nutzt Cloudflare standardmäßig?",
      options: ["HTTP/3", "FTP", "SMTP"],
      answer: "HTTP/3"
    }
  ])
})

export default app