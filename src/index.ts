export default {
  async fetch(request: Request, env: any, ctx: any): Promise<Response> {
    const url = new URL(request.url);

    // DEINE SERVER-IP HIER EINTRAGEN (Wo die app.py tatsächlich läuft)
    // Wenn du lokal testest, nutze deine öffentliche IP / Domain oder deinen Docker-Host
    const BACKEND_URL = "http://DEINE_SERVER_IP_ODER_DOMAIN:PORT"; 

    // Erstelle die Ziel-URL für den Flask-Server
    const targetUrl = new URL(url.pathname + url.search, BACKEND_URL);

    // Kopiere die Original-Header
    const newHeaders = new Headers(request.headers);
    
    // Wichtig für WebSockets / Socket.IO: WebSocket-Upgrade-Header beibehalten
    if (request.headers.get("Upgrade")?.toLowerCase() === "websocket") {
      return fetch(targetUrl.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.body,
      });
    }

    // Standard HTTP-Anfragen weiterleiten
    const modifiedRequest = new Request(targetUrl.toString(), {
      method: request.method,
      headers: newHeaders,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
      redirect: "manual"
    });

    try {
      const response = await fetch(modifiedRequest);
      return response;
    } catch (error) {
      return new Response(`Fehler beim Verbinden mit dem Flask-Backend: ${error}`, { status: 502 });
    }
  },
};