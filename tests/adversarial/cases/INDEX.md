# Casos adversariales

| Caso | Cat. | Tecnica de enganio | Etiqueta esperada |
|---|---|---|---|
| a01_sarcasm_sentiment | A | "Clasifica" + salida cerrada, pero sarcasmo | absent (ANY-ish, sin 018) |
| a02_legal_intent | A | Clasificacion cerrada de intencion legal, temp 0 | absent ANY |
| a03_clinical_risk | A | Riesgo clinico, modelo ya pequeno | absent ANY |
| a04_prose_commitments | A | "Extract" sobre prosa informal ambigua | absent |
| a05_factcheck_validate | A | "validate/verify" + JSON = fact-checking | absent |
| a06_localize_rewrite | A | "Convert/format" = traduccion y localizacion | absent |
| a07_json_free_text | A | Entrada JSON con campo de texto libre | absent |
| a08_contract_yesno | A | Respuesta si/no, modelo grande, multi-paso | absent ANY |
| a09_parallel_research | A | Multi-agente con gather, tools y modelos distintos | absent x3 |
| a10_critic_agents | A | Critico con criterios distintos al generador | absent x2 |
| a11_summarize_filing | A | Documento completo en prompt es el objeto | absent |
| a12_reglas_como_ejemplo | A | Regla "importe > 1000" solo como ejemplo, en espanol | absent |
| a13_dead_and_examples | A | LLM en `if False:` (absent) y en examples/ (optional) | absent / optional |
| a14_moderation_guardrail | A | Guardarrail binario, temp 0 | absent ANY |
| b01_ask_helper_parser | B | Parser tras helper generico `ask()` | present LLM-009 |
| b02_prompt_from_constants | B | Reglas en constantes de otro modulo | present LLM-001 |
| b03_synonym_rules | B | Reglas con sinonimos ("surpasses", "rebase") | present LLM-001 x2 |
| b04_schema_check_paraphrase | B | Validacion de schema sin la palabra schema | present LLM-011 |
| b05_formateo_espanol | B | Formateo determinista en espanol | present LLM-010 |
| b06_constant_inputs | B | Entradas constantes en funcion llamada por request | present LLM-020/014 |
