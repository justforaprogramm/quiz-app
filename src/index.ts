import { Hono } from 'hono'

const app = new Hono()

app.get('/', (c) => {
  return c.json({ status: 'online', project: 'quiz-app-ts' })
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