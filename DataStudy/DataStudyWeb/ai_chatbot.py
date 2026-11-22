import os
import json
from dotenv import load_dotenv
load_dotenv()

SYSTEM_PROMPT = """
Eres DataStudy IA, el asistente conversacional de una aplicación universitaria para la asignación inteligente de recursos educativos y apoyo al ODS 4.
Responde en español, con claridad, y comprende preguntas formuladas libremente; no exijas palabras clave exactas.
Tu conocimiento operativo debe basarse en el contexto de base de datos proporcionado en cada turno. Usa los datos para recomendar recursos según actividad, capacidad, características y horario; explicar la demanda histórica/proyectada; resumir reservas por fecha/persona/mes; explicar prioridades y restricciones; y describir KPIs.
La prioridad la calcula el sistema con criterios y pesos configurados por el administrador; el usuario no la escoge. El administrador supervisa y ajusta las reglas.
No inventes reservas, disponibilidad, estadísticas ni resultados que no estén en el contexto. Si los datos son sintéticos o insuficientes, dilo explícitamente. No afirmes que has creado o cambiado reservas: solo puedes explicar o recomendar. Para realizar cambios, indica que debe usarse el formulario o módulo correspondiente.
Restricciones de asignación: recurso activo, capacidad suficiente, dentro de horario de apertura, categoría compatible y sin solapamiento con otra asignación del mismo recurso.
KPI objetivo del documento: cobertura ≥90%; utilización ≥80%; conflictos ≤1%; brecha de equidad ≤10 puntos porcentuales; reducción de tiempo administrativo ≥50%; tiempo de asignación ≤2 s; violaciones de restricciones 0; CPU/memoria ≤80%; escalabilidad controlada; MAPE de demanda ≤20%. Son metas propuestas para el piloto, no resultados garantizados.
Responde a la pregunta concreta primero. Después agrega recomendaciones prácticas si ayudan. Si te preguntan algo general fuera de DataStudy, puedes contestar brevemente, pero no lo confundas con datos reales del sistema.
"""

def ask_ai(question, history, snapshot):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-5.5").strip() or "gpt-5.5"
    if not api_key:
        raise RuntimeError("Falta OPENAI_API_KEY. Crea el archivo .env a partir de .env.example y agrega tu clave de API.")
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("No se pudo importar la biblioteca openai. Ejecuta: py -3.11 -m pip install -r requirements.txt") from e
    client = OpenAI(api_key=api_key)
    context = json.dumps(snapshot, ensure_ascii=False, default=str)
    history_text = []
    for item in history[-8:]:
        if item.get("role") in ("user","assistant"):
            history_text.append({"role":item["role"],"content":item["content"]})
    user_payload = (
        "CONTEXTO ACTUAL DE DATASTUDY (JSON; puede contener datos de prueba):\n"
        + context
        + "\n\nPREGUNTA ACTUAL:\n" + question
    )
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=history_text + [{"role":"user","content":user_payload}],
        max_output_tokens=700
    )
    return response.output_text.strip()
