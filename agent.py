import json
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from groq import Groq

from apis.odds_api import get_events_in_range, find_match
from apis.api_sports import get_team_stats, get_h2h_stats
from apis.totalfootball import get_live_matches as fetch_live
from tools import TOOLS

MODEL = "llama-3.3-70b-versatile"


def _now_context() -> str:
    tz = ZoneInfo(os.environ.get("LOCAL_TZ", "America/Bogota"))
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    return (
        f"FECHA Y HORA ACTUAL:\n"
        f"  - UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"  - Local ({tz}): {now_local.strftime('%Y-%m-%d %H:%M:%S')} ({now_local.strftime('%A')})\n"
        f"  - SOLO analiza partidos que NO han comenzado todavía (ignora 'EN CURSO o terminado')."
    )


def _build_system_prompt_general() -> str:
    return f"""Eres un analista experto en apuestas deportivas con 20+ años de experiencia. \
Tu misión: identificar las MEJORES apuestas del día con cuotas entre 1.40 y 1.70.

{_now_context()}

═══════ PROCESO OBLIGATORIO ═══════
PASO 1: Llama get_events_in_odds_range(sport="all", hours_ahead=36) para ver candidatos.
PASO 2: Para los partidos de FÚTBOL más prometedores (top 5-8), llama get_team_statistics \
en AMBOS equipos para conocer su forma reciente.
PASO 3: Para los 3 mejores candidatos, llama get_head_to_head para confirmar tendencia.
PASO 4: Opcional: llama get_live_matches por si hay partidos en curso interesantes.
PASO 5: Responde con el JSON final.

═══════ METODOLOGÍA DE ANÁLISIS (puntuación 0-100) ═══════
• Forma últimos 5 partidos del equipo seleccionado: hasta 40 puntos
   - 5V=40, 4V=32, 3V+1E=28, 3V=24, 2V+2E=20, 2V=16, 1V=8
• Diferencia de goles (marcados − encajados, promedio): hasta 25 puntos
   - >+1.5 = 25, +1 a +1.5 = 20, +0.5 a +1 = 15, 0 a +0.5 = 10
• Historial H2H favorable (>50% victorias): hasta 20 puntos
   - >70% = 20, 60-70% = 15, 50-60% = 10
• Condición local (si juega en casa con buen %): hasta 15 puntos
   - >70% local = 15, 50-70% = 10
Para deportes NO-fútbol (NBA, NFL, etc.) usa solo análisis de cuotas y ráfagas \
de bookmakers (consenso entre múltiples casas = más confianza).

═══════ CRITERIO ESTRICTO DE RECOMENDACIÓN ═══════
• prob_estimada = puntuación_total / 100 (en %)
• prob_implícita = (1 / cuota) × 100
• RECOMIENDA solo si: prob_estimada ≥ prob_implícita + 5%
• Ejemplo: cuota 1.55 → prob implícita 64.5% → solo si tu análisis ≥ 69.5%
• Sé HONESTO: mejor 0 recomendaciones que apuestas dudosas.

═══════ RESPUESTA FINAL (OBLIGATORIO JSON) ═══════
Termina SIEMPRE con este bloque (sin texto después del cierre):
```json
{{
  "predicciones": [
    {{
      "deporte": "Fútbol - Premier League",
      "partido": "Arsenal vs Chelsea",
      "cuando": "HOY 19:30",
      "mercado": "Resultado final",
      "seleccion": "Arsenal",
      "cuota": 1.52,
      "prob_implicita": 65.8,
      "prob_estimada": 74.0,
      "nivel_confianza": "ALTA",
      "razonamiento": "Arsenal: 4V-1E últimos 5, +1.4 goles diferencia, gana 75% en casa, H2H 6-2 favor.",
      "recomendar": true
    }}
  ],
  "total_analizadas": 20,
  "total_recomendadas": 4,
  "resumen": "4 apuestas recomendadas de 20 analizadas"
}}
```

nivel_confianza: "ALTA" si prob_estimada ≥ 75%, "MEDIA" si ≥ 70%, "BAJA" si ≥ 65%.
Si nada cumple el criterio, devuelve predicciones=[] con explicación en resumen."""


def _build_system_prompt_match(query: str) -> str:
    return f"""Eres un analista experto en apuestas deportivas. El usuario pide tu predicción \
sobre un partido ESPECÍFICO: "{query}".

{_now_context()}

═══════ PROCESO OBLIGATORIO ═══════
PASO 1: Llama find_specific_match(query="{query}") para localizar el partido y ver TODAS sus cuotas.
PASO 2: Si es fútbol, llama get_team_statistics para ambos equipos.
PASO 3: Llama get_head_to_head para conocer su historial directo.
PASO 4: Analiza TODOS los mercados disponibles (1X2, Over/Under, etc.)
PASO 5: Responde con el JSON final indicando la MEJOR apuesta del partido.

═══════ ANÁLISIS DETALLADO ═══════
• Compara forma reciente de ambos equipos
• Calcula probabilidad real de cada resultado posible
• Identifica el mercado con mejor relación probabilidad/cuota
• Si hay alguna apuesta entre 1.40-1.70 con valor → recomiéndala
• Si todas las cuotas son malas o tu confianza es baja → di NO apostar

═══════ RESPUESTA FINAL (JSON OBLIGATORIO) ═══════
```json
{{
  "partido_analizado": "Real Madrid vs Barcelona",
  "cuando": "HOY 21:00",
  "deporte": "Fútbol",
  "analisis_general": "Real Madrid llega con 4V-1D, Barcelona 3V-2D. H2H favorable a Real Madrid.",
  "mejor_prediccion": {{
    "mercado": "Resultado final",
    "seleccion": "Real Madrid",
    "cuota": 1.65,
    "prob_implicita": 60.6,
    "prob_estimada": 72.0,
    "nivel_confianza": "MEDIA",
    "razonamiento": "Forma superior, juega de local, H2H 7-3 últimos 10.",
    "recomendar": true
  }},
  "alternativas": [
    {{
      "mercado": "Más de 2.5 goles",
      "cuota": 1.55,
      "prob_estimada": 68.0,
      "razonamiento": "Promedio H2H 3.2 goles por partido."
    }}
  ]
}}
```

Si no encuentras el partido, devuelve {{"error": "Partido no encontrado: ..."}}."""


# ─── Cache simple de stats para evitar llamadas duplicadas ──────────────────
_team_stats_cache: dict = {}
_h2h_cache: dict = {}


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
            hours_ahead=tool_input.get("hours_ahead", 36),
        )
    elif name == "find_specific_match":
        result = find_match(odds_key, tool_input["query"])
    elif name == "get_team_statistics":
        team_name = tool_input["team_name"]
        if team_name in _team_stats_cache:
            result = _team_stats_cache[team_name]
        else:
            result = get_team_stats(sports_key, team_name)
            _team_stats_cache[team_name] = result
    elif name == "get_head_to_head":
        key = tuple(sorted([tool_input["team1"], tool_input["team2"]]))
        if key in _h2h_cache:
            result = _h2h_cache[key]
        else:
            result = get_h2h_stats(sports_key, tool_input["team1"], tool_input["team2"])
            _h2h_cache[key] = result
    elif name == "get_live_matches":
        result = fetch_live(rapid_key)
    else:
        result = {"error": f"Herramienta desconocida: {name}"}

    return json.dumps(result, ensure_ascii=False)


def _extract_json(text: str) -> dict | None:
    if not text:
        return None

    # Buscar bloque JSON marcado con ```json o ```
    for marker in ("```json", "```"):
        start = text.find(marker)
        while start != -1:
            end = text.find("```", start + len(marker))
            if end != -1:
                fragment = text[start + len(marker):end].strip()
                try:
                    return json.loads(fragment)
                except json.JSONDecodeError:
                    pass
            start = text.find(marker, start + len(marker))

    # Buscar el bloque {} más exterior y bien formado
    depth = 0
    json_start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                json_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and json_start != -1:
                try:
                    return json.loads(text[json_start:i + 1])
                except json.JSONDecodeError:
                    json_start = -1

    return None


def _serialize_message(msg) -> dict:
    """Convierte un ChatCompletionMessage a dict válido para el historial."""
    out = {"role": msg.role}
    if msg.content is not None:
        out["content"] = msg.content
    if getattr(msg, "tool_calls", None):
        out["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in msg.tool_calls
        ]
    if "content" not in out:
        out["content"] = ""
    return out


def _run_loop(client: Groq, system_prompt: str, user_message: str, max_iterations: int = 15) -> dict:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

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
        messages.append(_serialize_message(message))

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


def run_general() -> dict:
    """Análisis general: encuentra las mejores apuestas del día/futuras."""
    _team_stats_cache.clear()
    _h2h_cache.clear()

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    system = _build_system_prompt_general()
    user = (
        "Analiza TODOS los deportes con apuestas en cuotas 1.40-1.70 que comiencen "
        "en las próximas 36 horas. Usa todas las herramientas necesarias y dame "
        "tus mejores predicciones del día con alto porcentaje de acierto."
    )
    return _run_loop(client, system, user)


def run_match(query: str) -> dict:
    """Analiza un partido específico que el usuario consulta."""
    _team_stats_cache.clear()
    _h2h_cache.clear()

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    system = _build_system_prompt_match(query)
    user = f"Analiza el partido: {query}. Dame tu mejor predicción detallada."
    return _run_loop(client, system, user)


# Compatibilidad con versión anterior
def run() -> dict:
    return run_general()
