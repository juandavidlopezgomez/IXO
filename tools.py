# Formato OpenAI/Groq compatible
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_events_in_odds_range",
            "description": (
                "Obtiene apuestas FUTURAS (no incluye partidos en curso ni terminados) "
                "con cuotas en el rango pedido. Devuelve lista ordenada por hora de inicio "
                "(las más cercanas primero), incluyendo cuándo empieza cada partido. "
                "LLAMA ESTA HERRAMIENTA PRIMERO siempre."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": "Deporte específico (ej: 'soccer_epl') o 'all' para todos.",
                    },
                    "min_odds": {"type": "number", "description": "Cuota mínima", "default": 1.40},
                    "max_odds": {"type": "number", "description": "Cuota máxima", "default": 1.70},
                    "hours_ahead": {
                        "type": "number",
                        "description": "Ventana de horas hacia adelante (default 36 = hoy y mañana)",
                        "default": 36,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_specific_match",
            "description": (
                "Busca un partido específico por nombre de equipo o partido. "
                "Devuelve TODAS las cuotas disponibles (no solo las del rango). "
                "Úsala cuando el usuario pregunte por un partido concreto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nombre de equipo o partido (ej: 'Real Madrid', 'Lakers vs Warriors')",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_statistics",
            "description": (
                "Obtiene estadísticas de un equipo de FÚTBOL: forma últimos 10 partidos, "
                "victorias, empates, derrotas, goles marcados/encajados, rendimiento como "
                "local y visitante. Solo funciona para fútbol."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "Nombre del equipo en inglés preferiblemente (ej: 'Real Madrid', 'Arsenal')",
                    }
                },
                "required": ["team_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_head_to_head",
            "description": (
                "Obtiene el historial H2H entre dos equipos de fútbol: ganador histórico, "
                "promedio de goles, % de partidos con más de 2.5 goles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team1": {"type": "string", "description": "Primer equipo"},
                    "team2": {"type": "string", "description": "Segundo equipo"},
                },
                "required": ["team1", "team2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_live_matches",
            "description": (
                "Obtiene partidos de fútbol EN VIVO ahora mismo con marcador y minuto. "
                "Útil para detectar oportunidades en partidos en curso."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]
