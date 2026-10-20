REGLAS = """Politica de gastos:
1. Si no hay recibo, rechazar.
2. Si el importe es mayor de 500, enviar a revision manual.
3. Si la categoria es 'representacion' y el importe supera 120, enviar a revision manual.
4. Si han pasado mas de 45 dias desde la compra, rechazar.
5. En cualquier otro caso, aprobar.
"""


def render(g) -> str:
    return (
        f"categoria={g.categoria}; importe={g.importe}; recibo={'si' if g.tiene_recibo else 'no'}; "
        f"dias={g.dias_desde_compra}"
    )
