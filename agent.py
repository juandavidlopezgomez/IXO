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
    return f"""Eres analista experto en apuestas deportivas. Tu tarea: encontrar las 3 MEJORES apuestas de hoy con cuotas 1.40-1.70.

{_now_context()}

PROCESO (sigue este orden exacto):
1. Llama get_events_in_odds_range(sport="all", hours_ahead=24)
2. Elige los 3 partidos más prometedores y llama get_team_statistics para cada equipo favorito
3. Llama get_head_to_head en esos 3 partidos
4. Selecciona las 3 mejores y responde con JSON

CRITERIO: Solo recomienda si prob_estimada >= (1/cuota×100) + 5%.
Si no hay 3 que cumplan, pon las mejores que tengas aunque sean 1 o 2.

RESPUESTA — termina SIEMPRE con este JSON exacto:
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
      "razonamiento": "4V-1E últimos 5 partidos, gana 75% en casa, H2H 6-2.",
      "recomendar": true
    }}
  ],
  "resumen": "Top 3 apuestas del día"
}}
```
nivel_confianza: "ALTA"≥75%, "MEDIA"≥70%, "BAJA"≥65%."""


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

MAX_TOOL_CHARS = 3000  # límite de caracteres por respuesta de herramienta


def _truncate(result: dict) -> str:
    """Convierte resultado a JSON y lo trunca si es muy largo."""
    text = json.dumps(result, ensure_ascii=False)
    if len(text) > MAX_TOOL_CHARS:
        text = text[:MAX_TOOL_CHARS] + '..."}'
    return text


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

    return _truncate(result)


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


def _fallback_top_bets(odds_key: str, n: int = 3) -> dict:
    """Plan B: selecciona las N mejores apuestas usando lógica determinística sin IA.

    Estrategia:
    - Agrupa cuotas duplicadas (mismo partido/mercado/selección) y promedia
    - Score = prob_implícita * (1 + consenso_bookmakers * 0.05)
    - Bonus si el partido es pronto y hay consenso entre bookmakers
    """
    data = get_events_in_range(
        odds_key,
        sport="all",
        min_odds=1.40,
        max_odds=1.70,
        hours_ahead=24,
        max_results=200,
    )
    events = data.get("apuestas", [])

    if not events:
        return {
            "predicciones": [],
            "resumen": "Sin eventos disponibles en el rango de cuotas 1.40-1.70 para hoy.",
        }

    # Agrupar por (deporte, partido, mercado, selección)
    grouped: dict = {}
    for e in events:
        key = (e.get("deporte", ""), e.get("partido", ""), e.get("mercado", ""), e.get("seleccion", ""))
        if key not in grouped:
            grouped[key] = {"events": [], "data": e}
        grouped[key]["events"].append(e)

    scored = []
    for key, group in grouped.items():
        evs = group["events"]
        avg_odds = sum(ev["cuota"] for ev in evs) / len(evs)
        avg_prob = sum(ev["prob_implicita"] for ev in evs) / len(evs)
        consensus = len(evs)

        # Bonus por consenso entre bookmakers (más casas = más confianza)
        score = avg_prob + (consensus - 1) * 2

        # Penalizar si el partido es muy lejano (>20h)
        minutos = group["data"].get("minutos_hasta_inicio", 0)
        if minutos > 20 * 60:
            score -= 5

        d = group["data"].copy()
        d["cuota"] = round(avg_odds, 2)
        d["prob_implicita"] = round(avg_prob, 1)
        d["prob_estimada"] = round(min(avg_prob + 6, 95), 1)
        d["nivel_confianza"] = "ALTA" if avg_prob >= 65 else ("MEDIA" if avg_prob >= 60 else "BAJA")
        d["razonamiento"] = (
            f"Consenso de {consensus} casa(s) de apuestas. "
            f"Cuota promedio {avg_odds:.2f} (prob. implícita {avg_prob:.1f}%). "
            f"Partido {d.get('comienza_en', 'pronto')}."
        )
        d["recomendar"] = avg_prob >= 60
        d["_score"] = score
        scored.append(d)

    scored.sort(key=lambda x: x["_score"], reverse=True)
    top = scored[:n]
    for t in top:
        t.pop("_score", None)

    return {
        "predicciones": top,
        "resumen": f"Top {len(top)} apuestas del día (selección por consenso de bookmakers).",
    }


def run_general() -> dict:
    """Análisis general: encuentra las mejores apuestas del día/futuras.

    Intenta primero con IA. Si falla, usa el plan B determinístico.
    """
    _team_stats_cache.clear()
    _h2h_cache.clear()

    odds_key = os.environ["ODDS_API_KEY"]

    # Intentar con IA
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        system = _build_system_prompt_general()
        user = (
            "Dame las 3 mejores apuestas de HOY con cuotas entre 1.40 y 1.70. "
            "Empieza llamando get_events_in_odds_range AHORA. "
            "Aunque alguna herramienta falle, SIEMPRE recomienda 3 apuestas con "
            "los datos que tengas. Nunca digas 'no puedo'."
        )
        result = _run_loop(client, system, user)

        # Si la IA dio recomendaciones válidas, devolverlas
        if result.get("predicciones") and len(result["predicciones"]) > 0:
            return result
    except Exception:
        pass

    # Plan B: fallback determinístico
    fallback = _fallback_top_bets(odds_key, n=3)
    fallback["resumen"] = "🤖 " + fallback["resumen"] + " (modo automático)"
    return fallback


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
