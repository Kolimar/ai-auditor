---
description: Calcula el coste mensual de una lista de instancias
argument-hint: <tipo:precio_hora:cantidad ...>
---
Recibes en $ARGUMENTS una lista de elementos con el formato `tipo:precio_hora:cantidad`, por ejemplo `m5.large:0.096:4`. Para cada uno calcula `precio_hora * cantidad * 730` y luego el total mensual y el total anual. Presenta una tabla con una fila por elemento y los totales al final, con dos decimales.
