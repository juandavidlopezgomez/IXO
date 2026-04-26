TOOLS = [
    {
        "name": "get_events_in_odds_range",
        "description": (
            "Obtiene eventos deportivos de todos los deportes disponibles cuyas cuotas "
            "están entre 1.40 y 1.70. Devuelve una lista de apuestas con el deporte, "
            "equipos, mercado, cuota y probabilidad implícita. "
            "Llama esta herramienta primero para obtener los candidatos a analizar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sport": {
                    "type": "string",
                    "description": (
                        "Clave del deporte a consultar (ej: 'soccer_epl', 'basketball_nba'). "
                        "Usa 'all' para consultar todos los deportes disponibles."
                    ),
                    "default": "all",
                },
                "min_odds": {
                    "type": "number",
                    "description": "Cuota mínima a buscar",
                    "default": 1.40,
                },
                "max_odds": {
                    "type": "number",
                    "description": "Cuota máxima a buscar",
                    "default": 1.70,
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_team_statistics",
        "description": (
            "Obtiene estadísticas recientes de un equipo de fútbol: forma en los últimos "
            "10 partidos, victorias, empates, derrotas, goles marcados/encajados, "
            "rendimiento como local y visitante. Úsala para los equipos de fútbol "
            "más prometedores que encontraste con get_events_in_odds_range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team_name": {
                    "type": "string",
                    "description": "Nombre del equipo en inglés o español (ej: 'Real Madrid', 'Arsenal')",
                },
            },
            "required": ["team_name"],
        },
    },
    {
        "name": "get_head_to_head",
        "description": (
            "Obtiene el historial de enfrentamientos directos (H2H) entre dos equipos "
            "de fútbol: quién ha ganado más, promedio de goles, porcentaje de partidos "
            "con más de 2.5 goles. Úsala cuando quieras comparar dos equipos específicos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "team1": {
                    "type": "string",
                    "description": "Nombre del primer equipo",
                },
                "team2": {
                    "type": "string",
                    "description": "Nombre del segundo equipo",
                },
            },
            "required": ["team1", "team2"],
        },
    },
    {
        "name": "get_live_matches",
        "description": (
            "Obtiene los partidos de fútbol que están en vivo ahora mismo con el marcador "
            "actual, minuto del partido y estadísticas en tiempo real. "
            "Úsala para detectar oportunidades de apuestas en partidos en curso."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
