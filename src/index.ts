import { Hono } from 'hono'

const app = new Hono()

app.get('/', (c) => {
  // Hier das "-ts" entfernen oder den Namen anpassen
  return c.json({ status: 'online', project: 'quiz-app' })
})

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