"""Task profile: deterministic features describing what an LLM step is asked to do.

Every feature keeps the text span that produced it, so findings can quote their
evidence. Lexicons cover English and Spanish. Text heuristics are weak evidence
on their own; rules combine them with structural facts from the IR/graph
(closed output contract, code branching on labels, structured inputs).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ai_auditor.ir.model import INSTRUCTION_FRAMEWORKS, LLMStep, NodeKind, OutputKind, VarSource
from ai_auditor.parser.tokens import count_tokens

if TYPE_CHECKING:
    from ai_auditor.graph.workflow_graph import WorkflowGraph
    from ai_auditor.model_routing.catalog import ModelCatalog, ModelInfo


def _rx(*parts: str) -> re.Pattern[str]:
    return re.compile("|".join(parts), re.I | re.S)


_FORMAT_TARGET = (r"(json|yaml|toml|csv|tsv|xml|markdown|html|(markdown |html )?table|iso[- ]?8601|e\.164|upper ?case|lower ?case|"
                  r"title case|sentence case|snake[_ ]case|camel ?case|kebab[- ]case|(url[- ])?slug|apa( 7| 7th)?( style)?|mla|chicago style|"
                  r"bibtex|ris|vcard|ical|rfc ?\d+|xliff|plist|gettext|strings\.xml|\w*\.strings|ini|dotenv|(nested |bulleted |numbered )?(markdown )?list of links|table of contents|(\"|')?(month|mm|dd|yyyy|d{1,2}/m{1,2})[^\n]{0,20}(yyyy|yy|dd|\d{4})(\"|')?)\b")

TASK_LEXICON: dict[str, re.Pattern[str]] = {
    "classify": _rx(
        r"\bclassif(y|ies|ication)\b", r"\bcategori[sz](e|ation)\b", r"\b(assign|pick|choose) (a|one|the) (single )?(label|category|class|tag|priority|severity)",
        r"\bwhich (category|class|label|bucket|queue|department|intent)\b", r"\bdetermine (the )?(category|class|type|intent|sentiment|priority|severity|language|topic)",
        r"\bsentiment\b", r"\bis (this|it) (spam|fraud(ulent)?|toxic|urgent|relevant)\b",
        r"\bclasific(a|ar|aci[oó]n)\b", r"\bcategoriz(a|ar)\b", r"\betiquet(a|ar)\b", r"\b(asigna|elige) (una |la )?(categor[ií]a|etiqueta|prioridad)",
        r"\bdetermin(a|ar) (la |el )?(categor[ií]a|intenci[oó]n|prioridad|sentimiento|tipo)", r"\basignador de (prioridad|categor[ií]a)",
        r"\b(priority|category|severity) (assigner|classifier)\b",
        # "Place/put/sort/file the title into exactly one of these categories", "pick the best matching category"
        r"\b(place|put|sort|file|bucket|assign|map|slot)s?\b(?:[^.\n]|\.(?=\S)){0,40}\b(in|into|to|under) (exactly |only )?(one|a single) (of|category|bucket|class|group)\b",
        r"\b(pick|choose|select)s? (the |a |one )?(best[- ]?(matching|fitting)|most (appropriate|fitting|relevant)|single|right) (category|label|class|tag|bucket|topic|department|queue)\b",
        r"\bwhich of (these|the following) (categories|labels|classes|topics|buckets|types|options)\b",
        r"\b(coloca|ubica|asigna|clasifica)\b(?:[^.\n]|\.(?=\S)){0,40}\ben (exactamente |solo )?una (de|sola)\b", r"\b(elige|selecciona|escoge) (la|una) (categor[ií]a|etiqueta|clase)\b",
        r"\bdime si\b(?:[^.\n]|\.(?=\S)){0,80}\b(trata|es|habla) (de|sobre)\b(?:[^.\n]|\.(?=\S)){0,160}\bo\b",
        r"(?-i:\b(?i:mark|label|tag|rate|grade)\s+(?i:it|this|them|the \w+|each \w+)\s+(?i:as\s+)?[\"'`“]?[A-Z][A-Z_]{1,})",
        r"(?-i:\b(?i:marca|etiqueta|califica)(?i:la|lo)?\s+(?i:(?:la|el|cada) \w+\s+)?(?i:como\s+)?[\"'`“]?[A-Z][A-Z_]{1,})",
        # "the priority is URGENT" / "la prioridad es URGENTE" (an upper-case label assigned to a category-like attribute)
        r"(?-i:\b(?i:the|its|la|el|su)\s+(?i:priority|severity|category|level|risk|tier|status|prioridad|severidad|categor[ií]a|nivel|riesgo|estado)\s+"
        r"(?i:is|es|will be|ser[aá])\s+[\"'`“]?[A-Z][A-Z_]{2,})",
    ),
    "extract": _rx(
        r"\bextract(s|ed|ing|ion)?\b", r"\bpulls? out\b", r"\bpars(e|es|ing)\b",
        r"\b(break|split|chop|separate|decompose)s? (up )?(the |this |each |every )?(\w+ ){0,3}into (its )?(fields?|columns?|parts|components|key[- ]value pairs|\w+, \w+)",
        r"\b(list|enumerate|output)s? (the |all |every |each )?(\w+ ){0,3}(entries|results|items|records|findings|rows)\b(?:[^.\n]|\.(?=\S)){0,60}\b(with|including|showing) (its|their|the)\b",
        r"\bfor each (entry|result|item|record|row|finding)\b(?:[^.\n]|\.(?=\S)){0,60}?(\b|`\s*)(output|return|list|print|give)\b",
        r"\b(return|output|produce|devuelve|genera)s? (a |an |un )?json (object |objeto )?(with|containing|con)\b(?:[^.\n]|\.(?=\S)){0,30}\b[a-z]+_[a-z_]+\b",
        r"\b(separa|divide|descomp[oó]n)\b(?:[^.\n]|\.(?=\S)){0,40}\ben (campos|columnas|partes)\b",
        r"\b(identify|find|get|return|give me|tell me|list|pull|grab|read off|read out|look up) (the |all |its |their )?(\w+ ){0,2}"
        r"(name|date|amount|total|email|phone|address|invoice|order|customer|sku|id|number|reference|code|quantity|price|status|fields?|values?)s?\b",
        r"\bextra(e|er|iga|igas)\b", r"\bobt[eé]n (el|la|los|las) ", r"\bidentifica (el|la|los|las) (nombre|fecha|importe|monto|total|campo)",
    ),
    "format": _rx(
        # conversion verb + concrete target representation. Output-spec verbs (return/respond/output) are NOT conversions.
        r"\b(convert|reformat|format|transform|render|turn|rewrite|re-?express|express|serialize|restructure|recast)(s|ed|ing)?\b(?:[^.\n]|\.(?=\S)){0,60}"
        r"\b(in)?to\s+(an?\s+|the\s+)?([\w-]+\s+){0,2}([\w-]+\.)?" + _FORMAT_TARGET,
        # "<convert-verb> X as/in <format>"; "format/present the answer in markdown" is an output spec, not a conversion
        r"\b(rewrite|re-?express|reformat|serialize|convert|transform)(s|ed|ing)?\b(?!(?:[^.\n]|\.(?=\S)){0,30}\b(answer|response|reply|output|result)s?\b)"
        r"(?:[^.\n]|\.(?=\S)){0,60}\b(as|in)\s+(an?\s+|the\s+)?([\w-]+\s+){0,2}" + _FORMAT_TARGET,
        r"\bformat (the|this|each|every|all) (\w+ )?(date|number|amount|phone|address|price|currency|name|citation|reference)s?",
        r"\bas an? (markdown |html )?table\b", r"\b(normali[sz]e|standardi[sz]e)s? (the )?(\w+ )?(date|phone|address|format|casing|spelling of)",
        r"\b(normali[sz]e|standardi[sz]e|tid(y|ies)|canonicali[sz]e|clean(s)? up)s? (the )?(\w+ ){0,2}(front ?matter|metadata|headers?|keys|whitespace|indentation|imports)\b",
        r"\b(sort|order|alphabeti[sz]e|regroup|dedupe|de-?duplicate)s?\b(?:[^.\n]|\.(?=\S)){0,20}\b(the |all )?(\w+ ){0,2}(imports|keys|entries|dependencies|headings|fields|lines)\b",
        r"\b(fill|fill in|fill out|populate|complete) (in )?(the |this )?(following )?template\b", r"\b(follow|use) (exactly )?(this|the following) (template|format)( exactly)?\b",
        r"\b(url|web)[- ]?slug\b", r"\bslugif(y|ied)\b",
        r"\b(list|render|output|write|insert)s?\b(?:[^.\n]|\.(?=\S)){0,80}\bas an? (nested |bulleted |numbered )?(markdown )?(list of links|table of contents)\b",
        r"\b(build|generate|create|update|regenerate)s? (a |the )?table of contents\b",
        r"\b(convierte|convertir|formatea|formatear|transforma|transformar|pasa|normaliza|reescribe|expresa)\b(?:[^.\n]|\.(?=\S)){0,60}"
        r"\b(a|en|al formato|como)\s+(json|yaml|csv|xml|markdown|una tabla|tabla|formato|iso|dd/mm|may[uú]sculas|min[uú]sculas|slug|cita|referencia apa|apa)",
        r"\b(rellena|completa) (la|esta) plantilla\b", r"\bformato (apa|iso|e\.164|dd/mm/aaaa)\b",
    ),
    "validate_schema": _rx(
        r"\b(validate|check|verify|ensure|confirm|make sure)\b(?:[^.\n]|\.(?=\S)){0,80}\b(json|schema|valid (json|format)|required fields?|(all|every) (required )?fields?|(each|every) (record|item|row|object) has|fields? (are|is) (present|missing|filled|non-empty)|data types?|correct types?|well[- ]formed|conforms? to|matches the (schema|format|spec)|iso[- ]?(date|8601)|has (an? )?(id|email|date))",
        r"\b(valida|verifica|comprueba|aseg[uú]rate)\b(?:[^.\n]|\.(?=\S)){0,80}\b(json|esquema|campos? (requeridos|obligatorios)|todos los campos|cada registro tiene|formato (v[aá]lido|iso)|tipos? de datos?)",
        r"\b(validat|check|verif|ensur|confirm)(e|es|y|ies|s)?\b(?:[^.\n]|\.(?=\S)){0,60}\b(all|every|each|the) (required |expected |declared )?(columns?|keys?|headers?|properties|attributes|placeholders)\b(?:[^.\n]|\.(?=\S)){0,60}\b(exists?|present|missing|match(es)?|declared type|expected type|correct type|no extra)",
        r"\b(revisa|confirma|chequea|comprueba|verifica) (que|si)\b(?:[^.\n]|\.(?=\S)){0,80}\b(campos?|columnas?|claves?|tipos?|existan|est[eé]n presentes|falte)",
    ),
    "validate_semantic": _rx(
        r"\bfact[- ]?check", r"\bverify (that )?(the |each )?(claims?|facts?|statements?|answer|citations?)\b", r"\bsupported by the (sources?|context|documents?|evidence)",
        r"\bhallucinat", r"\bconsistent with (the )?(sources?|context|documents?|policy|policies)", r"\b(complies|compliant|compliance) with\b", r"\bgrounded\b",
        r"\bverifica (que )?(los )?(hechos|datos|afirmaciones)", r"\bcontrasta\b", r"\brespaldad[oa]s? por (las )?fuentes", r"\balucin",
    ),
    "decide": _rx(
        r"\b(decide|route|routing)\b", r"\bselect (the|which) (queue|team|handler|route|tool|agent|department)", r"\b(approve|reject|escalate|flag)\b",
        r"\bwhich (queue|team|department|handler|route)\b", r"\b(decide|enruta|elige (la|el) (cola|equipo)|aprueba|rechaza|escala)\b",
        r"\b(choose|select|pick|determine)s? (who|whom|which (\w+ ){0,2}(gets?|receives?|handles?|owns?|should))\b",
        r"\b(select|choose|pick)s? the (\w+ ){0,2}(class|tier|plan|carrier|vendor|lane|bucket|route|queue|team|owner|assignee|channel|warehouse|supplier)\b",
        r"\bappl(y|ies) (the |our |these )?(\w+ ){0,3}(polic(y|ies)|rules?|criteria|matrix|rule table|decision table)\b",
        r"\baplica (la |las |los |nuestra |nuestras )?(\w+ ){0,3}(pol[ií]tica|reglas|criterios|matriz)\b", r"\b(aprobar|rechazar)\b",
    ),
    "compute": _rx(
        r"\b(calculate|compute|add up|sum (up|of)|the total of|multiply|subtract|average of|count (the|how many))\b",
        r"\b(calculat|comput)es\b", r"\bwork(s)? out (the|how much|how many|what)\b", r"\bmultipli(ed|es) by\b", r"\bdivided by\b",
        r"\bconvert(s|ed|ing)?\b(?:[^.\n]|\.(?=\S)){0,50}\b(in)?to (grams?|kilo(gram)?s?|kg|pounds?|lbs?|ounces?|oz|met(er|re)s?|feet|inch(es)?|cm|mm|km|miles?|celsius|fahrenheit|kelvin|lit(er|re)s?|gallons?|ml|usd|eur|dollars|euros|seconds|minutes|hours|bytes|kb|mb|gb|the target (unit|currency))\b",
        r"\b(bump|increment)s? (the )?(\w+ )?(version|patch|minor|major|build number|revision)\b", r"\bunit conversion\b", r"\bfrom (the )?source (unit|currency) to (the )?target (unit|currency)\b",
        r"\bconvierte\b(?:[^.\n]|\.(?=\S)){0,50}\ba (gramos|kilos|kilogramos|libras|metros|litros|cent[ií]metros|euros|d[oó]lares|grados)\b",
        r"\b(calcula|calcular|suma|multiplica|resta|promedio de|cuenta (los|las|cu[aá]nt))\b",
    ),
    "summarize": _rx(
        # the verb, or "a/the summary of X" — not the noun alone ("print the pytest summary line" is not summarizing)
        r"\bsummari[sz](e|es|ed|ing|ation)\b", r"\b(write|give|provide|produce|create|return|generate|draft) (me )?(a|an|the) (\w+ ){0,2}summary\b",
        r"\bsummary of (the|this|each|every|these|those|all)\b", r"\btl;?dr\b", r"\bcondens(e|es|ed|ing)\b", r"\bkey (points|takeaways)\b",
        # Spanish; bare "resume" is also English for CV, so only with a Spanish determiner
        r"\bres[uú]me(lo|la|los|las)?\s+(el|la|los|las|este|esta|estos|estas|en)\b", r"\bresumen (de|del|breve|ejecutivo)\b", r"\bresumir\b", r"\bsintetiza\b",
    ),
    "generate": _rx(
        r"\b(write|draft|compose|craft|create|generate|produce)\b(?:[^.\n]|\.(?=\S)){0,40}\b(email|reply|response|message|letter|story|article|post|essay|blog|copy|description|headline|tagline|poem|script|announcement|proposal|report|note|apology|pitch)",
        r"\b(creative|persuasive|engaging|empathetic|warm|friendly|compelling|on-brand)\b",
        r"\b(redacta|escribe|genera|crea)\b(?:[^.\n]|\.(?=\S)){0,40}\b(correo|email|respuesta|mensaje|carta|historia|art[ií]culo|publicaci[oó]n|descripci[oó]n|propuesta|informe|disculpa)",
    ),
    "reason": _rx(
        r"\b(analy[sz](e|es|ing)|analysis of|reason (about|through)|assess|evaluate|diagnose|investigate|root cause|trade-?offs?|critique|review (the|this) (code|design|architecture|contract|argument|draft|pull request|pr))\b",
        r"\b(perform|do|provide|write|give|conduct) (an? |the )?(\w+ )?analysis\b",
        r"\bexplain why\b", r"\b(make|create|draft|devise|write) an? (plan|strategy)\b", r"\bplan (out|how)\b", r"\bdesign (a|an|the)\b",
        r"\b(propose|recommend|strategy)\b",
        r"\b(analiza|eval[uú]a|diagnostica|investiga|planifica|dise[ñn]a|prop[oó]n|recomienda|critica)\b", r"\brevisa\b(?! (que|si)\b)",
    ),
    "translate": _rx(r"\btranslat(e|ion)\b", r"\blocali[sz](e|ation)\b", r"\btradu(ce|cir|cci[oó]n)\b", r"\blocaliza\b"),
    "code": _rx(r"\b(write|generate|implement|refactor|fix)\b(?:[^.\n]|\.(?=\S)){0,20}\b(code|function|script|query|sql|regex|class|tests?|patch)\b"),
    "conversation": _rx(r"\byou are a (helpful|friendly|conversational) (assistant|chatbot)\b",
                        r"\beres un asistente( virtual| conversacional)?( (amable|[uú]til|cordial))?(?! (de|para|que) )\b", r"\b(chat|talk) with the user\b"),
}
MECHANICAL = {"format", "validate_schema", "compute"}
SEMANTIC_OPEN = {"generate", "reason", "summarize", "translate", "code", "conversation"}

JUDGMENT = _rx(
    r"\bnuanc", r"\btone\b", r"\bsarcas", r"\biron(y|ic)", r"\bintent(ion)?\b", r"\bimplie[ds]\b", r"\bimplicit", r"\bsubtle", r"\bempath",
    r"\bjudge?ment\b", r"\buse your (best )?judg", r"\bsubjective", r"\bambigu", r"\bcontext[- ]dependent", r"\binterpret", r"\bread between",
    r"\bpersuasiv", r"\bcreativ", r"\btactful", r"\bdiplomatic", r"\bsensitiv", r"\bemotion", r"\bcultural", r"\bidiom", r"\bholistic",
    r"\bweigh\b", r"\bconsider the (full |whole )?context", r"\bedge cases?\b", r"\bit depends\b",
    r"\bmati(z|ces)", r"\btono\b", r"\bsarcasmo", r"\biron[ií]a", r"\bintenci[oó]n", r"\bimpl[ií]cit", r"\bsutil", r"\bempat", r"\bcriterio\b",
    r"\bjuicio\b", r"\bsubjetiv", r"\bambig", r"\binterpret", r"\bdelicad", r"\bemocional", r"\bcultural",
)
RISK = {
    "medical": _rx(r"\b(medical|clinical|patient|diagnos|symptom|dosage|triage nurse|m[eé]dic|cl[ií]nic|paciente|s[ií]ntoma|dosis)"),
    "legal": _rx(r"\b(legal|contract|clause|liabilit|compliance|regulat|gdpr|hipaa|lawsuit|contrato|cl[aá]usula|cumplimiento|normativ)"),
    "financial": _rx(r"\b(fraud|credit|loan|aml\b|kyc\b|chargeback|dispute|underwrit|fraude|cr[eé]dito|pr[eé]stamo|disputa|contracargo)"),
    "safety": _rx(r"\b(moderat|toxic|harm|self-harm|abuse|hate speech|harass|violen|moderaci[oó]n|t[oó]xic|acoso|odio)"),
    "security": _rx(r"\b(vulnerab|exploit|malware|phishing|prompt injection|jailbreak|\bpii\b|personal data|datos personales)"),
}
REASONING_REQ = _rx(r"step[- ]by[- ]step", r"\bthink (carefully|step|through|hard)", r"chain[- ]of[- ]thought", r"explain your reasoning",
                    r"show your (work|reasoning)", r"\breasoning\b\s*:", r"\bjustify\b", r"<thinking>", r"paso a paso", r"explica tu razonamiento",
                    r"\brazona\b", r"\bjustifica\b")
BOOLEAN_OUT = _rx(r"\b(yes|true)\b\s*(or|/)\s*\b(no|false)\b", r"\bs[ií]\s*(o|/)\s*no\b", r"\bverdadero\s*(o|/)\s*falso\b")
SHORT_OUT = _rx(r"\b(only|just) (the|one|a single|that|this) (word|label|category|number|letter|name|value)", r"\b(single|one)[- ]word\b",
                r"\brespond(ing)? (with )?only\b", r"\bnothing else\b", r"\bno (explanation|other text)\b", r"\bsolo (la|el|una) (palabra|etiqueta|categor[ií]a|n[uú]mero)",
                r"\bsin explicaci[oó]n\b", r"\bnada m[aá]s\b", r"\buna sola palabra\b",
                # "Answer with the color only" / "Responde solo la prioridad"
                r"\b(answer|respond|reply|return|output)( with)? (the|its|a|one) \w+ only\b",
                r"\b(responde|contesta|devuelve)( con)? (solo|s[oó]lo|[uú]nicamente) (la|el|una|un) \w+\b",
                r"\b(responde|contesta|devuelve)( con)? (solo|s[oó]lo|[uú]nicamente)\s*:", r"\b(answer|respond|reply|return|output) (only|just)\s*:")
STRUCTURED_INPUT_TEXT = _rx(r"\b(the following|this|below is the|given the|here is the) (json|csv|xml|html|yaml|log line|record|payload|row|object|api response|headers?)\b",
                            r"\b(message|input|content|payload|text|file)\s+(is|contains|will be)\s+(an?\s+)?(\w+\s+)?(csv|json|xml|yaml|tsv)\b",
                            r"\b(csv|json|xml|tsv)\s+(export|payload|dump|file|document)\b",
                            r"\b(alert|log|syslog|audit[- ]log|access[- ]log|csv|tsv|edi|fixed[- ]width|nginx|apache) (line|record|entry|row)s?\b",
                            r"\b(sarif|junit|bibtex|ics|vcf|har|openapi|swagger|geojson|gpx|kml|x12|hl7|fhir|strings\.xml) (file|document|payload|report|export|entries|records|output)s?\b",
                            r"\b(el siguiente|este|a continuaci[oó]n el) (json|csv|xml|registro|objeto|payload)")
_NOT_STRUCT = r"(?!\s+(is|contains|will be)\s+(an?\s+)?(\w+\s+)?(csv|json|xml|yaml|tsv)\b)"
FREE_TEXT_INPUT_TEXT = _rx(r"\b(the following|this|below is the|the customer'?s?|user'?s?) (message|email|review|text|conversation|complaint|description|comment|feedback|transcript|narrative|chat|story|post|letter)\b" + _NOT_STRUCT,
                           r"\b(el siguiente|este|el) (mensaje|correo|texto|comentario|reclamo|rese[ñn]a|conversaci[oó]n|descripci[oó]n|relato)")
_FT_WORDS = r"(complaint|description|message|comment|notes?|narrative|body|text|feedback|review|story|reason|explanation|reclamo|descripci[oó]n|mensaje|comentario|nota|relato|motivo)"
# Only field-like mentions: "complaint" (quoted key), complaint field, field `notes`, el campo descripción
FREE_TEXT_FIELD = re.compile(
    rf"[\"'`]{_FT_WORDS}[\"'`]|\b{_FT_WORDS}\s+(field|key|property|attribute|column)\b|\b(field|key|campo|columna)\s+[\"'`]?{_FT_WORDS}\b",
    re.I,
)
RULE_SENTENCE = re.compile(
    r"(?:^|[\n.;:])\s*[-*\d.)\s]*(?:[\"'`]?[\w=-]{1,30}[\"'`]?,?\s+){0,4}(?:if|when|whenever|where|for|si|cuando|siempre que)\b(?P<cond>[^.\n]{3,160}?)"
    r"(?:>=|<=|>|<|=|\bgreater\b|\bmore than\b|\bless than\b|\bfewer\b|\bover\b|\bunder\b|\babove\b|\bbelow\b|\bexceeds?\b|\bsurpass(?:es)?\b|"
    r"\bequals?\b|\bis (?:not )?(?:\"|'|`|one of|in|missing|empty|null|older|newer|before|after)|\bcontains\b|\bmayor\b|\bmenor\b|\bsupera\b|\brebasa\b|"
    r"\bsupere\b|\brebase\b|\bexceda\b|\bhigher than\b|\blower than\b|\breaches\b|\bat most\b|\bno more than\b|\bcomo m[aá]ximo\b|\bcomo m[ií]nimo\b|"
    r"\bexcede\b|\bigual\b|\bes (?:\"|'|uno de)|\bcontiene\b|\bantes\b|\bdespu[eé]s\b|"
    r"\b(?:is|es|=) (?:true|false|verdadero|falso|\d)|\bor more\b|\bo m[aá]s\b|\bat least\b|\bal menos\b)(?P<rest>[^\n]{0,160})",
    re.I,
)
# "1. hazmat or oversize -> POOL" / "premium => priority lane": a rule table written with arrows. The left side is a
# condition, not a quoted example sentence ('"I love it" -> POSITIVE' is a few-shot example, not a rule).
ARROW_RULE = re.compile(r"(?m)^[ \t]*(?:[-*•]|\d+[.)])?[ \t]*(?P<cond>[^\"'“\n][^\n]{1,80}?)[ \t]*(?:->|→|=>)[ \t]*(?P<out>[\"'`]?[\w-]{2,30}[\"'`]?)[ \t.]*$")
FEW_SHOT = re.compile(r"(?im)^\s*(?:example\s*\d*|ejemplo\s*\d*|input|entrada|q|user)\s*\d*\s*[:\-]")


@dataclass
class Signal:
    name: str
    weight: float
    evidence: str


@dataclass
class TaskProfile:
    step_id: str
    tasks: dict[str, list[str]] = field(default_factory=dict)  # task -> matched spans
    primary: str = "unknown"
    output_space: str = "unknown"  # closed | structured | open | unknown
    labels: list[str] = field(default_factory=list)
    label_sources: list[str] = field(default_factory=list)
    explicit_rules: list[str] = field(default_factory=list)
    input_structured: bool | None = None
    input_evidence: list[str] = field(default_factory=list)
    free_text_inputs: list[str] = field(default_factory=list)
    judgment: list[str] = field(default_factory=list)
    reasoning_requested: list[str] = field(default_factory=list)
    reasoning_consumed: bool | None = None
    risk_domains: dict[str, str] = field(default_factory=dict)
    untrusted_input: bool = False
    few_shot: int = 0
    static_tokens: int = 0
    instruction_tokens: int = 0
    short_output: bool = False
    prompt_resolved: bool = True
    consumers: list[str] = field(default_factory=list)  # node ids
    controls_branch: bool = False
    model: ModelInfo | None = None
    determinism: dict = field(default_factory=dict)

    def has(self, task: str) -> bool:
        return task in self.tasks


def _spans(rx: re.Pattern[str], text: str, limit: int = 3) -> list[str]:
    out = []
    for m in rx.finditer(text):
        a, b = max(0, m.start() - 20), min(len(text), m.end() + 20)
        out.append(text[a:b].replace("\n", " ").strip())
        if len(out) >= limit:
            break
    return out


_ASSIGNED_LABEL = re.compile(
    r"(?:(?i:mark|label|flag|tag|set|rate|grade|assign|classify|categori[sz]e|return|answer|respond|output|reply|use|"
    r"marca|etiqueta|asigna|clasifica|califica|devuelve|responde|usa))\w*\s+(?:(?i:it|this|them|the|each|that|la|el|lo|los|las)"
    r"(?:\s+\w+)?\s+)?(?:(?i:as|to|with|como|con|a)\s+)?[\"'`“]?([A-Z][A-Z0-9_]{1,30})\b"
    r"|(?i:otherwise|else|default|in (?:all |any )?other cases?|de lo contrario|en (?:cualquier )?otro caso|si no)[,:]?\s+(?:(?i:use|return|mark|it is|es)\s+)?[\"'`“]?([A-Z][A-Z0-9_]{1,30})\b"
    # copula after a rule clause: "anything lower is GREEN", "la prioridad es URGENTE" (3+ letters: no country codes)
    r"|\b(?i:is|are|becomes|es|son|ser[aá])\s+[\"'`“]?([A-Z][A-Z0-9_]{2,30})\b"
)
_NOT_LABELS = {"JSON", "YAML", "CSV", "XML", "API", "URL", "ID", "PDF", "HTML", "SQL", "ISO", "UTC", "USD", "EUR", "GBP", "TODO",
               "NOTE", "IMPORTANT", "ONLY", "NOT", "MUST", "NEVER", "ALWAYS", "DO", "NO", "OK", "AI", "LLM", "UI", "UX", "IF"}


def _prompt_labels(text: str) -> list[str]:
    labels: list[str] = []
    # "one of: A, B, C" / "categories: billing, refund or other" / "responde con una de: ..."
    for m in re.finditer(r"(?i)(?:one of|either|categories|labels|options|values|classes|queues|exactly one|allowed(?: values| labels| categories)?|una de|categor[ií]as|etiquetas|opciones|valores|permitidas?)\s*(?:the following)?\s*[:(\[]?\s*([^\n.]{3,200})", text):
        chunk = m.group(1)
        quoted = re.findall(r"[\"'`“”‘’]([\w][\w /&-]{0,40})[\"'`“”‘’]", chunk)
        cands = quoted or [c.strip(" *-`'\"") for c in re.split(r",|\bor\b|\bo\b|\|| / ", chunk)]
        cands = [c for c in cands if c and len(c) <= 40 and len(c.split()) <= 4]
        if 2 <= len(cands) <= 25:
            labels += cands
            break
    # bullet list under a "categories:" style header
    m = re.search(r"(?im)^(?:.*\b(?:categories|labels|options|queues|categor[ií]as|etiquetas|opciones)\b.*:)\s*\n((?:\s*[-*•]\s*[^\n]{1,60}\n?){2,25})", text)
    if m and not labels:
        for line in m.group(1).splitlines():
            item = line.strip(" -*•\t")
            item = re.split(r"\s[:\-–—(]\s?", item)[0].strip(" `'\"")
            if item and len(item) <= 40:
                labels.append(item)
    # "Respond only with HIGH, MEDIUM or LOW" / "Responde solo con ALTA, MEDIA o BAJA" (upper-case label lists)
    if not labels:
        m = re.search(r"(?i:respond|answer|reply|return|output|responde|contesta|devuelve)\w*\s+(?i:only\s+|just\s+|solo\s+|s[oó]lo\s+|[uú]nicamente\s+)?"
                      r"(?i:with\s+|con\s+)?(?i:one of\s+|una de\s+)?[:\s]*([A-Z][A-Z0-9_]{1,30}(?:\s*(?:,|/|\||\bor\b|\bo\b)\s*[A-Z][A-Z0-9_]{1,30}){1,15})", text)
        if m:
            labels = [c.strip() for c in re.split(r",|/|\||\bor\b|\bo\b", m.group(1)) if c.strip()]
    # explicit quoted answers: answer "review" / responde "aprobado"
    if not labels:
        q = re.findall(r"(?i)\b(?:answer|respond(?: with)?|return|output|reply|responde(?: con)?|devuelve|contesta)\s+(?:with\s+)?[\"'`“]([\w][\w /-]{0,30})[\"'`”]", text)
        if len(set(q)) >= 2:
            labels = q
    # "Responde solo: aprobar, rechazar o revision" / "Answer only: yes, no, unsure" (lower-case list after a colon)
    if not labels:
        m = re.search(r"(?i)\b(?:respond|answer|reply|return|output|responde|contesta|devuelve)\w*\s+(?:(?:with|con)\s+)?"
                      r"(?:only|just|solo|s[oó]lo|[uú]nicamente|(?:a |one |una )?(?:single|sola) (?:word|palabra)|one word|una palabra|one of|una de)"
                      r"(?:\s+(?:with|con|these|estas))?\s*:\s*([^\n.]{3,160})", text)
        if m:
            cands = [c.strip(" *-`'\"“”") for c in re.split(r",|\bor\b|\bo\b|\||/", m.group(1))]
            cands = [c for c in cands if c and len(c) <= 30 and len(c.split()) <= 3]
            if 2 <= len(cands) <= 15:
                labels = cands
    # arrow rule tables: the right-hand sides are the labels
    if not labels:
        outs = [m.group("out").strip("\"'`") for m in ARROW_RULE.finditer(text) if len(m.group("cond").split()) <= 12]
        if len(set(outs)) >= 2:
            labels = outs
    # labels assigned by verb across several rule sentences: "mark the account RED ... mark it AMBER ... otherwise GREEN"
    if not labels:
        found = [g for m in _ASSIGNED_LABEL.finditer(text) if (g := m.group(1) or m.group(2) or m.group(3)) and g not in _NOT_LABELS]
        if len(set(found)) >= 2:
            labels = found
    return list(dict.fromkeys(labels))


def build_profile(step: LLMStep, graph: WorkflowGraph, catalog: ModelCatalog) -> TaskProfile:
    p = TaskProfile(step.id)
    instr_roles = {"system", "developer", "instructions", "user"}
    body = step.static_text(instr_roles)
    desc = step.static_text({"description"})
    text = body if body.strip() else desc
    # instructions only (placeholders removed) so variable names don't trigger lexicons
    instructions = re.sub(r"\{[^{}]{0,200}\}", " ", text)
    p.static_tokens = count_tokens(re.sub(r"\{[^{}]{0,200}\}", "", step.static_text()))
    p.instruction_tokens = count_tokens(instructions)
    p.prompt_resolved = len(instructions.strip()) >= 15
    p.model = catalog.resolve(step.model) if (step.model.raw or step.model.inherited) else None

    for task, rx in TASK_LEXICON.items():
        spans = _spans(rx, instructions)
        if spans:
            p.tasks[task] = spans
    if not p.tasks and body.strip() and desc.strip():
        # the body gives no task cue: the description (what the agent/skill is for) often states the job
        desc_instr = re.sub(r"\{[^{}]{0,200}\}", " ", desc)
        for task, rx in TASK_LEXICON.items():
            spans = _spans(rx, desc_instr)
            if spans:
                p.tasks[task] = spans
        if p.tasks:
            instructions = desc_instr  # primary task positions refer to the text the cues came from
    # Primary task: the earliest strong instruction usually states the job.
    if p.tasks:
        def first_pos(task: str) -> int:
            m = TASK_LEXICON[task].search(instructions)
            return m.start() if m else 10**9
        priority = {"format": 0, "validate_schema": 0, "validate_semantic": 0, "compute": 1, "extract": 2, "classify": 2,
                    "decide": 3, "translate": 3, "summarize": 3, "generate": 3, "code": 3, "reason": 5, "conversation": 6}
        p.primary = min(p.tasks, key=lambda t: (first_pos(t) // 400, priority.get(t, 4), first_pos(t)))
    if step.framework in INSTRUCTION_FRAMEWORKS and body.strip() and desc.strip() and p.primary not in MECHANICAL and not p.tasks.keys() & SEMANTIC_OPEN:
        # the description declares the job ("Converts BibTeX entries into APA 7 references"); the body only details it
        desc_instr = re.sub(r"\{[^{}]{0,200}\}", " ", desc)
        declared = [t for t in ("format", "compute", "validate_schema") if TASK_LEXICON[t].search(desc_instr)]
        if declared:
            p.primary = declared[0]
            p.tasks.setdefault(declared[0], _spans(TASK_LEXICON[declared[0]], desc_instr))

    # -- explicit rules (before the output space: a rule table naming the labels closes it) ------------------------------------------------------------------------------
    for m in RULE_SENTENCE.finditer(instructions):
        sentence = (m.group(0)).strip(" \n-*.;:")
        if re.search(r"\d|[\"'`]|\b[a-z_]+\.[a-z_]+\b|\b[a-z]+_[a-z_]+\b|\b(field|amount|total|score|age|days|country|status|tier|plan|importe|monto|d[ií]as|pa[ií]s|estado)\b", sentence, re.I):
            p.explicit_rules.append(sentence[:200])
    arrows = [m.group(0).strip(" \t-*•") for m in ARROW_RULE.finditer(instructions) if len(m.group("cond").split()) <= 12]
    if len(arrows) >= 2:
        p.explicit_rules += arrows
    p.explicit_rules = list(dict.fromkeys(p.explicit_rules))[:12]

    # -- output space ------------------------------------------------------------------------
    out = step.output
    if out.labels:
        p.labels, p.label_sources = list(out.labels), ["output_schema"]
    branch_labels: list[str] = []
    for e in graph.controlled_branches(step.id):
        branch_labels += e.attrs.get("labels", [])
    if branch_labels:
        p.controls_branch = True
        p.label_sources.append("code_branches")
        p.labels = list(dict.fromkeys(p.labels + branch_labels))
    elif graph.controlled_branches(step.id):
        p.controls_branch = True
    prompt_labels = _prompt_labels(instructions)
    if prompt_labels:
        p.label_sources.append("prompt")
        p.labels = list(dict.fromkeys(p.labels + prompt_labels))
    if BOOLEAN_OUT.search(instructions) or out.kind == OutputKind.BOOLEAN:
        p.label_sources.append("boolean")
        p.labels = list(dict.fromkeys(p.labels + ["yes", "no"]))
    p.short_output = bool(SHORT_OUT.search(instructions)) or (out.max_tokens is not None and out.max_tokens <= 32)
    in_rules = [l for l in p.labels if any(re.search(rf"(?i)(?<!\w){re.escape(l)}(?!\w)", r) for r in p.explicit_rules)]
    label_var = re.search(r"(?i)\b(exactly one|one|una|exactamente una) (of|de) (these|the following|the|estas|las siguientes)( \w+)?\s*[:(]?\s*\{", text)
    if out.kind in (OutputKind.ENUM, OutputKind.BOOLEAN) or (p.labels and (p.short_output or "output_schema" in p.label_sources or "code_branches" in p.label_sources
                                                                             or len(in_rules) >= 2)):
        p.output_space = "closed"
    elif label_var and not p.labels:
        # "exactly one of these categories: {names}": a closed set whose members come from a variable
        p.output_space = "closed"
        p.label_sources.append("prompt_variable")
    elif out.kind in (OutputKind.SCHEMA, OutputKind.JSON, OutputKind.TOOL_CALL) or re.search(r"(?i)\b(json|yaml)\b", instructions):
        p.output_space = "structured"
    elif p.tasks.keys() & SEMANTIC_OPEN or (out.max_tokens or 0) >= 500:
        p.output_space = "open"

    # -- inputs ---------------------------------------------------------------------------------
    vars_ = [v for v in step.variables() if v.source != VarSource.CONSTANT]
    structured = [v for v in vars_ if v.structured is True]
    free = [v for v in vars_ if v.structured is False]
    p.free_text_inputs = [v.name for v in free]
    if STRUCTURED_INPUT_TEXT.search(instructions):
        p.input_evidence.append("prompt describes structured input: " + _spans(STRUCTURED_INPUT_TEXT, instructions, 1)[0])
    if FREE_TEXT_INPUT_TEXT.search(instructions):
        p.input_evidence.append("prompt describes free-text input: " + _spans(FREE_TEXT_INPUT_TEXT, instructions, 1)[0])
    free_fields = []
    if structured or STRUCTURED_INPUT_TEXT.search(instructions):
        label_set = {l.lower() for l in p.labels}
        for m in FREE_TEXT_FIELD.finditer(instructions):
            word = next((g for g in m.groups() if g and g.lower() not in ("field", "key", "property", "attribute", "column", "campo", "columna")), "")
            if word and word.lower() not in label_set:
                free_fields.append(word)
    if free or FREE_TEXT_INPUT_TEXT.search(instructions):
        p.input_structured = False
    elif structured or STRUCTURED_INPUT_TEXT.search(instructions):
        # structured container whose fields hold prose ({"complaint": "..."}) is not structured for our purposes
        p.input_structured = None if free_fields else True
        if free_fields:
            p.input_evidence.append(f"structured container with free-text fields: {sorted(set(f.lower() for f in free_fields))[:4]}")
    if structured:
        p.input_evidence.append("structured variables: " + ", ".join(v.name for v in structured[:3]))
    if free:
        p.input_evidence.append("free-text variables: " + ", ".join(v.name for v in free[:3]))
    p.untrusted_input = any(v.source in (VarSource.USER_INPUT, VarSource.RETRIEVAL, VarSource.TOOL_RESULT) for v in vars_) or bool(free)
    if p.primary == "unknown" and p.input_structured is True and p.output_space == "structured":
        # "Here is a CSV export... Return a JSON object {...}": a structure-to-structure transformation
        p.primary = "extract"
        p.tasks["extract"] = ["inferred: structured input transformed into a structured output"]

    # -- semantics, risk, reasoning ------------------------------------------------------------------
    p.judgment = _spans(JUDGMENT, instructions, 6)
    for dom, rx in RISK.items():
        s = _spans(rx, instructions + "\n" + desc, 1)
        if s:
            p.risk_domains[dom] = s[0]
    p.reasoning_requested = _spans(REASONING_REQ, instructions, 2)
    if step.thinking:
        p.reasoning_requested.append(f"thinking/effort configured: {step.thinking}")
    consumers = graph.consumers(step.id)
    p.consumers = [c.id for c in consumers]
    if p.reasoning_requested:
        if p.output_space == "closed" and not consumers:
            p.reasoning_consumed = False
        elif any(c.kind == NodeKind.LLM_STEP for c in consumers):
            p.reasoning_consumed = None
    p.few_shot = len(FEW_SHOT.findall(instructions))

    from ai_auditor.optimization.determinism import determinism_score

    p.determinism = determinism_score(p, step)
    return p
