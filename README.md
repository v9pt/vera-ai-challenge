# Vera AI Challenge Bot

Deployed at: 

---

## Overview

AI-first merchant engagement bot built for the Magicpin Vera AI Challenge.

The bot takes in contextual business data across four dimensions:

* Category Context
* Merchant Context
* Customer Context
* Trigger Context

Using these, it proactively generates personalised growth recommendations for merchants and handles conversational replies in real time.

The architecture combines:

* Gemini 2.5 Flash (primary LLM)
* Groq Llama 3.3 70B (automatic fallback LLM)
* Rule-based fallback engine (last resort, always works)
* Stateful in-memory context storage
* Version-controlled context updates
* Conversation memory

If the LLM is down or rate-limited, the bot still responds — just with a template message instead of a generated one.

---

# Problem Statement

Local businesses receive large amounts of performance, customer, and category data.

Most merchants don't have time to dig through:

* Customer retention numbers
* Performance drops
* Subscription renewals
* Re-engagement windows
* Seasonal opportunities

Vera's job is to turn that raw data into something actionable and send it directly to the merchant.

---

# System Architecture

## AI First

Message generation runs through two LLMs in sequence:

1. **Gemini 2.5 Flash** — primary. Called via raw HTTP against Google's Generative Language API. Temperature locked at 0.0. Max output tokens set to 1000 (needed to give the model enough room for its thinking process before the actual response).

2. **Groq Llama 3.3 70B** — fallback. Automatically triggered if Gemini is missing, slow, or returns a 429.

Both use the same prompt. The caller doesn't care which one responded.

---

## Rule-Based Fallback

If both LLMs fail, a deterministic rule engine kicks in based on the trigger classification from `decision.py`:

```
Gemini → success → return message

Gemini → fail
  ↓
Groq → success → return message

Groq → fail
  ↓
Rule Engine → return template message
```

The bot never returns empty actions.

---

# Context Framework

All contexts are held in memory:

```python
contexts = {
    "category": {},
    "merchant": {},
    "customer": {},
    "trigger": {}
}
```

Each one is stored independently and versioned. Stale updates are rejected.

---

## Category Context

Stores industry-level data:

* Voice and tone guidelines
* Peer benchmarks
* Seasonal trends
* Offer catalogs
* Research digests

---

## Merchant Context

Stores per-business data:

* Identity (name, city, owner)
* Subscription status and days remaining
* Performance metrics (CTR, views, calls, leads)
* Active offers
* Business signals (e.g. `trial_ending_soon`, `perf_dip_severe`)
* Conversation history

---

## Customer Context

Stores customer relationship data:

* Visit count and recency
* Services received
* Lifecycle state (active, lapsed, recall-due)
* Preferred contact channel

---

## Trigger Context

Stores actionable events that activate message generation:

* `trial_ending_soon`
* `renewal_due_soon`
* `perf_dip_severe`
* `recall_reminder`
* `scheduled_recurring`
* Any unknown trigger kind (handled gracefully)

---

# Version-Controlled Context Updates

Each context update includes a version number:

```json
{
  "context_id": "m1",
  "version": 2
}
```

If the incoming version is older than what's already stored, it gets rejected:

```json
{
  "accepted": false,
  "reason": "stale_version"
}
```

---

# Trigger Resolution

When `/v1/tick` is called, the bot resolves the trigger → merchant mapping in this order:

1. Look up the trigger ID in the context store
2. If not found, check if the trigger ID itself matches a known merchant ID
3. Fall back to `trigger.payload.merchant_id`
4. If a trigger doesn't exist but the merchant does, synthesise a default `scheduled_recurring` trigger automatically

This means the bot handles both `{"merchant_id": "m_001"}` and `{"available_triggers": ["trg_001"]}` payloads without needing a pre-pushed trigger every time.

---

# Message Generation Pipeline

```
1. Judge fires /v1/tick with trigger IDs or merchant ID

2. Bot resolves each trigger → finds merchant, category, customer contexts

3. Logs loaded context to stdout for debugging

4. Classifies the situation (decision.py):
   - renewal, trial, winback, growth, content, or general

5. Builds prompt (prompt_builder.py):
   - Merchant-facing: highlights specific numbers, subscription state, peer gaps
   - Customer-facing: uses business voice, lists service details, ends with a CTA
   - Hinglish if merchant's language list includes "hi"

6. Calls Gemini → Groq → Rule Engine (in that order until one succeeds)

7. Returns {"actions": [...]} with the generated message
```

---

# Prompt Engineering

The prompt tells the model to:

* Use the merchant's first name
* Reference exact numbers (CTR, views, days remaining)
* Not hallucinate data that wasn't provided
* Sound like a business account manager, not a chatbot
* End with a specific CTA
* Keep it under two sentences

Priority order when multiple signals are present:

1. Active offers with low engagement
2. Lapsed customers eligible for recall
3. Subscription expiry / trial ending
4. Severe performance dip
5. Previous conversation thread
6. General growth check-in

---

# Conversation Management

Conversation state lives in memory:

```python
conversations = {}
```

Tracked per `conversation_id`. Enables multi-turn flows without re-sending context on every message.

---

# Reply Handling

When a merchant replies, the message goes through:

1. **Auto-reply detection** — if it matches canned phrases like "thank you for contacting" or "we will respond shortly", the conversation ends immediately.

2. **Hostility detection** — words like "stop", "spam", "not interested" trigger an `end` action.

3. **LLM classification** — positive intent, question, or neutral replies get classified and routed to `send` or `wait`.

4. **Keyword fallback** — if the LLM is down, keyword matching handles the basics.

Actions returned:

```json
{ "action": "send", "body": "..." }
{ "action": "wait" }
{ "action": "end" }
```

---

# Challenge Endpoints

## GET /v1/healthz

Returns system status, uptime in seconds, and count of loaded contexts per type.

---

## GET /v1/metadata

Returns team name, model details, approach summary, contact email, and submission timestamp.

---

## POST /v1/context

Ingests category, merchant, customer, or trigger contexts. Enforces version checks. Rejects stale updates.

---

## POST /v1/tick

Receives active trigger IDs (or a merchant ID directly). Runs the full message generation pipeline. Returns an action list.

```json
{
  "actions": [
    {
      "merchant_id": "m_001",
      "body": "...",
      "cta": "..."
    }
  ]
}
```

---

## POST /v1/reply

Processes a merchant's reply within an ongoing conversation. Returns `send`, `wait`, or `end`.

---

## POST /v1/teardown

Wipes all stored contexts, versions, and conversations. Used between test runs.

---

# Project Structure

```text
vera-ai-challenge-main/

├── app.py                    # FastAPI app, all endpoints
├── store.py                  # In-memory context store
├── requirements.txt
├── README.md
├── .env
├── .env.example
├── .gitignore

├── services/
│   ├── data_loader.py        # Loads seed JSON files
│   ├── decision.py           # Classifies trigger type
│   ├── llm.py                # Gemini + Groq LLM calls
│   ├── prompt_builder.py     # Builds system prompts
│   └── message_builder.py    # Orchestrates LLM → fallback chain

├── data/
│   ├── merchants_seed.json   # 10 representative merchant profiles
│   ├── customers_seed.json
│   └── triggers_seed.json

├── tests/
│   └── test_bot.py           # Integration test suite (6 scenarios)
```

---

# Run Locally

Clone and install:

```bash
pip install -r requirements.txt
```

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

Start the server:

```bash
uvicorn app:app --reload
```

Swagger UI at:

```
http://127.0.0.1:8000/docs
```

Run the integration tests:

```bash
python tests/test_bot.py
```

---

# Technology Stack

| Layer | Tech |
| :--- | :--- |
| Backend | FastAPI + Uvicorn |
| Primary LLM | Gemini 2.5 Flash (Google Generative Language API) |
| Fallback LLM | Groq — Llama 3.3 70B Versatile |
| HTTP Client | `requests` |
| Environment | python-dotenv |
| Language | Python 3.11 |

---

# Author

Huzaifa Mulla

Built for the Magicpin Vera AI Challenge.
