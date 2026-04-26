import requests
from datetime import datetime, timezone

BASE_URL = "https://api.the-odds-api.com/v4"

MARKET_NAMES = {
    "h2h": "Resultado final",
    "totals": "Total de goles/puntos",
    "spreads": "Hándicap",
    "h2h_lay": "Lay resultado",
    "outrights": "Ganador torneo",
}

TOP_SPORTS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league",
    "basketball_nba",
    "basketball_euroleague",
    "tennis_atp_french_open",
    "americanfootball_nfl",
    "baseball_mlb",
    "icehockey_nhl",
]


def get_sports_list(api_key: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/sports",
        params={"apiKey": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    return [s for s in resp.json() if s.get("active")]


def _extract_outcomes_in_range(
    event: dict, min_odds: float, max_odds: float
) -> list[dict]:
    seen = set()
    results = []

    for bookmaker in event.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            market_key = market.get("key", "")
            for outcome in market.get("outcomes", []):
                price = outcome.get("price", 0)
                if not (min_odds <= price <= max_odds):
                    continue

                dedup_key = (event["id"], market_key, outcome["name"])
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                implied_prob = round(1 / price * 100, 1)
                results.append({
                    "event_id": event["id"],
                    "deporte": event.get("sport_title", event.get("sport_key", "")),
                    "deporte_key": event.get("sport_key", ""),
                    "equipo_local": event["home_team"],
                    "equipo_visitante": event["away_team"],
                    "fecha": event["commence_time"],
                    "casa_apuestas": bookmaker["title"],
                    "mercado": MARKET_NAMES.get(market_key, market_key),
                    "mercado_key": market_key,
                    "seleccion": outcome["name"],
                    "cuota": price,
                    "prob_implicita": implied_prob,
                })

    return results


def get_events_in_range(
    api_key: str,
    sport: str = "all",
    min_odds: float = 1.40,
    max_odds: float = 1.70,
) -> dict:
    if sport != "all":
        sports_to_check = [sport]
    else:
        try:
            all_sports = get_sports_list(api_key)
            active_keys = [s["key"] for s in all_sports]
            # Prioritize top sports, then add the rest
            sports_to_check = [s for s in TOP_SPORTS if s in active_keys]
            remaining = [s for s in active_keys if s not in TOP_SPORTS]
            sports_to_check.extend(remaining[:10])  # limit extra sports
        except Exception:
            sports_to_check = TOP_SPORTS

    all_events = []
    errors = []

    for sport_key in sports_to_check:
        try:
            resp = requests.get(
                f"{BASE_URL}/sports/{sport_key}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "eu,uk",
                    "markets": "h2h,totals",
                    "oddsFormat": "decimal",
                    "dateFormat": "iso",
                },
                timeout=15,
            )
            if resp.status_code in (404, 422):
                continue
            resp.raise_for_status()

            for event in resp.json():
                outcomes = _extract_outcomes_in_range(event, min_odds, max_odds)
                all_events.extend(outcomes)

        except requests.RequestException as e:
            errors.append(f"{sport_key}: {str(e)}")

    return {
        "total_apuestas_encontradas": len(all_events),
        "deportes_consultados": len(sports_to_check),
        "apuestas": all_events[:50],  # limit to 50 to avoid overloading context
        "errores": errors if errors else None,
    }
