import json

def build_prompt(category: dict, merchant: dict, trigger: dict, customer: dict = None) -> str:
    is_customer_facing = (trigger.get("scope") == "customer") or (customer is not None)
    
    merchant_name = merchant.get("identity", {}).get("name", "the business")
    owner_name = merchant.get("identity", {}).get("owner_first_name", "")
    locality = merchant.get("identity", {}).get("locality", "")
    languages = merchant.get("identity", {}).get("languages", ["en"])
    vertical = category.get("slug", "general")
    
    trigger_kind = trigger.get("kind", "general_update")
    trigger_payload = trigger.get("payload", {})
    
    if is_customer_facing:
        # CUSTOMER-FACING CHAT (Vera acting on behalf of the merchant to their customer)
        customer_name = customer.get("identity", {}).get("name", "there") if customer else "there"
        lang_pref = customer.get("identity", {}).get("language_pref", "en") if customer else "en"
        
        # Specific customer data
        service_due = trigger_payload.get("service_due", "")
        days_overdue = trigger_payload.get("days_since_last_visit", "")
        slots = trigger_payload.get("available_slots", [])
        offer = next((o.get("title") for o in merchant.get("offers", []) if o.get("status") == "active"), None)
        price = trigger_payload.get("price", "") or trigger_payload.get("amount", "")

        return f"""You are the automated WhatsApp booking and recall assistant for {merchant_name} (a {vertical} practice).
Write a warm, direct message to their customer {customer_name} on behalf of the clinic.

The message MUST start: "Hi {customer_name}, {merchant_name} here."
Do NOT mention "Vera" or "magicpin". Do NOT invent any data not provided below.

--- CUSTOMER DATA ---
Name: {customer_name}
Language Preference: {lang_pref}
State: {customer.get("state", "") if customer else ""}
Relationship: {json.dumps(customer.get("relationship", {})) if customer else "{}"}

--- TRIGGER ---
Kind: {trigger_kind}
Payload: {json.dumps(trigger_payload)}

--- ACTIVE OFFERS ---
{offer if offer else "None"}

{'IMPORTANT: The customer prefers Hindi. You MUST write in Hinglish (English-dominant but include Hindi words naturally, e.g. "Apka 6-month cleaning due hai", "Slots ready hain"). Do NOT write full Hindi — keep it natural mix.' if lang_pref in ('hi', 'hi-en mix', 'hi-en', 'hi-en-mix') else ''}
RULES (follow in order):
1. Greeting: "Hi {customer_name}, {merchant_name} here."
2. State the SPECIFIC reason for this message in ONE sentence. Use the trigger payload directly (e.g. service due date, days since last visit, specific service name).
3. Give ONE health/hygiene benefit for the service due (e.g. "prevents plaque buildup" / "keeps hair hydrated"). Do not skip this.
4. If offer is available, state the price or discount explicitly.
5. LOSS AVERSION (one line, mandatory): State the COST of skipping this appointment using a specific ₹ figure comparison:
   - Dental: "Cleaning costs ₹299 now vs ₹3,000+ to fill a cavity later."
   - Salon: "A trim now costs ₹200 vs ₹800+ split-end treatment later."
   - Gym: "Members who skip 2+ weeks are 3x more likely to cancel their membership."
   Use the real price from offer data if available. Otherwise use vertical norms above.
6. End with a LOW-FRICTION CTA with urgency. MUST include a named slot time or booking deadline:
   With slots from payload: "Reply 1 for [Day Time e.g. Wed 6pm] or 2 for [Day Time] — slots fill fast, book by [day]."
   Without slots: "Reply YES to confirm your slot — we'll hold it until tomorrow."
   NEVER use bare "Reply 1 or 2" without stating what 1 and 2 mean — always name the slot time.
7. Under 80 words. Output ONLY the raw message. No JSON, no preamble.
"""
    else:
        # MERCHANT-FACING CHAT (Vera acting as growth assistant to the merchant owner)
        voice_tone = category.get("voice", {}).get("tone", "peer_clinical" if vertical == "dentists" else "operator")
        taboos = category.get("voice", {}).get("vocab_taboo", [])
        
        # Determine how to address the merchant (Dentists like "Dr. [Name]")
        salutation = owner_name
        if vertical == "dentists" and owner_name:
            if not owner_name.lower().startswith("dr"):
                salutation = f"Dr. {owner_name}"
        
        # Check if Hindi is in the merchant's preferred languages
        use_hinglish = "hi" in languages or "hi-en mix" in languages or any("hi" in lang for lang in languages)
        
        # Extract key performance data for explicit inclusion
        perf = merchant.get("performance", {})
        ctr = perf.get("ctr", None)
        views = perf.get("views", None)
        calls = perf.get("calls", None)
        delta_7d = perf.get("delta_7d", {})
        views_change = delta_7d.get("views_pct", None)
        calls_change = delta_7d.get("calls_pct", None)
        
        sub = merchant.get("subscription", {})
        sub_status = sub.get("status", "")
        days_remaining = sub.get("days_remaining", None)
        days_since_expiry = sub.get("days_since_expiry", None)
        
        signals = merchant.get("signals", [])
        active_offers = [o.get("title") for o in merchant.get("offers", []) if o.get("status") == "active"]
        lapsed = merchant.get("customer_aggregate", {}).get("lapsed_90d_plus") or \
                 merchant.get("customer_aggregate", {}).get("lapsed_180d_plus", None)
        
        # Build a data bullets string so the LLM can cite numbers directly
        data_bullets = []
        if ctr is not None:
            data_bullets.append(f"CTR: {ctr} (include this in your message)")
        if views is not None:
            data_bullets.append(f"Profile views (30d): {views}")
        if calls is not None:
            data_bullets.append(f"Calls (30d): {calls}")
        if views_change is not None:
            pct = f"+{int(views_change*100)}%" if views_change >= 0 else f"{int(views_change*100)}%"
            data_bullets.append(f"Views change (7d): {pct}")
        if calls_change is not None:
            pct = f"+{int(calls_change*100)}%" if calls_change >= 0 else f"{int(calls_change*100)}%"
            data_bullets.append(f"Calls change (7d): {pct}")
        if days_remaining is not None and sub_status in ("trial", "active"):
            data_bullets.append(f"Subscription days remaining: {days_remaining}")
        if days_since_expiry is not None:
            data_bullets.append(f"Days since subscription expired: {days_since_expiry}")
        if lapsed is not None:
            data_bullets.append(f"Lapsed customers (90/180d+): {lapsed} — mention this count")
        if active_offers:
            data_bullets.append(f"Active offers: {active_offers}")
        if signals:
            data_bullets.append(f"Business signals: {signals}")
        
        data_section = "\n".join(f"  • {b}" for b in data_bullets) if data_bullets else "  • No specific data available"

        return f"""You are Vera, an intelligent growth assistant for local merchants. Write ONE proactive recommendation message to {salutation}, owner of {merchant_name}{' in ' + locality if locality else ''}.

This message is triggered by: [{trigger_kind}]
Trigger payload: {json.dumps(trigger_payload)}

--- MERCHANT NUMBERS (cite at least 2 of these in your message) ---
{data_section}

--- CATEGORY CONTEXT ---
Vertical: {vertical}
Voice tone: {voice_tone}
Peer benchmarks: {json.dumps(category.get("peer_stats", {}))}
Research/digest: {json.dumps(category.get("digest", [])[:2])}
Seasonal: {json.dumps(category.get("seasonal_beats", [])[:2])}

STRICT RULES:
{'IMPORTANT: The merchant speaks Hindi. You MUST write this message in Hinglish (natural Hindi-English mix). English-dominant is fine, but key phrases, data points, and the CTA must have Hindi words woven in.' if use_hinglish else ''}
1. Greet the owner by name in sentence 1 — include their business name and locality.
2. State WHY NOW in sentence 1-2. Trigger: [{trigger_kind}]. Cite the specific source/deadline AND what opportunity or risk window opens. Be concrete:
   - research_digest → "[Journal] [month] issue highlights [finding]. Acting this month means [specific outcome]."
   - regulation_change → "[Regulation] effective [date]. Clinics caught non-compliant face [consequence]."
   - performance_drop → "Your [metric] dropped [amount] this week — that's [₹ estimate] in missed bookings."
3. Cite at least 2 SPECIFIC NUMBERS from the merchant data section. Do NOT invent data.
   Also explain HOW these numbers connect to the trigger — e.g. "Your CTR of 0.021 (40% below peers) means each recall campaign has outsized impact because you're getting fewer organic visits anyway."
4. LOSS AVERSION: One concrete consequence of NOT acting, attached to a number:
   - Research: "Clinics that don't run recall in Q4 see 28% fewer return patients by Jan."
   - Regulation: "Non-compliant setups after [date] risk DCI inspection + equipment shutdown costing ₹50,000+ in lost bookings."
   - Performance: "At this CTR, [X] fewer patients click through per 1,000 impressions vs. peers."
5. URGENCY/SCARCITY (mandatory, one sentence): Give a time-bound reason to act TODAY — not eventually:
   - Deadline: "DCI inspection window opens after Dec 15 — only [N] weeks left."
   - Cohort: "The recall cohort window closes next month — I can set it up today."
   - Capacity: "I have capacity to draft this for 2 more clinics this week."
   - Peer competition: "Two clinics in Lajpat Nagar already run this — acting now keeps you ahead."
6. CTA (final sentence only): Use NUMBERED OPTIONS — not YES/NO — for lowest friction:
   English format:  "Reply 1 to [start action now], or 2 to [schedule for later]."
   Hinglish format: "Reply 1 karo aur main [action] abhi draft karta hoon, ya 2 agar agle hafte karein."
   Examples:
   - "Reply 1 and I'll draft the fluoride recall template now, or 2 to schedule for next week."
   - "Reply 1 to start the 2-min DCI compliance check today, or 2 to set a reminder for next week."
   - "Reply 1 and I'll pull your 78 lapsed patients list now, or 2 to revisit next month."
   BAD CTAs: "yes or no?" / "Reply YES or NO" / "Would you like?" / open-ended questions.
7. Taboo words to AVOID: {taboos if taboos else 'none'}
8. Under 95 words. Output ONLY the message text. No JSON, no preamble, no markdown.

EXAMPLE of a HIGH-SCORING message (research_digest trigger, Hinglish):
"Dr. Meera, JIDA's Oct digest highlights a 3-month fluoride recall trial — 34% better retention in high-risk adults. Aapka CTR 0.021 hai, peers se 40% low, aur 78 lapsed patients abhi reachable hain. Clinics that skip Q4 recalls see 28% drop in Jan return rate. The cohort window closes next month — 2 more clinics in Lajpat Nagar already enrolled. Reply 1 and I'll draft the WhatsApp recall template now, or 2 to schedule next week."
"""