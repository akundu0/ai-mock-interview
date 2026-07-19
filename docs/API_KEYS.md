# Getting API keys for the AI mock-interview agent

This walkthrough gives you every key/ID the agent expects in
`.env.local`, with concrete URLs and the exact cURL for the
non-obvious Tavus setup. Total time: **~5 min** once you have both
accounts.

## TL;DR — the env vars you need

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL` | LiveKit Cloud → Project → "URL" |
| `LIVEKIT_API_KEY` | LiveKit Cloud → Project → "API Key" |
| `LIVEKIT_API_SECRET` | LiveKit Cloud → Project → "API Secret" |
| `TAVUS_API_KEY` | platform.tavus.io → Account → "API Keys" |
| `TAVUS_FACE_ID` | platform.tavus.io → Replicas → Phoenix-3 PRO → copy id |
| `TAVUS_REPLICA_ID` | Same as `TAVUS_FACE_ID` — alias |
| `TAVUS_PERSONA_ID` | Created via the cURL below |

(For zero external-API-key tests, the agent uses **LiveKit Inference**
as the default voice pipeline — Deepgram / OpenAI / Cartesia tokens
are issued by LiveKit Cloud automatically.)

---

## 1. LiveKit Cloud

LiveKit Cloud is a free managed LiveKit server. Two minutes to a working
project.

1. Sign up at <https://cloud.livekit.io/>.
2. Click **Create project**, accept any defaults.
3. After it spins up, copy from the project page:
   - **URL** → `LIVEKIT_URL` (looks like `wss://your-project.livekit.cloud`)
   - **API Key** → `LIVEKIT_API_KEY`
   - **API Secret** → `LIVEKIT_API_SECRET`
4. Optional but recommended: install the [LiveKit CLI](https://docs.livekit.io/home/cli/cli-install/)
   so you can run `lk agent dev` later for a one-command local agent
   invocation against the cloud.

> **Self-hosting instead of Cloud?** Skip this section and point
> `LIVEKIT_URL` at your server. You'll also need to drop the
> `livekit-agents[inference]` defaults and pass your own STT/LLM/TTS
> API keys.

---

## 2. Tavus — API key

1. Sign up at <https://platform.tavus.io/>.
2. After email verification, the dashboard lands on your account page.
3. Click **API Keys** in the left sidebar → **Create API Key** → copy
   the value into `TAVUS_API_KEY`.

> ⚠️ Treat this like a credit-card key — anyone with it can spawn
> Tavus replicas and burn your minutes.

---

## 3. Tavus — Phoenix-3 PRO face (`TAVUS_FACE_ID`)

Phoenix-3 PRO is the lowest-latency face model Tabus ships. Pick it
in the dashboard once and copy the resulting replica id.

1. In the Tavus dashboard, click **Replicas** in the sidebar.
2. Click **Create Replica**. When prompted for the face model, pick
   **Phoenix-3 PRO**.
3. Upload or accept the bundled stock footage as required by the
   wizard.
4. After Tavus finishes training (a few minutes), open the new
   replica. Its id (a short hash like `r90bbd427f71`) goes into
   `TAVUS_FACE_ID`.
5. The agent accepts either name — if you previously set
   `TAVUS_REPLICA_ID`, that still works; the helper function in
   `agent.py` honours both env vars.

---

## 4. Tavus — LiveKit-compatible persona (`TAVUS_PERSONA_ID`)

The persona is the *behavioral* layer on top of a face; it controls
pipeline mode, transport, and any persona-specific config.

You can't actually click "Create Persona → transport=livekit → pipeline
mode=echo" through the dashboard — the LiveKit transport option is
API-only. Use the exact `curl` from the LiveKit Tavus docs:

```bash
curl --request POST \
  --url https://tavusapi.com/v2/personas \
  -H "Content-Type: application/json" \
  -H "x-api-key: $TAVUS_API_KEY" \
  -d '{
    "layers": { "transport": { "transport_type": "livekit" } },
    "persona_name": "AI Mock Interviewer",
    "pipeline_mode": "echo"
  }'
```

The response body includes a `persona_id` (single short hash). Copy
that into `TAVUS_PERSONA_ID`.

> **Why `pipeline_mode: "echo"`?** This mode echoes the agent's
> generated audio straight into the avatar's mouth — it gives the
> tightest lip-sync at the lowest end-to-end latency. Other modes
> (e.g. "full") wait for a complete utterance before synthesizing,
> which would visibly desync the avatar from the interviewer.

---

## 5. Putting it together

Drop these into `~/.your-project/.env.local` (or whatever path
`dotenv` finds first):

```ini
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

TAVUS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TAVUS_FACE_ID=r90bbd427f71            # your Phoenix-3 PRO replica id
TAVUS_REPLICA_ID=r90bbd427f71         # alias (optional)
TAVUS_PERSONA_ID=pxxxxxxxxxx           # your LiveKit-transport persona id
```

Then:

```bash
uv sync
uv run agent.py dev
```

---

## 6. Frontend — Vercel deployment env vars

The Next.js frontend in `frontend/` mints LiveKit access tokens
server-side — so the **same** LiveKit API key/secret pair must live in
the Vercel project settings:

| Vercel env var | Same as |
|---|---|
| `LIVEKIT_URL` | (`NEXT_PUBLIC_LIVEKIT_URL` is the public-facing version) |
| `LIVEKIT_API_KEY` | project-level, server-only |
| `LIVEKIT_API_SECRET` | project-level, server-only |
| `NEXT_PUBLIC_LIVEKIT_URL` | `LIVEKIT_URL`, exposed to the browser |

Tavus credentials are **not** needed in the frontend — only the agent
talks to Tavus directly.

See [`frontend/README.md`](../frontend/README.md) for the full
deploy-to-Vercel flow.
