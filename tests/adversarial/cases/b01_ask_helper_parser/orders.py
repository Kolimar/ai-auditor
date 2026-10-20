from llm_utils import ask


def read_order_fields(order_json: str) -> str:
    prompt = (
        "Here is an order record from our warehouse API:\n"
        f"{order_json}\n"
        "Give me the order id, the total and the shipping date, one per line."
    )
    return ask(prompt)
