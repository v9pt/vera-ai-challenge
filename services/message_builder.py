from services.decision import decide_action
from services.llm import generate_message
from services.prompt_builder import build_prompt
from store import contexts


def build_message_rule(merchant, trigger):

    action = decide_action(merchant)

    identity = merchant.get("identity", {})
    performance = merchant.get("performance", {})
    signals = merchant.get("signals", [])
    offers = merchant.get("offers", [])
    history = merchant.get("conversation_history", [])
    customer_data = merchant.get("customer_aggregate", {})
    subscription = merchant.get("subscription", {})

    name = identity.get("owner_first_name", "there")
    ctr = performance.get("ctr", 0)

    # --------------------------------------------------
    # CONTENT / LOW CTR CASE
    # --------------------------------------------------

    stale = any("stale_posts" in s for s in signals)
    low_ctr = any("ctr_below_peer_median" in s for s in signals)

    interested_topic = ""

    for msg in history:
        body = msg.get("body", "").lower()

        if "whitening" in body and "whitening" not in interested_topic:
            interested_topic += "whitening"

        if "aligners" in body:
            if interested_topic:
                interested_topic += " and aligners"
            else:
                interested_topic += "aligners"

    active_offer = None

    for offer in offers:
        if offer.get("status") == "active":
            active_offer = offer.get("title")
            break

    high_risk = customer_data.get(
        "high_risk_adult_count",
        0
    )

    if stale and low_ctr:

        return (
            f"{name}, your CTR ({ctr:.1%}) is currently below similar clinics "
            f"and your last post appears outdated.\n\n"
            f"You previously showed interest in {interested_topic} content.\n\n"
            f"I can generate 3 ready-to-publish posts and promote "
            f"your active offer ({active_offer}) to "
            f"{high_risk} high-intent customers.\n\n"
            f"Generate campaign drafts?"
        )

    # --------------------------------------------------
    # RENEWAL CASE
    # --------------------------------------------------

    if action == "renewal":

        days = subscription.get(
            "days_remaining",
            0
        )

        lapsed = customer_data.get(
            "lapsed_180d_plus",
            0
        )

        return (
            f"{name}, your Pro plan expires in "
            f"{days} days and recent performance "
            f"has declined.\n\n"
            f"You currently have no active offers "
            f"and {lapsed} past customers have not "
            f"returned recently.\n\n"
            f"I can help create a renewal strategy, "
            f"a new patient offer, and a re-engagement campaign.\n\n"
            f"Would you like me to prepare it?"
        )

    # --------------------------------------------------
    # OFFER CASE
    # --------------------------------------------------

    if action == "offer":

        return (
            f"{name}, you currently have no active offers.\n\n"
            f"Creating a limited-time promotion could help "
            f"increase visibility and attract new customers.\n\n"
            f"Would you like me to suggest an offer?"
        )

    # --------------------------------------------------
    # PERFORMANCE CASE
    # --------------------------------------------------

    if action == "performance":

        views_change = performance.get(
            "delta_7d",
            {}
        ).get(
            "views_pct",
            0
        )

        return (
            f"{name}, your business visibility has dropped "
            f"over the last week ({views_change:.0%}).\n\n"
            f"I can identify the biggest causes and suggest "
            f"actions to improve discovery and lead generation.\n\n"
            f"Would you like a performance review?"
        )

    # --------------------------------------------------
    # GROWTH CASE
    # --------------------------------------------------

    if action == "growth":

        return (
            f"{name}, your business is outperforming similar "
            f"businesses in your area.\n\n"
            f"Views and customer engagement are growing.\n\n"
            f"I noticed local demand trends that could help "
            f"you attract even more customers.\n\n"
            f"Would you like a growth campaign suggestion?"
        )

    # --------------------------------------------------
    # WINBACK CASE
    # --------------------------------------------------

    if action == "winback":

        lapsed = customer_data.get(
            "lapsed_90d_plus",
            0
        )

        return (
            f"{name}, your subscription has expired and "
            f"business visibility appears to have declined.\n\n"
            f"You also have {lapsed} past customers who "
            f"have not returned recently.\n\n"
            f"I can prepare a win-back campaign and "
            f"profile recovery plan.\n\n"
            f"Would you like me to prepare it?"
        )

    # --------------------------------------------------
    # TRIAL CASE
    # --------------------------------------------------

    if action == "trial":

        days = subscription.get(
            "days_remaining",
            0
        )

        return (
            f"{name}, your trial ends in {days} days.\n\n"
            f"You already have an active promotion and "
            f"local demand opportunities available.\n\n"
            f"I can help create a campaign before the "
            f"trial expires.\n\n"
            f"Would you like suggestions?"
        )

    # --------------------------------------------------
    # FALLBACK
    # --------------------------------------------------

    return (
    f"Hi {name}, I found a few growth opportunities "
    f"for your business. Would you like a quick review?"
)


def build_message(merchant, trigger):

    try:

        action = decide_action(merchant)

        category_slug = merchant.get(
            "category_slug"
        )

        category = contexts["category"].get(
            category_slug,
            {}
        )

        customer_id = trigger.get(
            "customer_id"
        )

        customer = None

        if customer_id:

            customer = contexts["customer"].get(
                customer_id
            )
            
            if not customer:
                try:
                    from services.data_loader import load_json
                    customers_seed = load_json("data/customers_seed.json")
                    for cust in customers_seed.get("customers", []):
                        if cust.get("customer_id") == customer_id:
                            customer = cust
                            break
                except Exception as e:
                    print("Error loading customer fallback:", e)

        category["recommended_action"] = action

        prompt = build_prompt(
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer
        )

        ai_message = generate_message(prompt)
        print(f"\n--- AI MESSAGE GENERATED ---\n{ai_message}\n----------------------------\n")

        if ai_message and len(ai_message.strip()) > 20:
            return ai_message

    except Exception as e:

        print("GROQ ERROR:", e)

    return build_message_rule(
        merchant,
        trigger
    )