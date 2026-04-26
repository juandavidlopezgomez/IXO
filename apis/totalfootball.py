import requests

BASE_URL = "https://totalfootball-api.p.rapidapi.com"


def get_live_matches(rapidapi_key: str) -> dict:
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": "totalfootball-api.p.rapidapi.com",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(
            f"{BASE_URL}/api/match/living/stream",
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"error": f"Error conectando a TotalFootball API: {str(e)}", "partidos_en_vivo": []}

    matches = _parse_live_matches(data)
    return {
        "total_en_vivo": len(matches),
        "partidos_en_vivo": matches,
    }


def _parse_live_matches(data) -> list[dict]:
    if not data:
        return []

    # Handle both list and dict responses
    if isinstance(data, dict):
        items = data.get("data", data.get("matches", data.get("events", [])))
        if isinstance(items, dict):
            items = list(items.values())
    elif isinstance(data, list):
        items = data
    else:
        return []

    matches = []
    for item in items:
        if not isinstance(item, dict):
            continue

        match = _extract_match_info(item)
        if match:
            matches.append(match)

    return matches


def _safe_get(obj: dict, *keys, default=None):
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key, default)
        if obj is None:
            return default
    return obj


def _extract_match_info(item: dict) -> dict | None:
    # Try various field name patterns used by the API
    home = (
        _safe_get(item, "home_team", "name")
        or _safe_get(item, "homeTeam", "name")
        or item.get("home_name")
        or item.get("homeName")
    )
    away = (
        _safe_get(item, "away_team", "name")
        or _safe_get(item, "awayTeam", "name")
        or item.get("away_name")
        or item.get("awayName")
    )

    if not home or not away:
        return None

    score_home = (
        _safe_get(item, "score", "home")
        or _safe_get(item, "goals", "home")
        or item.get("home_score", 0)
        or 0
    )
    score_away = (
        _safe_get(item, "score", "away")
        or _safe_get(item, "goals", "away")
        or item.get("away_score", 0)
        or 0
    )

    minute = (
        item.get("minute")
        or item.get("elapsed")
        or _safe_get(item, "status", "elapsed")
        or "?"
    )

    league = (
        _safe_get(item, "league", "name")
        or item.get("league_name")
        or item.get("competition")
        or "Desconocida"
    )

    return {
        "partido": f"{home} vs {away}",
        "equipo_local": home,
        "equipo_visitante": away,
        "marcador": f"{score_home}-{score_away}",
        "minuto": minute,
        "liga": league,
        "goles_total": int(score_home) + int(score_away),
    }
