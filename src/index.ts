export default {
  async fetch(request: Request, env: any, ctx: any): Promise<Response> {
    const url = new URL(request.url);

    // Routen für die einzelnen HTML-Seiten definieren
    if (url.pathname === "/" || url.pathname === "/index.html") {
      return env.ASSETS.fetch(new Request(new URL("/index.html", request.url)));
    }
    if (url.pathname === "/gamemaster") {
      return env.ASSETS.fetch(new Request(new URL("/gamemaster.html", request.url)));
    }
    if (url.pathname === "/player") {
      return env.ASSETS.fetch(new Request(new URL("/player.html", request.url)));
    }

    // Falls Socket.IO-Verbindungen reinkommen (für Echtzeit-Events)
    if (url.pathname.startsWith("/socket.io")) {
      return new Response("Socket.IO wird auf Serverless Edge vorbereitet.", { status: 200 });
    }

    // Standard-Fallback für alle anderen Assets (CSS, JS-Dateien aus dem public-Ordner)
    return env.ASSETS.fetch(request);
  },
};