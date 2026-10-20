# Guía fácil de ai-auditor

## ¿Qué es?

Hoy muchos programas usan inteligencia artificial (ChatGPT, Claude…) para hacer tareas. Cada vez que el programa le
pregunta algo a la IA, **cuesta dinero y tarda unos segundos**.

Muchas veces se usa la IA para cosas que un programa normal hace gratis, al instante y sin equivocarse. Por ejemplo:

- sumar los importes de una factura;
- copiar datos de una tabla a otra;
- decidir algo que ya tiene una regla fija ("si el pedido pasa de 100 €, el envío es gratis").

Es como contratar a un abogado para que te sume la cuenta del supermercado: lo hace, pero una calculadora es más
barata, más rápida y no se equivoca.

**ai-auditor revisa un programa y te señala en qué sitios está usando la IA para cosas que no la necesitan.** También
te dice dónde la IA sí hace falta, para que no la toques ahí.

Funciona como un mecánico que revisa tu coche y te dice: "esta pieza cara la puedes cambiar por esta otra más barata
que hace lo mismo".

## Lo que tienes que saber antes

- **No cambia nada.** Solo lee tu proyecto y te da un informe. Tus archivos quedan igual.
- **No gasta dinero.** No le pregunta nada a ninguna IA: revisa el código él solo.
- **Es rápido.** Un proyecto normal tarda unos segundos.
- **No es perfecto.** En pruebas con proyectos que nunca había visto:
  - de cada 10 avisos que da, unos 8 son correctos;
  - encuentra más o menos la mitad de los problemas que encontraría una persona revisando a mano.

  Es prudente a propósito: prefiere callarse antes que inventar.
- **El informe sale en inglés.** Más abajo te explico cómo leerlo.

## Instalación (una sola vez)

**1. Instala `uv`**, el programa que se encarga de Python por ti. Abre la terminal (la ventana donde se escriben
órdenes), pega esta línea y pulsa Enter:

- en Mac o Linux:

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- en Windows (PowerShell):

  ```powershell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Después cierra la terminal y vuelve a abrirla.

**2. Descarga la herramienta.** Hay dos formas:

- Desde la página de GitHub: botón verde **Code**, luego **Download ZIP**, y descomprímelo donde quieras.
- Si tienes `git`:

  ```bash
  git clone https://github.com/Kolimar/ai-auditor.git
  ```

## Cómo usarlo (3 pasos)

**Paso 1.** Abre la terminal.

**Paso 2.** Entra en la carpeta de la herramienta (la que descargaste). Por ejemplo, si está en tu carpeta personal:

```bash
cd ~/ai-auditor
```

Si la bajaste en ZIP, la carpeta se llama `ai-auditor-main`. La primera vez tardará unos segundos más, porque `uv`
prepara todo lo que necesita.

**Paso 3.** Pídele que revise un proyecto. Cambia `/ruta/de/tu/proyecto` por la carpeta que quieras revisar y pulsa
Enter:

```bash
uv run ai-auditor analyze /ruta/de/tu/proyecto
```

El informe aparece en la pantalla.

**Si prefieres guardarlo en un archivo** para leerlo con calma (por ejemplo, en el Escritorio):

```bash
uv run ai-auditor analyze /ruta/de/tu/proyecto -f markdown -o ~/Escritorio/informe.md
```

**Para revisar tus propios agentes y skills de Claude Code:**

```bash
uv run ai-auditor analyze ~/.claude
```

## Cómo leer el informe

Este es un aviso real, y debajo su explicación:

```
 3. [LIKELY] LLM-026 Deterministic Computation Delegated to LLM  ·  compute_invoice_totals  ·  invoices.py:81
    → Compute in code (Decimal for money) and, if needed, let the LLM only phrase the result.
      + arithmetic/aggregation requested: '...compute subtotal (sum of qt...'
```

| parte | qué significa |
|---|---|
| `3.` | Es el aviso número 3. Los más importantes van primero. |
| `[LIKELY]` | **Cuánta seguridad tiene** (ver la tabla siguiente). |
| `LLM-026` y el título | **Qué problema ve.** Aquí: "le pide a la IA que haga cuentas". |
| `compute_invoice_totals` | **Dónde**: el nombre de la parte del programa. |
| `invoices.py:81` | El archivo y la línea exacta, para que quien programa lo encuentre. |
| línea con `→` | **Qué te recomienda hacer.** Aquí: "haz la cuenta con código y deja a la IA solo la redacción". |
| líneas con `+` | Las **pistas** que lo llevaron a pensarlo. |
| líneas con `-` | Las pistas **en contra**, que le restan seguridad. |

**Cuánta seguridad tiene cada aviso:**

| palabra | qué significa | qué hacer |
|---|---|---|
| `PROVEN` | Comprobado con una prueba real. | Puedes hacer el cambio. |
| `HIGH_CONFIDENCE` | Casi seguro. | Vale la pena hacerlo. |
| `LIKELY` | Probable. | Revísalo; suele tener razón. |
| `HYPOTHESIS` | Sospecha. | Míralo con calma y no cambies nada sin probar antes. |
| `DO_NOT_OPTIMIZE` / "LLM use justified" | Aquí la IA **sí** hace falta. | No lo toques. |

Al final del informe, `LLM use justified: …` lista las partes donde la IA está bien usada.

## Los avisos más comunes, en palabras sencillas

| código | qué quiere decir |
|---|---|
| LLM-001 | Usa la IA para decidir algo que ya tiene reglas fijas. Bastan unos "si pasa esto, haz aquello". |
| LLM-003 / LLM-018 | Usa una IA grande y cara para una tarea fácil. Una más pequeña y barata podría bastar. |
| LLM-004 | Le manda a la IA muchísimo texto que no necesita. Se paga por cada palabra. |
| LLM-008 | Cuando la IA responde con el formato mal, se le vuelve a preguntar una y otra vez en lugar de exigirle el formato desde el principio. |
| LLM-009 | Usa la IA para leer datos que ya vienen ordenados (una tabla, un archivo). Un programa normal los lee gratis. |
| LLM-010 | Usa la IA solo para cambiar el formato de algo (de tabla a lista, de un tipo de archivo a otro). |
| LLM-011 | Usa la IA para comprobar que no falte ningún dato obligatorio. Eso se comprueba con código. |
| LLM-017 | Un agente que solo ejecuta siempre los mismos comandos en el mismo orden. Un script lo hace igual. |
| LLM-021 | Un agente que puede quedarse dando vueltas sin límite, gastando sin parar. |
| LLM-022 | Le pide a la IA que conteste con un formato "por favor", en vez de obligarla, y a veces no cumple. |
| LLM-024 | Procesa muchos elementos uno a uno sin prisa. Los proveedores tienen una modalidad por lotes con descuento. |
| LLM-026 | Le pide a la IA que haga cuentas. Una calculadora no se equivoca. |

La lista completa sale con `uv run ai-auditor rules`. Las definiciones detalladas están en `docs/RULES.md`.

## Preguntas frecuentes

**¿Me dice cuánto voy a ahorrar?**
No a ciencia cierta. Sin datos de uso real solo puede decir "esto quita una llamada a la IA cada vez". Nunca inventa
cifras de ahorro.

**¿Puedo hacer caso a todo lo que dice?**
No a ciegas. Trátalo como el consejo de un mecánico: los avisos `LIKELY` suelen acertar, y los `HYPOTHESIS` son
sospechas que hay que comprobar.

**Un aviso no tiene sentido. ¿Qué hago?**
Ignóralo. Si quieres que se corrija, pásale el aviso a quien mantiene la herramienta.

**No me da ningún aviso. ¿Está todo perfecto?**
No necesariamente. Puede que el proyecto esté bien, o que haya algo que la herramienta no supo ver (recuerda que
encuentra más o menos la mitad).

**¿Qué proyectos entiende?**
Programas en Python que usan IA (OpenAI, Anthropic, Google, LangChain, CrewAI…) y los agentes, skills y comandos de
Claude Code. No entiende otros lenguajes, como JavaScript.

**Me sale un error.**
Comprueba que estás dentro de la carpeta de la herramienta (paso 2) y que la ruta del proyecto existe. Si sigue
fallando, copia el mensaje y pásaselo a quien mantiene la herramienta.

## Palabras raras

| palabra | qué es |
|---|---|
| IA / LLM | El "cerebro" artificial que contesta preguntas, como ChatGPT o Claude. |
| prompt | La pregunta o las instrucciones que el programa le manda a la IA. |
| agente | Un programa que usa la IA para hacer tareas por su cuenta, paso a paso. |
| skill / comando | Instrucciones guardadas que Claude Code sigue para una tarea concreta. |
| modelo | Cada versión de IA. Las grandes son más listas y más caras; las pequeñas, más baratas. |
| terminal | La ventana donde se escriben órdenes para el ordenador. |
