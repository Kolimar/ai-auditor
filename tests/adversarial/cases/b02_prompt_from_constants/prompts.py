REFUND_HEADER = "You are the refunds desk. Output exactly one word: APPROVE, REJECT or ESCALATE.\n"
REFUND_RULES = (
    "- APPROVE when order_total <= 500 and days_since_delivery <= 30 and item_returned is true.\n"
    "- ESCALATE when order_total > 500 and days_since_delivery <= 30.\n"
    "- REJECT in every other case.\n"
)
REFUND_INPUT = "Request:\norder_total={order_total}\ndays_since_delivery={days}\nitem_returned={returned}\n"
