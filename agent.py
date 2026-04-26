import json
import os

from groq import Groq

from apis.odds_api import get_events_in_range
from apis.api_sports import get_team_stats, get_h2h_stats
from apis.totalfootball import get_live_matches as fetch_live
from tools import TOOLS

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Eres un analista experto en apuestas deportivas. Tu misión es identificar las mejores apuestas con cuotas entre 1.40 y 1.70 usando datos reales de APIs.

PROCESO OBLIGATORIO:
1. Llama get_events_in_odds_range con sport="all" para obtener todos los candidatos
2. Para cada partido de fútbol interesante, llama get_team_statistics en ambos equipos
3. Llama get_head_to_head para los mejores candidatos
4. Llama get_live_matches para ver oportunidades en vivo
5. Analiza todo y produce el JSON final

METODOLOGÍA DE PUNTUACIÓN (0-100 puntos por apuesta):
- Forma reciente últimos 5 partidos: hasta 40 puntos
  * 5 victorias = 40 pts, 4V = 32 pts, 3V = 24 pts, 2V = 16 pts
- Promedio de goles marcados vs encajados: hasta 25 puntos
  * Si marca más de 2 por partido y encaja menos de 1 = 25 pts
- Historial H2H favorable: hasta 20 puntos
  * Gana más del 60% de los H2H = 20 pts
- Condición local/visitante: hasta 15 puntos
  * Si juega de local y tiene buen % como local = 15 pts

CRITERIO DE RECOMENDACIÓN:
- Calcula tu probabilidad estimada = puntuación / 100
- Probabilidad implícita = (1 / cuota) × 100
- Solo recomienda si: prob_estimada >= prob_implicita + 5%
- Ejemplo: cuota 1.55 → prob implícita 64.5% → recomendar solo si tu análisis da ≥ 69.5%

RESPUESTA FINAL:
Termina SIEMPRE con este JSON exacto (sin texto después):

```json
{
  "predicciones": [
    {
      "deporte": "Fútbol - Premier League",
      "partido": "Arsenal vs Chelsea",
      "mercado": "Resultado final",
      "seleccion": "Arsenal",
      "cuota": 1.52,
      "prob_implicita": 65.8,
      "prob_estimada": 74.0,
      "nivel_confianza": "ALTA",
      "razonamiento": "Arsenal: 4V-1E en últimos 5, promedio 2.1 goles marcados y 0.8 encajados...",
      "recomendar": true
    }
  ],
  "total_analizadas": 20,
  "total_recomendadas": 4,
  "resumen": "4 apuestas recomendadas de 20 analizadas"
}
```

nivel_confianza: "ALTA" si prob_estimada >= 75%, "MEDIA" si >= 70%, "BAJA" si >= 65%
Si no hay apuestas que cumplan el criterio, devuelve predicciones vacío y explica en resumen."""


def _process_tool(name: str, tool_input: dict) -> str:
    odds_key = os.environ["ODDS_API_KEY"]
    sports_key = os.environ["API_SPORTS_KEY"]
    rapid_key = os.environ["RAPIDAPI_KEY"]

    if name == "get_events_in_odds_range":
        result = get_events_in_range(
            odds_key,
            sport=tool_input.get("sport", "all"),
            min_odds=tool_input.get("min_odds", 1.40),
            max_odds=tool_input.get("max_odds", 1.70),
        )
    elif name == "get_team_statistics":
        result = get_team_stats(sports_key, tool_input["team_name"])
    elif name == "get_head_to_head":
        result = get_h2h_stats(sports_key, tool_input["team1"], tool_input["team2"])
    elif name == "get_live_matches":
        result = fetch_live(rapid_key)
    else:
        result = {"error": f"Herramienta desconocida: {name}"}

    return json.dumps(result, ensure_ascii=False)


def _extract_json(text: str) -> dict | None:
    for marker in ("```json", "```"):
        start = text.find(marker)
        if start != -1:
            end = text.find("```", start + len(marker))
            if end != -1:
                fragment = text[start + len(marker):end].strip()
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    pass

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return None


def run() -> dict:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Analiza todos los deportes disponibles ahora mismo. "
                "Busca apuestas con cuotas entre 1.40 y 1.70, analiza estadísticas "
                "de los equipos más prometedores y dame tus mejores predicciones. "
                "Empieza llamando las herramientas ya."
            ),
        },
    ]

    max_iterations = 15

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=4096,
            temperature=0.2,
        )

        choice = response.choices[0]
        message = choice.message

        # Agregar respuesta del asistente al historial
        messages.append(message.model_dump(exclude_unset=False))

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            for tc in message.tool_calls:
                try:
                    tool_input = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    tool_input = {}

                result_str = _process_tool(tc.function.name, tool_input)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_str,
                })

        elif choice.finish_reason == "stop":
            content = message.content or ""
            parsed = _extract_json(content)
            if parsed:
                return parsed
            return {
                "predicciones": [],
                "resumen": "No se pudo extraer JSON de la respuesta",
                "respuesta_raw": content,
            }
        else:
            break

    return {"predicciones": [], "resumen": "El agente no completó el análisis"}
