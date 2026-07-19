# AI Mock Interview — Frontend

A Next.js 14 (App Router) browser client that connects to the
[`ai-mock-interview`](../) LiveKit agent and shows the Tavus virtual
avatar in real-time video. Deployable to Vercel in three commands.

## Stack

- **Next.js 14** (App Router, React Server Components)
- **`@livekit/components-react`** for the room UI
- **`livekit-server-sdk`** for minting access tokens server-side
  (so your `LIVEKIT_API_SECRET` never reaches the browser)

## Local development

```bash
cd frontend
npm install        # or: pnpm install / yarn / bun install
npm run dev        # http://localhost:3000
```

The dev server proxies `/api/token` to your agent. You'll also need
the agent worker running locally — in the parent folder:

```bash
cd ..
uv run agent.py dev
```

## Deploy to Vercel

1. **Push the repo to GitHub.** The `frontend/` directory is the
   Vercel project root.
2. **Import into Vercel.**
   - Project root: `frontend`
   - Build command: `next build` (default)
   - Output: `.next` (default)
3. **Set the server env vars** in the Vercel project
   (*Settings → Environment Variables*):

   | Variable | Notes |
   |---|---|
   | `LIVEKIT_URL` | Same value your agent uses, e.g. `wss://…livekit.cloud` |
   | `LIVEKIT_API_KEY` | From your LiveKit Cloud project |
   | `LIVEKIT_API_SECRET` | From your LiveKit Cloud project — server-only |

4. **Set the client env var** so the browser can connect:

   | Variable | Notes |
   |---|---|
   | `NEXT_PUBLIC_LIVEKIT_URL` | Same as `LIVEKIT_URL` — the only env var that ships to the client |

5. Deploy. The `npm install` step installs the deps; `next build`
   produces the static page bundle; Vercel serves both the page and
   the `/api/token` serverless function.

That's it — open the deployed URL on any browser (camera is REQUIRED
only because LiveKit's UI calls for it; the agent will use only
**audio** from your device, so you can deny camera permission and
still interview fine).

## Project layout

```
frontend/
├── app/
│   ├── layout.tsx         # Root layout — imports LiveKit styles
│   ├── page.tsx           # Connect form + LiveKit room stage
│   └── api/token/route.ts # Serverless token minter
├── next.config.js
├── package.json
├── tsconfig.json
└── frontend/.env.example  # Local-only env vars (don't commit secrets)
```

## Demo flow

1. Open the deployed URL.
2. Enter a room name (any string — the agent joins "ai-mock-interview"
   by default; enter that to match).
3. Click **Start interview**. The browser fetches a server-minted
   token from `/api/token`, connects to the LiveKit room, and the
   agent joins as a participant with the Tavus avatar publishing its
   video track.
4. The interviewer greets you, runs the
   **self-introduction → past-experience** flow with stage
   transitions, and ends gracefully.
5. Click **Leave** to disconnect; the stage swap / transition logic
   stays clean because `onDisconnected` clears the token and the
   room tears down.
