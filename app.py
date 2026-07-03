from fastapi import FastAPI
from datetime import datetime, timezone
import json
from services.llm import generate_message

from services.data_loader import load_all_data
from store import (
    contexts,
    versions,
    conversations
)
from services.message_builder import build_message

app = FastAPI()

seed_data = load_all_data()

import time

START_TIME = time.time()

@app.get("/v1/healthz")
def health():

    return {
        "status": "ok",
        "uptime_seconds": int(
            time.time() - START_TIME
        ),
        "contexts_loaded": {
            "category": len(contexts["category"]),
            "merchant": len(contexts["merchant"]),
            "customer": len(contexts["customer"]),
            "trigger": len(contexts["trigger"])
        }
    }



@app.get("/v1/metadata")
def metadata():

    return {
        "team_name": "Huzaifa Mulla",
        "team_members": [
            "Huzaifa Mulla"
        ],
        "model": "Groq Llama 3.3 70B + Rule Fallback",
        "approach": "AI-first contextual message generation with rule-based fallback",
        "contact_email": "huzaifa.mulla.ug22@nsut.ac.in",
        "version": "1.0",
        "submitted_at": datetime.now(
            timezone.utc
        ).isoformat()
    }


@app.post("/v1/context")
def context(payload: dict):

    scope = payload.get("scope")
    context_id = payload.get("context_id")
    version = payload.get("version", 1)

    if scope not in contexts:

        return {
            "accepted": False,
            "reason": "invalid_scope"
        }

    current_version = versions.get(
        context_id,
        0
    )

    if version < current_version:

        return {
            "accepted": False,
            "reason": "stale_version",
            "current_version": current_version
        }

    contexts[scope][context_id] = payload.get(
        "payload",
        {}
    )

    versions[context_id] = version

    return {
    "accepted": True,
    "ack_id": f"ack_{context_id}_v{version}",
    "stored_at": datetime.now(
        timezone.utc
    ).isoformat()
}


@app.post("/v1/tick")
def tick(payload: dict):
    actions = []
    diagnostic_error = None

    trigger_ids = payload.get("available_triggers", [])
    merchant_id_from_payload = payload.get("merchant_id")

    if merchant_id_from_payload and not trigger_ids:
        trigger_ids = [merchant_id_from_payload]

    print("\n--- TICK EXECUTION ---")
    print(f"Payload: {payload}")
    print(f"Trigger IDs to process: {trigger_ids}")

    for trigger_id in trigger_ids:
        trigger = contexts["trigger"].get(trigger_id)

        if not trigger:
            if trigger_id in contexts["merchant"]:
                print(f"[INFO] Trigger ID '{trigger_id}' not found. Synthesizing trigger context for merchant '{trigger_id}'...")
                trigger = {
                    "id": trigger_id,
                    "scope": "merchant",
                    "kind": "scheduled_recurring",
                    "source": "internal",
                    "merchant_id": trigger_id,
                    "payload": {}
                }
            else:
                diagnostic_error = f"Trigger context '{trigger_id}' is missing and cannot be synthesized."
                print(f"[WARN] {diagnostic_error}")
                continue

        merchant_id = trigger.get("merchant_id")
        if not merchant_id:
            if trigger_id in contexts["merchant"]:
                merchant_id = trigger_id
            elif trigger.get("payload", {}).get("merchant_id"):
                merchant_id = trigger.get("payload", {}).get("merchant_id")
            elif trigger.get("context_id") and trigger.get("context_id") in contexts["merchant"]:
                merchant_id = trigger.get("context_id")

        if not merchant_id:
            diagnostic_error = f"Could not resolve merchant_id for trigger '{trigger_id}'"
            print(f"[WARN] {diagnostic_error}")
            continue

        merchant = contexts["merchant"].get(merchant_id)
        if not merchant:
            diagnostic_error = f"Merchant context '{merchant_id}' is missing."
            print(f"[WARN] {diagnostic_error}")
            continue

        customer_id = trigger.get("customer_id")
        customer = None
        if customer_id:
            customer = contexts["customer"].get(customer_id)
            if not customer:
                try:
                    from services.data_loader import load_json
                    customers_seed = load_json("data/customers_seed.json")
                    for cust in customers_seed.get("customers", []):
                        if cust.get("customer_id") == customer_id:
                            customer = cust
                            break
                except Exception:
                    pass

        category_slug = merchant.get("category_slug")
        category = contexts["category"].get(category_slug, {})

        print(f"\n--- Context Loaded ---")
        print("Merchant:", json.dumps(merchant, indent=2) if merchant else None)
        print("Customer:", json.dumps(customer, indent=2) if customer else None)
        print("Category:", json.dumps(category, indent=2) if category else None)
        print("Trigger:", json.dumps(trigger, indent=2) if trigger else None)
        print(f"----------------------\n")

        message = build_message(merchant, trigger)
        print(f"Resulting AI Message: {message}\n")

        scope = trigger.get("scope", "merchant")
        send_as = "merchant_on_behalf" if scope == "customer" else "vera"

        actions.append(
            {
                "conversation_id": f"conv_{trigger_id}",
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "send_as": send_as,
                "trigger_id": trigger_id,
                "template_name": "vera_ai",
                "template_params": [],
                "body": message,
                "cta": "open_ended",
                "suppression_key": trigger.get("suppression_key", ""),
                "rationale": "Generated using category, merchant, trigger and customer context"
            }
        )

    response = {"actions": actions}
    if not actions and diagnostic_error:
        response["diagnostic_error"] = diagnostic_error

    return response

@app.get("/v1/debug")
def debug():

    return {
        "merchant_keys": list(seed_data["merchants"].keys()),
        "customer_keys": list(seed_data["customers"].keys()),
        "trigger_keys": list(seed_data["triggers"].keys())
    }


@app.get("/v1/sample")
def sample():
    return seed_data["merchants"]


@app.get("/v1/check")
def check():
    return contexts["merchant"]



@app.get("/v1/merchant/{idx}")
def merchant(idx: int):
    return seed_data["merchants"]["merchants"][idx]



@app.get("/v1/simulate/{idx}")
def simulate(idx: int):

    merchant = seed_data["merchants"]["merchants"][idx]

    message = build_message(
        merchant,
        {}
    )

    return {
        "merchant": merchant["identity"]["name"],
        "message": message
    }



@app.get("/v1/all_merchants")
def all_merchants():
    return {
        "count": len(seed_data["merchants"]["merchants"]),
        "ids": [
            m["merchant_id"]
            for m in seed_data["merchants"]["merchants"]
        ]
    }

@app.post("/v1/reply")
def reply(payload: dict):

    message = payload.get(
        "message",
        ""
    ).lower()

    conversation_id = payload.get("conversation_id", "default")
    
    # Initialize list if first time seeing this conversation
    if conversation_id not in conversations:
        conversations[conversation_id] = []
        
    conversations[conversation_id].append(message)
    
    # Keywords indicating automated out-of-office/bot responses
    auto_reply_keywords = [
        "thank you for contacting",
        "we will respond shortly",
        "our team will respond shortly",
        "automated assistant",
        "busy right now",
        "auto reply",
        "canned response",
        "aapki jaankari ke liye bahut-bahut shukriya"  # Hindi auto-reply example in brief
    ]
    
    is_auto_reply = False
    
    # 1. Keyword check
    if any(kw in message for kw in auto_reply_keywords):
        is_auto_reply = True
        
    # 2. Verbatim repeat check (3+ identical consecutive messages in history)
    history = conversations[conversation_id]
    if len(history) >= 3 and len(set(history[-3:])) == 1:
        is_auto_reply = True
        
    if is_auto_reply:
        return {
            "action": "end",
            "rationale": "Auto-reply detected via keyword match or repeated messages"
        }

    try:

        reply_prompt = f"""
Merchant replied:

{message}

Decide the next action.

Possible actions:

send
wait
end

Rules:

- If merchant accepted, return send
- If merchant declined, return end
- If merchant is unclear, return wait

Return only one word.
"""

        decision = generate_message(
            reply_prompt
        ).strip().lower()

        if "send" in decision:

            return {
                "action": "send",
                "body": "Done. I'll proceed with drafting the campaign recommendations using your recent performance trends and send them here shortly.",
                "cta": "open_ended",
                "rationale": "AI detected positive intent"
            }

        if "wait" in decision:

            return {
                "action": "wait",
                "wait_seconds": 1800,
                "rationale": "AI requested wait"
            }

        if "end" in decision:

            return {
                "action": "end",
                "rationale": "AI detected decline intent"
            }

    except Exception as e:

        print("REPLY AI ERROR:", e)

    return {
        "action": "wait",
        "wait_seconds": 1800,
        "rationale": "Fallback wait"
    }

@app.post("/v1/teardown")
def teardown():

    contexts["category"].clear()
    contexts["merchant"].clear()
    contexts["customer"].clear()
    contexts["trigger"].clear()

    versions.clear()
    conversations.clear()

    return {
        "success": True
    }


@app.get("/")
def home():

    return {
        "service": "Magicpin Vera AI Challenge Bot",
        "status": "running",
        "team": "Huzaifa Mulla",
        "version": "1.0",
        "docs": "/docs",
        "health": "/v1/healthz",
        "metadata": "/v1/metadata"
    }
