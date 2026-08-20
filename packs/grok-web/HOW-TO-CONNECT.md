# Connect langextract to grok.com and Grok Desktop

Grok Desktop is the same grok.com account in a desktop window. Add the connector **once** on grok.com; it then appears in both.

## 1. Start the local server + public tunnel

Double-click:

`C:\Users\USER\projects\langextract\CONNECT-GROK-WEB.bat`

or:

```powershell
powershell -File C:\Users\USER\projects\langextract\scripts\start-http.ps1 -Tunnel
```

Leave that window open.

## 2. Copy the public MCP URL

In the tunnel log, find:

`https://<random>.trycloudflare.com`

Append `/mcp`:

`https://<random>.trycloudflare.com/mcp`

That URL is also written to `packs/grok-web/PUBLIC_URL.txt` when a helper captures it.

Quick-tunnel hostnames change every start. Do not reuse an old `trycloudflare.com` URL. Stop with `STOP.bat`.

## 3. Add the custom connector

1. Open https://grok.com/connectors
2. Sign in if asked
3. **New Connector** → **Custom**
4. Name: `langextract`
5. MCP server URL: the `https://…/mcp` URL from step 2
6. Save / connect (no OAuth)

## 4. Use it

In grok.com **or** Grok Desktop, start a new chat and ask:

> Run grounded extraction on the NVIDIA Q4 sample and open the review UI.

Or paste `SYSTEM_PROMPT.md` as a first message if the connector tools are not auto-picked.

## Stop

Close the CONNECT-GROK-WEB window (or Ctrl+C). The connector URL dies with the quick tunnel; start the bat again and update the URL if Cloudflare gave a new hostname.
