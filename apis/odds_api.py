import os
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

BASE_URL = "https://api.the-odds-api.com/v4"

MARKET_NAMES = {
    "h2h": "Resultado final",
    "totals": "Total de goles/puntos",
    "spreads": "Hándicap",
    "outrights": "Ganador torneo",
}

TOP_SPORTS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_germany_bundesliga",
    "soccer_italy_serie_a",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league",
    "soccer_uefa_europa_league",
    "soccer_conmebol_copa_libertadores",
    "basketball_nba",
    "basketball_euroleague",
    "americanfootball_nfl",
    "baseball_mlb",
    "icehockey_nhl",
    "tennis_atp_french_open",
    "tennis_wta_french_open",
]


def _local_tz():
    return ZoneInfo(os.environ.get("LOCAL_TZ", "America/Bogota"))


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _format_match_time(commence_time_iso: str, now_utc: datetime) -> dict:
    event_utc = _parse_iso(commence_time_iso)
    event_local = event_utc.astimezone(_local_tz())
    now_local = now_utc.astimezone(_local_tz())

    delta = event_utc - now_utc
    minutes = int(delta.total_seconds() / 60)

    if minutes < 0:
        comienza_en = "EN CURSO o terminado"
    elif minutes < 60:
        comienza_en = f"en {minutes} min"
    elif minutes < 1440:
        h = minutes // 60
        m = minutes % 60
        comienza_en = f"en {h}h {m}min" if m else f"en {h}h"
    else:
        d = minutes // 1440
        comienza_en = f"en {d} día{'s' if d > 1 else ''}"

    if event_local.date() == now_local.date():
        cuando = f"HOY {event_local.strftime('%H:%M')}"
    elif event_local.date() == (now_local + timedelta(days=1)).date():
        cuando = f"MAÑANA {event_local.strftime('%H:%M')}"
    else:
        cuando = event_local.strftime("%a %d %b %H:%M")

    return {
        "fecha_iso": commence_time_iso,
        "hora_local": event_local.strftime("%Y-%m-%d %H:%M %Z"),
        "cuando": cuando,
        "comienza_en": comienza_en,
        "minutos_hasta_inicio": minutes,
    }


def get_sports_list(api_key: str) -> list[dict]:
    resp = requests.get(
        f"{BASE_URL}/sports",
        params={"apiKey": api_key},
        timeout=15,
    )
    resp.raise_for_status()
    return [s for s in resp.json() if s.get("active")]


def _extract_outcomes_in_range(
    event: dict,
    min_odds: float,
    max_odds: float,
    now_utc: datetime,
) -> list[dict]:
    seen = set()
    results = []

    time_info = _format_match_time(event["commence_time"], now_utc)

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

                point = outcome.get("point")
                seleccion = outcome["name"]
                if point is not None:
                    seleccion = f"{seleccion} {point}"

                results.append({
                    "event_id": event["id"],
                    "deporte": event.get("sport_title", event.get("sport_key", "")),
                    "deporte_key": event.get("sport_key", ""),
                    "equipo_local": event["home_team"],
                    "equipo_visitante": event["away_team"],
                    "partido": f"{event['home_team']} vs {event['away_team']}",
                    "cuando": time_info["cuando"],
                    "comienza_en": time_info["comienza_en"],
                    "hora_local": time_info["hora_local"],
                    "minutos_hasta_inicio": time_info["minutos_hasta_inicio"],
                    "casa_apuestas": bookmaker["title"],
                    "mercado": MARKET_NAMES.get(market_key, market_key),
                    "mercado_key": market_key,
                    "seleccion": seleccion,
                    "cuota": price,
                    "prob_implicita": round(1 / price * 100, 1),
                })

    return results


def get_events_in_range(
    api_key: str,
    sport: str = "all",
    min_odds: float = 1.40,
    max_odds: float = 1.70,
    hours_ahead: int = 36,
    only_future: bool = True,
    max_results: int = 60,
) -> dict:
    """Obtiene apuestas en rango de cuotas. SOLO eventos futuros por defecto."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc + timedelta(hours=hours_ahead)

    if sport != "all":
        sports_to_check = [sport]
    else:
        try:
            all_sports = get_sports_list(api_key)
            active_keys = [s["key"] for s in all_sports]
            sports_to_check = [s for s in TOP_SPORTS if s in active_keys]
            extras = [s for s in active_keys if s not in TOP_SPORTS]
            sports_to_check.extend(extras[:8])
        except Exception:
            sports_to_check = TOP_SPORTS

    all_events = []
    errors = []
    deportes_consultados = []

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
            deportes_consultados.append(sport_key)

            for event in resp.json():
                event_time = _parse_iso(event["commence_time"])

                # Filtrar partidos pasados
                if only_future and event_time < now_utc:
                    continue

                # Filtrar partidos muy lejanos
                if event_time > cutoff:
                    continue

                outcomes = _extract_outcomes_in_range(event, min_odds, max_odds, now_utc)
                all_events.extend(outcomes)

        except requests.RequestException as e:
            errors.append(f"{sport_key}: {str(e)[:100]}")

    # Ordenar por hora de inicio (más cercanos primero)
    all_events.sort(key=lambda x: x["minutos_hasta_inicio"])

    return {
        "ahora_utc": now_utc.isoformat(),
        "ahora_local": now_utc.astimezone(_local_tz()).strftime("%Y-%m-%d %H:%M %Z"),
        "ventana_horas": hours_ahead,
        "total_apuestas_encontradas": len(all_events),
        "deportes_con_apuestas": len(set(e["deporte"] for e in all_events)),
        "deportes_consultados": len(deportes_consultados),
        "apuestas": all_events[:max_results],
        "errores": errors if errors else None,
    }


def find_match(
    api_key: str,
    query: str,
    hours_ahead: int = 72,
) -> dict:
    """Busca un partido específico por nombre de equipo."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc + timedelta(hours=hours_ahead)
    query_lower = query.lower()

    try:
        all_sports = get_sports_list(api_key)
        sports_to_check = [s["key"] for s in all_sports]
    except Exception:
        sports_to_check = TOP_SPORTS

    found = []

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
                event_time = _parse_iso(event["commence_time"])
                if event_time < now_utc or event_time > cutoff:
                    continue

                home = event["home_team"].lower()
                away = event["away_team"].lower()

                if query_lower in home or query_lower in away or query_lower in f"{home} {away}":
                    time_info = _format_match_time(event["commence_time"], now_utc)
                    all_outcomes = []
                    for bm in event.get("bookmakers", [])[:3]:
                        for m in bm.get("markets", []):
                            for o in m.get("outcomes", []):
                                seleccion = o["name"]
                                if o.get("point") is not None:
                                    seleccion = f"{seleccion} {o['point']}"
                                all_outcomes.append({
                                    "casa": bm["title"],
                                    "mercado": MARKET_NAMES.get(m["key"], m["key"]),
                                    "seleccion": seleccion,
                                    "cuota": o["price"],
                                    "prob_implicita": round(1 / o["price"] * 100, 1) if o["price"] else 0,
                                })

                    found.append({
                        "event_id": event["id"],
                        "deporte": event.get("sport_title", sport_key),
                        "equipo_local": event["home_team"],
                        "equipo_visitante": event["away_team"],
                        "partido": f"{event['home_team']} vs {event['away_team']}",
                        "cuando": time_info["cuando"],
                        "comienza_en": time_info["comienza_en"],
                        "todas_las_cuotas": all_outcomes,
                    })
        except requests.RequestException:
            continue

    return {
        "ahora_local": now_utc.astimezone(_local_tz()).strftime("%Y-%m-%d %H:%M %Z"),
        "busqueda": query,
        "encontrados": len(found),
        "partidos": found[:5],
    }
