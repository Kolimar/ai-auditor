from openai import OpenAI

client = OpenAI()


def flag_account(balance: float, country: str) -> str:
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": (
                    "Whenever the balance surpasses 10000 mark the account RED; if it stays under that "
                    "but above 2500 mark it AMBER; anything lower is GREEN. Regardless of the amount, "
                    f"accounts opened from {', '.join(['KP', 'IR', 'SY'])} are RED.\n"
                    f"Balance: {balance}\nCountry: {country}\nAnswer with the color only."
                ),
            }
        ],
    )
    return r.choices[0].message.content.strip()


def prioridad_pago(monto: float, dias_vencido: int) -> str:
    r = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": (
                    "Cuando el monto rebase 5000 dolares o el pago lleve mas de 45 dias vencido, la "
                    "prioridad es URGENTE; si el monto queda entre 1000 y 5000, NORMAL; en cualquier "
                    f"otro caso, BAJA.\nMonto: {monto}\nDias vencido: {dias_vencido}\nResponde solo la prioridad."
                ),
            }
        ],
    )
    return r.choices[0].message.content.strip()
