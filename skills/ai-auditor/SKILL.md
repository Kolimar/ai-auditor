---
name: ai-auditor
description: Audita skills, agentes, playbooks, reglas, stages de AI-DLC, prompts o código con LLM (un archivo, una carpeta, un repositorio o un flujo completo) y devuelve un informe de mejoras con las citas verificadas. Señala qué partes no necesitan IA, cuáles gastan contexto de más y qué pasos se pueden simplificar. Úsala cuando pidan auditar, revisar u optimizar instrucciones para IA (Claude Code, Devin, Cursor) o un sistema que llama a un LLM.
---

# Auditoría con ai-auditor y revisión propia

La herramienta es determinista y conservadora: encuentra más o menos la mitad de lo que vería una persona. Tú
completas el análisis leyendo lo que ella no supo clasificar y revisando el flujo entero. Ella te da los hechos medidos
(qué carga cada paso, texto repetido, código, piezas externas) y después comprueba tus citas contra los archivos.

## 1. Qué analizar

| el usuario pide | analiza |
|---|---|
| un archivo (skill, agente, playbook, prompt) | ese archivo |
| una carpeta o un repositorio local | esa carpeta; si son `.md` sueltos sin nombres estándar (playbooks exportados, prompts), añade `--md-instructions` |
| un plugin o una instalación de AI-DLC | su carpeta (se reconoce sola); los protocolos del core que referencia salen como piezas externas: para medirlos, analiza también el core o la instalación |
| un repositorio remoto (URL) | clónalo sin historial en una carpeta temporal (`git clone --depth 1 URL "$(mktemp -d)/repo"`) y analiza esa carpeta |
| «mis skills» o «mis agentes» | `~/.claude`, y también `~/.config/devin/skills`, `~/.cursor` o `~/.agents` si existen |
| un flujo completo | el punto de entrada, y después sigue el paso 4 |
| nada concreto | el proyecto actual |

## 2. Ejecutar

Si `ai-auditor` está instalado:

```bash
ai-auditor analyze RUTA --for-agent -f markdown
```

Si no lo está:

```bash
uvx --from git+https://github.com/Kolimar/ai-auditor ai-auditor analyze RUTA --for-agent -f markdown
```

(Con `uvx`, usa el mismo prefijo para `ai-auditor report` en el paso 5.)

El análisis no llama a ninguna IA, no cuesta dinero y no modifica lo analizado.

## 3. Revisar

El informe tiene dos partes:

1. Las recomendaciones de la herramienta.
2. La sección **"Brief for the agent running the auditor"**: es tu encargo. Síguela al pie de la letra.
   - Empieza por **"Workflow map"**: qué carga cada paso y cuántos tokens suma, qué ejecuta, texto repetido entre
     archivos que se cargan juntos, código que la herramienta no parsea y piezas externas. Son hechos medidos:
     úsalos como evidencia.
   - Abre cada fichero de "To review" y aplica la tabla de patrones.
   - Confirma o descarta cada aviso de "To double-check" por su id, con un motivo.

## 4. Flujos completos

Por ejemplo: una skill que llama a una herramienta que clona un repositorio con más skills, o un ciclo con fases
(explorar, proponer, especificar, diseñar, implementar, verificar).

1. **Mapa.** Lee el punto de entrada y dibuja la cadena: qué fases, agentes o herramientas hay, en qué orden, qué lee
   cada uno y a quién llama. "External pieces" lista los repos, descargas, paquetes, scripts y servidores MCP que
   mencionan las instrucciones.
2. **Cada pieza.** Clona o descarga cada repo o paquete externo en una carpeta temporal y pasa el auditor sobre él
   con `--for-agent`. Si hay más de cinco, pregunta antes cuáles.
3. **La cadena entera.** Aplica los patrones de flujo del encargo:
   - el mismo contexto grande se vuelve a cargar en varias fases (LLM-005);
   - un salto entre agentes o fases que no aporta nada (LLM-012);
   - pasos independientes que se ejecutan en serie (LLM-025);
   - trabajo que se repite en cada ejecución, como clonar, instalar o resumir lo mismo (LLM-014);
   - repos o documentos enteros en contexto cuando bastaría una búsqueda (LLM-015/016);
   - bucles sin límite de turnos, tiempo o presupuesto (LLM-021).

## 5. Verificar y armar el informe

1. Escribe tu revisión en un JSON con el formato de "Answer format", en una carpeta temporal. Cada hallazgo lleva el
   archivo y una frase **copiada tal cual** de ese archivo.
2. Ejecuta:

   ```bash
   ai-auditor report RUTA --review /tmp/.../revision.json -f markdown
   ```

   La herramienta busca cada cita en su archivo y le pone el número de línea. Marca como **no verificado** lo que no
   encuentra: citas inexistentes, archivos o reglas desconocidos, niveles que una revisión no puede tener e ids de
   avisos que no existen.
3. Corrige o quita lo no verificado y vuelve a ejecutarlo hasta que no quede nada en "Not verified".
4. Presenta el resultado en el idioma del usuario con la misma estructura:
   - resumen y mejoras principales;
   - recomendaciones de la herramienta;
   - revisión del agente, aclarando que es tu criterio y no una medición;
   - piezas externas;
   - lo que sí necesita IA.

Si el usuario lo pide, guarda el informe con `-o informe.md`.

## Reglas

- No modifiques lo auditado salvo que el usuario lo pida.
- No ejecutes ni instales el código de las piezas externas: solo léelo y audítalo.
- No inventes ahorros en dinero ni en tokens: di qué desaparecería (por ejemplo, "una llamada a la IA por ejecución").
- Si la herramienta falla o no encuentra ficheros, dilo; no lo suplas con un análisis inventado.
- Borra las carpetas temporales al terminar.
