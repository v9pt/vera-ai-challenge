def decide_action(merchant):
    if not merchant:
        return "general"

    signals = merchant.get("signals", []) or []
    signals_text = " ".join(signals)

    if "trial_ending_soon" in signals_text:
        return "trial"

    if "winback_eligible" in signals_text:
        return "winback"

    if "renewal_due_soon" in signals_text:
        return "renewal"

    if "high_engagement" in signals_text:
        return "growth"

    if "no_active_offers" in signals_text:
        return "offer"

    if "stale_posts" in signals_text:
        return "content"

    if "perf_dip_severe" in signals_text:
        return "performance"

    return "general"