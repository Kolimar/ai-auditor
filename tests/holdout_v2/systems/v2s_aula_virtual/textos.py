NOTA_FINAL = """Calcula la nota final del alumno. La ponderación es: examen parcial 30 %,
tareas 20 %, examen final 50 %. Aplica la fórmula con los tres valores recibidos (escala 0 a 10)
y redondea el resultado a un decimal. Si el alumno tiene más de tres faltas injustificadas resta 0,5
puntos antes de redondear. Devuelve solo el número."""

CLASIFICAR_FORO = (
    "Una alumna o alumno ha escrito en el foro del curso. Dime si la pregunta trata sobre contenido "
    "técnico de la materia, sobre un trámite administrativo (matrícula, certificados, plazos) o sobre "
    "problemas de la plataforma. Responde con una sola palabra: tecnica, administrativa o plataforma."
)

RESUMEN_LECCION = "Resume la transcripción de la clase en un párrafo con las ideas principales."

RESUMEN_DEL_RESUMEN = (
    "A partir del siguiente resumen de clase, escribe un resumen más corto, de dos frases, con lo más importante."
)

EJERCICIOS = (
    "Diseña {n} ejercicios de práctica para el tema '{tema}', de dificultad creciente, pensados para "
    "estudiantes de nivel {nivel}. Incluye una pista breve para cada uno y evita repetir el enfoque."
)

CORRECCION = (
    "Corrige el ensayo según la rúbrica adjunta. Para cada criterio explica qué hizo bien el estudiante, "
    "qué puede mejorar y propone una frase de ejemplo. Habla directamente al estudiante con tono "
    "alentador."
)

TUTOR = (
    "Eres un tutor de matemáticas. Resuelve el problema delante del estudiante paso a paso, explicando "
    "tu razonamiento en cada paso para que pueda seguirlo, y termina con una pregunta de comprobación."
)

RESPUESTA_CURSO = (
    "Responde a la pregunta del estudiante usando únicamente los materiales del curso incluidos en el "
    "contexto. Si no aparece la respuesta, dilo."
)

REPORTE_SEMANAL = (
    "Escribe un breve informe semanal para la familia sobre el progreso del estudiante, con un tono "
    "cercano. Datos de la semana: {datos}"
)
