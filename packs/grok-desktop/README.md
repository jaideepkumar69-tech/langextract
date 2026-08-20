# Grok Desktop

Grok Desktop (`C:\Users\USER\AppData\Local\Programs\Grok Desktop\Grok Desktop.exe`) is grok.com in a desktop shell. It does **not** load `~/.grok/config.toml` (that is Grok Build CLI only).

Use the same custom MCP connector as grok.com:

1. Run `C:\Users\USER\projects\langextract\CONNECT-GROK-WEB.bat`
2. Add the `https://….trycloudflare.com/mcp` URL at https://grok.com/connectors → Custom
3. Open Grok Desktop, sign in with the same account, start a new chat

Optional: paste `..\grok-web\SYSTEM_PROMPT.md` as the first message.
