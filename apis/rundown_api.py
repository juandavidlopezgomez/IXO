"""
The Rundown API (RapidAPI) — reemplaza The Odds API.
100 requests/día gratis. Cubre: Fútbol, NBA, NFL, MLB, NHL, UFC, MLS.
"""
import os
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

RAPIDAPI_HOST = "therundown-therundown-v1.p.rapidapi.com"
BASE_URL = f"https://{RAPIDAPI_HOST}"

# IDs de deportes conocidos
SPORT_IDS = {
    1:  "NFL",
    2:  "MLB",
    3:  "NBA",
    4:  "NCAAF",
    5:  "NCAAB",
    6:  "NHL",
    8:  "UFC/MMA",
    12: "Fútbol",
}

# Cache de sesión para no repetir llamadas
_sports_cache: list | None = None


def _headers(api_key: str) -> dict:
    return {
        "x-rapidapi-host": RAPIDAPI_HOST,
        "x-rapidapi-key": api_key,
    }


def _local_tz():
    return ZoneInfo(os.environ.get("LOCAL_TZ", "America/Bogota"))


def _american_to_decimal(american) -> float:
    """Convierte cuotas americanas a decimales. Retorna 0 si inválido."""
    try:
        a = float(american)
    except (TypeError, ValueError):
        return 0.0
    if a == 0 or abs(a) >= 9999:
        return 0.0
    if a > 0:
        return round(1 + a / 100, 4)
    return round(1 + 100 / abs(a), 4)


def _format_match_time(event_date_str: str, now_utc: datetime) -> dict:
    try:
        event_utc = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
    except Exception:
        return {"cuando": "?", "comienza_en": "?", "minutos_hasta_inicio": 99999}

    event_local = event_utc.astimezone(_local_tz())
    now_local = now_utc.astimezone(_local_tz())
    minutes = int((event_utc - now_utc).total_seconds() / 60)

    if minutes < 0:
        comienza_en = "EN CURSO o terminado"
    elif minutes < 60:
        comienza_en = f"en {minutes} min"
    elif minutes < 1440:
        h, m = divmod(minutes, 60)
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

    return {"cuando": cuando, "comienza_en": comienza_en, "minutos_hasta_inicio": minutes}


def get_sports_list(api_key: str) -> list[dict]:
    global _sports_cache
    if _sports_cache is not None:
        return _sports_cache
    resp = requests.get(f"{BASE_URL}/sports", headers=_headers(api_key), timeout=15)
    resp.raise_for_status()
    _sports_cache = resp.json().get("sports", [])
    return _sports_cache


def _parse_period(period: dict) -> tuple[dict, dict]:
    """Extrae (moneyline, total) de un periodo, manejando ambos formatos de API."""
    ml = period.get("moneyline") or {}
    total = period.get("total") or {}
    # Algunos endpoints usan "totals" en vez de "total"
    if not total:
        total = period.get("totals") or {}
    return ml, total


def _extract_outcomes(event: dict, sport_name: str, min_odds: float, max_odds: float, now_utc: datetime) -> list[dict]:
    """Extrae apuestas de un evento dentro del rango de cuotas.
    The Rundown API puede tener odds en 'lines' o en 'line_periods'.
    """
    teams = event.get("teams_normalized") or event.get("teams", [])
    if not teams or len(teams) < 2:
        return []

    home = next((t.get("name", "") for t in teams if t.get("is_home")), teams[0].get("name", ""))
    away = next((t.get("name", "") for t in teams if not t.get("is_home")), teams[1].get("name", ""))
    if not home or not away:
        return []

    partido = f"{home} vs {away}"
    time_info = _format_match_time(event.get("event_date", ""), now_utc)
    seen: set = set()
    results = []

    def _add_ml(ml: dict, name_home: str, name_away: str):
        for odds_key, seleccion in [
            ("moneyline_home", name_home),
            ("moneyline_away", name_away),
            ("moneyline_draw", "Empate"),
        ]:
            val = ml.get(odds_key)
            dec = _american_to_decimal(val)
            if dec and min_odds <= dec <= max_odds:
                dk = (partido, "Resultado final", seleccion)
                if dk not in seen:
                    seen.add(dk)
                    results.append({
                        "deporte": sport_name, "partido": partido,
                        "cuando": time_info["cuando"], "comienza_en": time_info["comienza_en"],
                        "minutos_hasta_inicio": time_info["minutos_hasta_inicio"],
                        "mercado": "Resultado final", "seleccion": seleccion,
                        "cuota": dec, "prob_implicita": round(1 / dec * 100, 1),
                    })

    def _add_total(total: dict):
        line_val = total.get("total_over") or total.get("total_over_under") or ""
        for odds_key, label in [("total_over_money", "Más de"), ("total_under_money", "Menos de")]:
            val = total.get(odds_key)
            dec = _american_to_decimal(val)
            if dec and min_odds <= dec <= max_odds:
                seleccion = f"{label} {line_val}"
                dk = (partido, "Total", seleccion)
                if dk not in seen:
                    seen.add(dk)
                    results.append({
                        "deporte": sport_name, "partido": partido,
                        "cuando": time_info["cuando"], "comienza_en": time_info["comienza_en"],
                        "minutos_hasta_inicio": time_info["minutos_hasta_inicio"],
                        "mercado": "Total puntos/goles", "seleccion": seleccion,
                        "cuota": dec, "prob_implicita": round(1 / dec * 100, 1),
                    })

    # ── Formato 1: campo "lines" (bookmaker_id → {moneyline, total}) ─────────
    for book_data in event.get("lines", {}).values():
        ml, total = book_data.get("moneyline", {}), book_data.get("total", {})
        _add_ml(ml, home, away)
        _add_total(total)

    # ── Formato 2: campo "line_periods" (bookmaker_id → {period_full_game}) ──
    for book_data in event.get("line_periods", {}).values():
        period = book_data.get("period_full_game") or book_data.get("1") or {}
        if not period:
            # Algunos tienen el periodo directamente como valor
            period = book_data
        ml, total = _parse_period(period)
        _add_ml(ml, home, away)
        _add_total(total)

    return results


def get_events_in_range(
    api_key: str,
    sport: str = "all",
    min_odds: float = 1.40,
    max_odds: float = 1.70,
    hours_ahead: int = 36,
    only_future: bool = True,
    max_results: int = 20,
) -> dict:
    """Obtiene apuestas en rango de cuotas. Interfaz idéntica a odds_api.py."""
    now_utc = datetime.now(timezone.utc)

    # Fechas a consultar
    dates = []
    d = now_utc
    while d <= now_utc + timedelta(hours=hours_ahead):
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    dates = list(dict.fromkeys(dates))  # dedup manteniendo orden

    # Deportes a consultar
    sport_ids = list(SPORT_IDS.keys()) if sport == "all" else []

    all_events: list[dict] = []
    errors: list[str] = []
    consultados: set[int] = set()

    for sport_id in sport_ids:
        sport_name = SPORT_IDS[sport_id]
        for date_str in dates:
            try:
                resp = requests.get(
                    f"{BASE_URL}/sports/{sport_id}/events/{date_str}",
                    headers=_headers(api_key),
                    params={"include": "all_periods"},
                    timeout=15,
                )
                if resp.status_code == 404:
                    continue
                if resp.status_code == 429:
                    errors.append(f"{sport_name}: límite de requests alcanzado (429)")
                    break
                resp.raise_for_status()

                events = resp.json().get("events", [])
                consultados.add(sport_id)

                for ev in events:
                    ti = _format_match_time(ev.get("event_date", ""), now_utc)
                    if only_future and ti["minutos_hasta_inicio"] < 0:
                        continue
                    if ti["minutos_hasta_inicio"] > hours_ahead * 60:
                        continue
                    outcomes = _extract_outcomes(ev, sport_name, min_odds, max_odds, now_utc)
                    all_events.extend(outcomes)

            except requests.RequestException as e:
                errors.append(f"{sport_name}: {str(e)[:80]}")

    all_events.sort(key=lambda x: x["minutos_hasta_inicio"])

    return {
        "ahora_utc": now_utc.isoformat(),
        "ahora_local": now_utc.astimezone(_local_tz()).strftime("%Y-%m-%d %H:%M %Z"),
        "ventana_horas": hours_ahead,
        "total_apuestas_encontradas": len(all_events),
        "deportes_con_apuestas": len(set(e["deporte"] for e in all_events)),
        "deportes_consultados": len(consultados),
        "apuestas": all_events[:max_results],
        "errores": errors if errors else None,
    }


TEAM_ALIASES = {
    "psg": ["paris saint-germain", "paris saint germain"],
    "bayern": ["bayern munich", "fc bayern", "bayern münchen"],
    "barca": ["barcelona", "fc barcelona"],
    "barça": ["barcelona", "fc barcelona"],
    "real": ["real madrid"],
    "atletico": ["atletico madrid", "atlético madrid"],
    "city": ["manchester city"],
    "united": ["manchester united"],
    "inter": ["inter milan", "internazionale"],
    "milan": ["ac milan"],
    "dortmund": ["borussia dortmund"],
    "juve": ["juventus"],
    "lakers": ["los angeles lakers"],
    "warriors": ["golden state warriors"],
    "celtics": ["boston celtics"],
    "heat": ["miami heat"],
}


def _expand_query(query: str) -> list[str]:
    q = query.lower().strip()
    variants = {q}
    for token in q.replace(" vs ", " ").replace("-", " ").split():
        variants.update(TEAM_ALIASES.get(token, []))
    variants.update(TEAM_ALIASES.get(q, []))
    if " vs " in q:
        for p in q.split(" vs "):
            p = p.strip()
            variants.add(p)
            variants.update(TEAM_ALIASES.get(p, []))
    return list(variants)


def find_match(api_key: str, query: str, hours_ahead: int = 72) -> dict:
    """Busca un partido específico por nombre de equipo."""
    now_utc = datetime.now(timezone.utc)
    variants = _expand_query(query)

    dates = []
    d = now_utc
    while d <= now_utc + timedelta(hours=hours_ahead):
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    dates = list(dict.fromkeys(dates))

    found = []

    for sport_id, sport_name in SPORT_IDS.items():
        for date_str in dates:
            try:
                resp = requests.get(
                    f"{BASE_URL}/sports/{sport_id}/events/{date_str}",
                    headers=_headers(api_key),
                    params={"include": "all_periods"},
                    timeout=15,
                )
                if resp.status_code in (404, 429):
                    continue
                resp.raise_for_status()

                for ev in resp.json().get("events", []):
                    ti = _format_match_time(ev.get("event_date", ""), now_utc)
                    if ti["minutos_hasta_inicio"] < -60:
                        continue

                    teams = ev.get("teams_normalized") or ev.get("teams", [])
                    if len(teams) < 2:
                        continue
                    home = next((t.get("name", "") for t in teams if t.get("is_home")), teams[0].get("name", ""))
                    away = next((t.get("name", "") for t in teams if not t.get("is_home")), teams[1].get("name", ""))
                    full = f"{home.lower()} {away.lower()}"

                    if not any(v in home.lower() or v in away.lower() or v in full for v in variants):
                        continue

                    # Recopilar todas las cuotas del partido
                    all_odds = []
                    for book_data in ev.get("lines", {}).values():
                        book = book_data.get("affiliate", {}).get("affiliate_name", "Casa")
                        ml = book_data.get("moneyline", {})
                        total = book_data.get("total", {})

                        for odds_key, sel in [("moneyline_home", home), ("moneyline_away", away), ("moneyline_draw", "Empate")]:
                            dec = _american_to_decimal(ml.get(odds_key))
                            if dec:
                                all_odds.append({"casa": book, "mercado": "Resultado final", "seleccion": sel, "cuota": dec, "prob_implicita": round(100 / dec, 1)})

                        line_val = total.get("total_over", "")
                        for ok, lbl in [("total_over_money", f"Más de {line_val}"), ("total_under_money", f"Menos de {line_val}")]:
                            dec = _american_to_decimal(total.get(ok))
                            if dec:
                                all_odds.append({"casa": book, "mercado": "Total", "seleccion": lbl, "cuota": dec, "prob_implicita": round(100 / dec, 1)})

                    found.append({
                        "deporte": sport_name,
                        "partido": f"{home} vs {away}",
                        "equipo_local": home,
                        "equipo_visitante": away,
                        "cuando": ti["cuando"],
                        "comienza_en": ti["comienza_en"],
                        "todas_las_cuotas": all_odds,
                    })

            except requests.RequestException:
                continue

    return {
        "ahora_local": now_utc.astimezone(_local_tz()).strftime("%Y-%m-%d %H:%M %Z"),
        "busqueda": query,
        "encontrados": len(found),
        "partidos": found[:5],
    }
