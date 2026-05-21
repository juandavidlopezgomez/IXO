#!/usr/bin/env python3
"""
IXO — Agente de predicción de apuestas deportivas.

Modos de uso:
  python main.py                                  → mejores apuestas de hoy/mañana
  python main.py "Real Madrid vs Barcelona"       → analiza partido específico
  python main.py --chat                           → modo interactivo
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from rich.console import Console

console = Console()
load_dotenv()


def _check_env():
    required = ["GROQ_API_KEY", "API_SPORTS_KEY", "RAPIDAPI_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        console.print(
            f"[bold red]Faltan variables de entorno:[/bold red] {', '.join(missing)}\n"
            "Edita el archivo .env y añade los valores que faltan."
        )
        sys.exit(1)


def _run_chat_mode():
    """Modo interactivo: el usuario puede preguntar varios partidos."""
    from display import show_header, show_predictions, show_match_analysis, show_error
    import agent

    show_header()
    console.print("[bold cyan]Modo interactivo activado.[/bold cyan]")
    console.print("[dim]Escribe el nombre de un partido o equipo para analizarlo.[/dim]")
    console.print("[dim]Escribe 'todas' para ver las mejores apuestas del día.[/dim]")
    console.print("[dim]Escribe 'salir' para terminar.[/dim]\n")

    while True:
        try:
            query = console.input("[bold green]›[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Hasta pronto.[/yellow]")
            break

        if not query:
            continue
        if query.lower() in ("salir", "exit", "quit"):
            console.print("[yellow]Hasta pronto.[/yellow]")
            break

        try:
            if query.lower() in ("todas", "todos", "todo", "hoy", "all"):
                console.print("[dim]⏳ Analizando todas las apuestas del día…[/dim]\n")
                result = agent.run_general()
                show_predictions(result)
            else:
                console.print(f"[dim]⏳ Analizando: {query}…[/dim]\n")
                result = agent.run_match(query)
                show_match_analysis(result)
        except KeyboardInterrupt:
            console.print("\n[yellow]Análisis cancelado.[/yellow]")
        except Exception as e:
            show_error(str(e))

        console.print()


def _run_match_mode(query: str):
    from display import show_header, show_match_analysis, show_error, show_spinner_message
    import agent

    show_header()
    show_spinner_message(f"Analizando partido: {query}…")
    console.print()

    try:
        result = agent.run_match(query)
        show_match_analysis(result)
    except Exception as e:
        show_error(str(e))
        sys.exit(1)


def _run_general_mode(top: int = 10):
    from display import show_header, show_predictions, show_error, show_spinner_message
    import agent

    show_header()
    show_spinner_message(
        f"Buscando top {top} apuestas con cuotas 1.40-1.70 en múltiples deportes…\n"
        "  [dim]Datos: The Rundown API (RapidAPI)  |  IA activada solo en análisis de partido específico[/dim]"
    )
    console.print()

    try:
        result = agent.run_general(n=top)
        show_predictions(result)
    except Exception as e:
        show_error(str(e))
        sys.exit(1)


def _run_diagnose():
    """Diagnostica el estado de las APIs."""
    import requests
    from apis.rundown_api import BASE_URL, RAPIDAPI_HOST, get_events_in_range, SPORT_IDS

    rapid_key = os.environ["RAPIDAPI_KEY"]
    console.print("[bold cyan]━━━ DIAGNÓSTICO DE APIs ━━━[/bold cyan]\n")

    # 1. The Rundown API (cuotas)
    console.print("[bold]1. The Rundown API (cuotas — RapidAPI)[/bold]")
    try:
        resp = requests.get(
            f"{BASE_URL}/sports",
            headers={"x-rapidapi-host": RAPIDAPI_HOST, "x-rapidapi-key": rapid_key},
            timeout=15,
        )
        console.print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            sports = resp.json().get("sports", [])
            console.print(f"   Deportes disponibles: {len(sports)}")
            console.print(f"   [green]✅ API funcionando correctamente[/green]")
        elif resp.status_code == 403:
            console.print("   [red]❌ Clave RapidAPI inválida o sin acceso a The Rundown[/red]")
        elif resp.status_code == 429:
            console.print("   [yellow]⚠️ Límite diario de 100 requests alcanzado. Intenta mañana.[/yellow]")
        else:
            console.print(f"   [red]Error {resp.status_code}: {resp.text[:150]}[/red]")
    except Exception as e:
        console.print(f"   [red]Error de conexión: {e}[/red]")

    console.print()

    # 2. Eventos disponibles
    console.print("[bold]2. Eventos disponibles ahora[/bold]")
    for min_o, max_o, hrs in [(1.40, 1.70, 24), (1.35, 1.80, 36), (1.30, 2.00, 72)]:
        data = get_events_in_range(rapid_key, "all", min_o, max_o, hours_ahead=hrs, max_results=500)
        n = data.get("total_apuestas_encontradas", 0)
        deps = data.get("deportes_con_apuestas", 0)
        cons = data.get("deportes_consultados", 0)
        console.print(f"   Cuotas {min_o}-{max_o} en próximas {hrs}h: [cyan]{n} apuestas[/cyan] en {deps} deportes ({cons} consultados)")
        errores = data.get("errores") or []
        if errores:
            console.print(f"      [yellow]Errores: {errores[:2]}[/yellow]")
        if n > 0:
            break

    console.print()


def _run_debug_api():
    """Muestra estructura RAW de la API para diagnóstico."""
    import requests, json
    key = os.environ["RAPIDAPI_KEY"]
    headers = {
        "x-rapidapi-host": "therundown-therundown-v1.p.rapidapi.com",
        "x-rapidapi-key": key,
    }
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    console.print(f"[bold cyan]━━━ DEBUG API RAW (NBA sport_id=3, fecha {today}) ━━━[/bold cyan]\n")
    r = requests.get(
        f"https://therundown-therundown-v1.p.rapidapi.com/sports/3/events/{today}",
        headers=headers,
        params={"include": "all_periods"},
        timeout=15,
    )
    console.print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        events = data.get("events", [])
        console.print(f"Eventos encontrados: {len(events)}")
        if events:
            ev = events[0]
            console.print(f"Claves del evento: {list(ev.keys())}")
            console.print(f"Teams: {ev.get('teams') or ev.get('teams_normalized')}")
            lines = ev.get("lines", {})
            console.print(f"Num bookmakers en lines: {len(lines)}")
            if lines:
                primera = list(lines.values())[0]
                console.print(f"Primera entrada lines:\n{json.dumps(primera, indent=2)[:600]}")
            lp = ev.get("line_periods", {})
            console.print(f"Num bookmakers en line_periods: {len(lp)}")
            if lp:
                primera = list(lp.values())[0]
                console.print(f"Primera entrada line_periods:\n{json.dumps(primera, indent=2)[:800]}")
    else:
        console.print(f"[red]Error: {r.text[:300]}[/red]")


def main():
    parser = argparse.ArgumentParser(
        description="IXO — Agente de predicción de apuestas deportivas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python main.py\n"
            "  python main.py --diagnose\n"
            '  python main.py "Real Madrid vs Barcelona"\n'
            '  python main.py "Lakers"\n'
            "  python main.py --chat"
        ),
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Partido o equipo a analizar (opcional)",
    )
    parser.add_argument(
        "--chat", "-i",
        action="store_true",
        help="Modo interactivo: pregunta sobre varios partidos en una sesión",
    )
    parser.add_argument(
        "--diagnose", "-d",
        action="store_true",
        help="Diagnostica el estado de las APIs (cuota, eventos disponibles)",
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=10,
        help="Número de apuestas a mostrar (por defecto: 10)",
    )
    parser.add_argument(
        "--debug-api",
        action="store_true",
        help="Muestra estructura RAW de la API para diagnóstico",
    )
    args = parser.parse_args()

    _check_env()

    try:
        if args.debug_api:
            _run_debug_api()
        elif args.diagnose:
            _run_diagnose()
        elif args.chat:
            _run_chat_mode()
        elif args.query:
            _run_match_mode(args.query)
        else:
            _run_general_mode(top=args.top)
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado por el usuario.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
