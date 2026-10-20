ROUTING_TABLE = """\
Claim situation                                              -> Queue
policy lapsed on the loss date                               -> reject
fraud_flag raised, or claim_amount above 5000                -> special_investigations
claim_amount from 500 up to and including 5000, policy live  -> adjuster
claim_amount below 500, policy live, no flag                 -> fast_track
"""


def header() -> str:
    return "You are the claims desk. Pick exactly one queue for the claim, using the table.\n"


def routing_prompt(claim_json: str) -> str:
    return header() + ROUTING_TABLE + "\nClaim record:\n" + claim_json + "\nQueue:"
