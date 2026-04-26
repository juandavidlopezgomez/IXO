import json
import os

import anthropic

from apis.odds_api import get_events_in_range
from apis.api_sports import get_team_stats, get_h2h_stats
from apis.totalfootball import get_live_matches as fetch_live
from tools import TOOLS

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """Eres un analista experto en apuestas deportivas con más de 20 años de experiencia. \
Tu objetivo es identificar apuestas de alto valor con cuotas entre 1.40 y 1.70 en cualquier deporte.

━━━ METODOLOGÍA DE ANÁLISIS ━━━
Analiza cada apuesta usando estos factores por orden de importancia:
1. Forma reciente del equipo (últimos 5-10 partidos): PESO 40%
2. Estadísticas de rendimiento (goles, puntos, eficiencia): PESO 25%
3. Historial de enfrentamientos directos H2H: PESO 20%
4. Ventaja de local vs visitante: PESO 15%

━━━ CRITERIO ESTRICTO DE RECOMENDACIÓN ━━━
Solo recomienda una apuesta SI y SOLO SI:
  - Tu probabilidad estimada >= probabilidad implícita de la cuota + 5% de margen de seguridad
  - Hay CONSISTENCIA entre la forma reciente, las estadísticas y el H2H
  - No hay factores negativos graves (racha muy mala, inferioridad notoria)

Fórmula probabilidad implícita = (1 ÷ cuota) × 100
Ejemplo: cuota 1.55 → prob implícita 64.5% → recomienda SOLO si tu análisis indica ≥ 69.5%

━━━ PROCESO OBLIGATORIO ━━━
1. Llama get_events_in_odds_range(sport="all") para obtener todos los candidatos
2. Para cada partido de fútbol prometedor, llama get_team_statistics en AMBOS equipos
3. Para los mejores candidatos, llama get_head_to_head
4. Llama get_live_matches para incluir oportunidades en vivo
5. Analiza todo y produce el JSON final

━━━ FORMATO DE RESPUESTA FINAL ━━━
Termina SIEMPRE con un bloque JSON válido con esta estructura exacta:
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
      "prob_estimada": 73.0,
      "nivel_confianza": "ALTA",
      "razonamiento": "Arsenal lleva 7V-1E-2D en los últimos 10 partidos...",
      "recomendar": true
    }
  ],
  "total_analizadas": 25,
  "total_recomendadas": 5,
  "resumen": "5 apuestas recomendadas de 25 analizadas"
}
```

Si no recomiendas ninguna apuesta, el array predicciones puede ser vacío o solo contener \
las de recomendar=false con explicación. Sé honesto: es mejor NO recomendar que arriesgar \
con análisis dudoso."""


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
    # Try to find JSON code block first
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

    # Fallback: find outermost { }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    return None


def run() -> dict:
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    messages = [
        {
            "role": "user",
            "content": (
                "Analiza todos los deportes disponibles ahora mismo. "
                "Busca apuestas con cuotas entre 1.40 y 1.70, analiza estadísticas "
                "de los equipos más prometedores y dame tus mejores predicciones "
                "con alto porcentaje de acierto."
            ),
        }
    ]

    max_iterations = 12  # prevent infinite loops

    for _ in range(max_iterations):
        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    parsed = _extract_json(block.text)
                    if parsed:
                        return parsed
            return {
                "predicciones": [],
                "resumen": "No se pudo extraer JSON de la respuesta",
                "respuesta_raw": next(
                    (b.text for b in response.content if hasattr(b, "text")), ""
                ),
            }

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_str = _process_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return {"predicciones": [], "resumen": "El agente no completó el análisis"}
