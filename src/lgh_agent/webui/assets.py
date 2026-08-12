from __future__ import annotations


WEBUI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>lgh_agent</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2937;
      --muted: #667085;
      --line: #d9dee7;
      --accent: #2563eb;
      --accent-strong: #1d4ed8;
      --tool: #ecfdf3;
      --tool-text: #067647;
      --error: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .shell {
      height: 100vh;
      display: grid;
      grid-template-rows: 56px 1fr auto;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
    }
    .mark {
      width: 28px;
      height: 28px;
      display: grid;
      place-items: center;
      border-radius: 6px;
      background: #111827;
      color: white;
      font-size: 14px;
    }
    .session {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }
    .session input {
      width: 160px;
      height: 32px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0 10px;
      color: var(--text);
      background: white;
    }
    main {
      overflow: auto;
      padding: 20px;
    }
    .messages {
      width: min(880px, 100%);
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .message {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
      background: var(--panel);
      white-space: pre-wrap;
      line-height: 1.55;
    }
    .message.user {
      border-color: #bcd2ff;
      background: #eff6ff;
    }
    .role {
      display: block;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }
    .tool-event {
      margin-top: 8px;
      border-radius: 6px;
      padding: 8px 10px;
      background: var(--tool);
      color: var(--tool-text);
      font-size: 13px;
      white-space: pre-wrap;
    }
    .composer {
      border-top: 1px solid var(--line);
      background: var(--panel);
      padding: 14px 20px;
    }
    form {
      width: min(880px, 100%);
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 10px;
      align-items: end;
    }
    textarea {
      width: 100%;
      min-height: 56px;
      max-height: 180px;
      resize: vertical;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      font: inherit;
      color: var(--text);
    }
    button {
      height: 44px;
      min-width: 92px;
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-strong); }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    .error { color: var(--error); }
    @media (max-width: 640px) {
      header { padding: 0 12px; }
      .session input { width: 110px; }
      main { padding: 12px; }
      .composer { padding: 12px; }
      form { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand"><span class="mark">LGH</span><span>lgh_agent</span></div>
      <label class="session">Session <input id="session" value="web" /></label>
    </header>
    <main>
      <section id="messages" class="messages">
        <article class="message">
          <span class="role">system</span>
          Ready. Try <code>/tools</code>, <code>/tool list_files .</code>, or ask a normal question.
        </article>
      </section>
    </main>
    <footer class="composer">
      <form id="form">
        <textarea id="message" placeholder="Type a message..." required></textarea>
        <button id="send" type="submit">Send</button>
      </form>
    </footer>
  </div>
  <script>
    const form = document.querySelector("#form");
    const input = document.querySelector("#message");
    const send = document.querySelector("#send");
    const messages = document.querySelector("#messages");
    const session = document.querySelector("#session");

    function addMessage(role, text, toolEvents = []) {
      const article = document.createElement("article");
      article.className = "message " + role;
      const label = document.createElement("span");
      label.className = "role";
      label.textContent = role;
      article.appendChild(label);
      article.appendChild(document.createTextNode(text));
      for (const event of toolEvents) {
        const trace = document.createElement("div");
        trace.className = "tool-event";
        trace.textContent = `${event.ok ? "tool" : "tool error"}: ${event.name} ${JSON.stringify(event.arguments)}\\n${event.content_preview || event.error || ""}`;
        article.appendChild(trace);
      }
      messages.appendChild(article);
      article.scrollIntoView({ block: "end" });
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      addMessage("user", text);
      send.disabled = true;
      try {
        const response = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, session: session.value || "web" })
        });
        const data = await response.json();
        if (!response.ok) {
          addMessage("assistant", data.error || "Request failed.", []);
        } else {
          addMessage("assistant", data.message, data.tool_events || []);
        }
      } catch (error) {
        addMessage("assistant", "Network error: " + error.message, []);
      } finally {
        send.disabled = false;
        input.focus();
      }
    });
  </script>
</body>
</html>
"""
