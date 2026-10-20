from dataclasses import dataclass


@dataclass
class Gasto:
    empleado: str
    categoria: str
    importe: float
    tiene_recibo: bool
    dias_desde_compra: int
