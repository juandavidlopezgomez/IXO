# Formato OpenAI/Groq compatible
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_events_in_odds_range",
            "description": (
                "Obtiene eventos deportivos de todos los deportes disponibles cuyas cuotas "
                "están entre 1.40 y 1.70. Devuelve lista de apuestas con deporte, equipos, "
                "mercado, cuota y probabilidad implícita. Llama esta herramienta primero."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": "Clave del deporte (ej: 'soccer_epl'). Usa 'all' para todos.",
                    },
                    "min_odds": {"type": "number", "description": "Cuota mínima", "default": 1.40},
                    "max_odds": {"type": "number", "description": "Cuota máxima", "default": 1.70},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_team_statistics",
            "description": (
                "Obtiene estadísticas recientes de un equipo de fútbol: forma últimos 10 partidos, "
                "victorias, empates, derrotas, goles marcados/encajados, rendimiento local y visitante."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "Nombre del equipo (ej: 'Real Madrid', 'Arsenal')",
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
                "Obtiene el historial H2H entre dos equipos de fútbol: quién ganó más, "
                "promedio de goles, porcentaje de partidos con más de 2.5 goles."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "team1": {"type": "string", "description": "Nombre del primer equipo"},
                    "team2": {"type": "string", "description": "Nombre del segundo equipo"},
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
                "Obtiene partidos de fútbol en vivo ahora mismo: marcador actual, minuto "
                "y estadísticas en tiempo real para detectar oportunidades en partidos en curso."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]
