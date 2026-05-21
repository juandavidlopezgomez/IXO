import requests

FOOTBALL_BASE = "https://v3.football.api-sports.io"


def _headers(api_key: str) -> dict:
    return {"x-apisports-key": api_key}


def search_team(api_key: str, team_name: str) -> dict | None:
    resp = requests.get(
        f"{FOOTBALL_BASE}/teams",
        headers=_headers(api_key),
        params={"search": team_name},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("response"):
        return data["response"][0]
    return None


def get_recent_fixtures(api_key: str, team_id: int, last: int = 10) -> list:
    resp = requests.get(
        f"{FOOTBALL_BASE}/fixtures",
        headers=_headers(api_key),
        params={"team": team_id, "last": last},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_h2h(api_key: str, team1_id: int, team2_id: int, last: int = 10) -> list:
    resp = requests.get(
        f"{FOOTBALL_BASE}/fixtures/headtohead",
        headers=_headers(api_key),
        params={"h2h": f"{team1_id}-{team2_id}", "last": last},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


def get_injuries(api_key: str, team_id: int) -> list:
    resp = requests.get(
        f"{FOOTBALL_BASE}/injuries",
        headers=_headers(api_key),
        params={"team": team_id, "season": 2025},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("response", [])


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_fixture_result(fixture: dict, team_id: int) -> str:
    home_id = fixture["teams"]["home"]["id"]
    home_goals = fixture["goals"]["home"] or 0
    away_goals = fixture["goals"]["away"] or 0

    if home_id == team_id:
        gf, ga = home_goals, away_goals
    else:
        gf, ga = away_goals, home_goals

    if gf > ga:
        return "W"
    if gf < ga:
        return "L"
    return "D"


def summarize_team_form(team_name: str, team_id: int, fixtures: list) -> dict:
    if not fixtures:
        return {"equipo": team_name, "mensaje": "Sin datos de partidos recientes"}

    wins = draws = losses = goals_for = goals_against = 0
    home_wins = home_played = away_wins = away_played = 0
    form_chars = []

    for f in fixtures:
        home_id = f["teams"]["home"]["id"]
        home_goals = f["goals"]["home"] or 0
        away_goals = f["goals"]["away"] or 0
        is_home = home_id == team_id

        if is_home:
            gf, ga = home_goals, away_goals
            home_played += 1
        else:
            gf, ga = away_goals, home_goals
            away_played += 1

        goals_for += gf
        goals_against += ga

        if gf > ga:
            wins += 1
            form_chars.append("V")
            if is_home:
                home_wins += 1
            else:
                away_wins += 1
        elif gf == ga:
            draws += 1
            form_chars.append("E")
        else:
            losses += 1
            form_chars.append("D")

    n = len(fixtures)
    return {
        "equipo": team_name,
        "partidos_analizados": n,
        "victorias": wins,
        "empates": draws,
        "derrotas": losses,
        "puntos_de": wins * 3 + draws,
        "porcentaje_victorias": round(wins / n * 100, 1),
        "goles_marcados_total": goals_for,
        "goles_encajados_total": goals_against,
        "promedio_goles_marcados": round(goals_for / n, 2),
        "promedio_goles_encajados": round(goals_against / n, 2),
        "forma_reciente_5": "".join(form_chars[:5]),
        "victorias_como_local": f"{home_wins}/{home_played}" if home_played else "N/A",
        "victorias_como_visitante": f"{away_wins}/{away_played}" if away_played else "N/A",
    }


def summarize_h2h(team1_name: str, team2_name: str, team1_id: int, fixtures: list) -> dict:
    if not fixtures:
        return {"mensaje": f"Sin historial H2H entre {team1_name} y {team2_name}"}

    t1_wins = t2_wins = draws = total_goals = 0

    for f in fixtures[:10]:
        home_id = f["teams"]["home"]["id"]
        home_goals = f["goals"]["home"] or 0
        away_goals = f["goals"]["away"] or 0
        total_goals += home_goals + away_goals
        is_t1_home = home_id == team1_id

        if home_goals > away_goals:
            if is_t1_home:
                t1_wins += 1
            else:
                t2_wins += 1
        elif home_goals < away_goals:
            if is_t1_home:
                t2_wins += 1
            else:
                t1_wins += 1
        else:
            draws += 1

    n = len(fixtures[:10])
    return {
        "partidos_h2h_analizados": n,
        f"victorias_{team1_name}": t1_wins,
        f"victorias_{team2_name}": t2_wins,
        "empates": draws,
        "promedio_goles_por_partido": round(total_goals / n, 2) if n else 0,
        "porcentaje_mas_2_5_goles": round(
            sum(
                1 for f in fixtures[:10]
                if (f["goals"]["home"] or 0) + (f["goals"]["away"] or 0) > 2
            ) / n * 100, 1
        ) if n else 0,
    }


def get_team_stats(api_key: str, team_name: str) -> dict:
    team_data = search_team(api_key, team_name)
    if not team_data:
        return {"error": f"Equipo no encontrado: {team_name}"}

    team_id = team_data["team"]["id"]
    actual_name = team_data["team"]["name"]

    try:
        fixtures = get_recent_fixtures(api_key, team_id, last=10)
        return summarize_team_form(actual_name, team_id, fixtures)
    except Exception as e:
        return {"error": f"Error obteniendo estadísticas de {team_name}: {str(e)}"}


def get_h2h_stats(api_key: str, team1_name: str, team2_name: str) -> dict:
    t1 = search_team(api_key, team1_name)
    t2 = search_team(api_key, team2_name)

    if not t1:
        return {"error": f"Equipo no encontrado: {team1_name}"}
    if not t2:
        return {"error": f"Equipo no encontrado: {team2_name}"}

    t1_id = t1["team"]["id"]
    t2_id = t2["team"]["id"]
    t1_real = t1["team"]["name"]
    t2_real = t2["team"]["name"]

    try:
        h2h = get_h2h(api_key, t1_id, t2_id)
        return summarize_h2h(t1_real, t2_real, t1_id, h2h)
    except Exception as e:
        return {"error": f"Error obteniendo H2H: {str(e)}"}
