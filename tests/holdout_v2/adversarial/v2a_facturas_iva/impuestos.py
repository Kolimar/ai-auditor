from dataclasses import dataclass
import litellm


@dataclass
class Linea:
    descripcion: str
    unidades: int
    precio: float
    tipo_iva: float


def _tabla(lineas):
    return "\n".join(f"{l.descripcion} | {l.unidades} x {l.precio} | IVA {int(l.tipo_iva * 100)}%" for l in lineas)


def calcular_total_factura(lineas: list[Linea]) -> str:
    peticion = (
        "Calcula la base imponible, el IVA desglosado por tipo y el total de esta factura. "
        "Redondea cada línea a dos decimales. Devuelve solo los números.\n" + _tabla(lineas)
    )
    r = litellm.completion(
        model="gpt-4o",
        temperature=0,
        messages=[{"role": "user", "content": peticion}],
    )
    return r.choices[0].message.content


def redactar_cobro(nombre: str, total: str, dias_mora: int) -> str:
    r = litellm.completion(
        model="gpt-4o",
        messages=[{"role": "user", "content": f"Escribe un recordatorio de pago cordial para {nombre}, "
                                              f"total {total}, mora de {dias_mora} dias."}],
    )
    return r.choices[0].message.content
