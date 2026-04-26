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
    required = ["GROQ_API_KEY", "ODDS_API_KEY", "API_SPORTS_KEY", "RAPIDAPI_KEY"]
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


def _run_general_mode():
    from display import show_header, show_predictions, show_error, show_spinner_message
    import agent

    show_header()
    show_spinner_message(
        "Analizando apuestas con cuotas 1.40-1.70 en próximas 36 horas…"
    )
    console.print()

    try:
        result = agent.run_general()
        show_predictions(result)
    except Exception as e:
        show_error(str(e))
        sys.exit(1)


def _run_diagnose():
    """Diagnostica el estado de las APIs."""
    import requests
    from apis.odds_api import BASE_URL, get_sports_list, get_events_in_range

    odds_key = os.environ["ODDS_API_KEY"]
    console.print("[bold cyan]━━━ DIAGNÓSTICO DE APIs ━━━[/bold cyan]\n")

    # 1. The Odds API
    console.print("[bold]1. The Odds API[/bold]")
    try:
        resp = requests.get(f"{BASE_URL}/sports", params={"apiKey": odds_key}, timeout=15)
        console.print(f"   Status: {resp.status_code}")
        console.print(f"   Quota usada: {resp.headers.get('x-requests-used', '?')}")
        console.print(f"   Quota restante: {resp.headers.get('x-requests-remaining', '?')}")
        if resp.status_code == 200:
            sports = [s for s in resp.json() if s.get("active")]
            console.print(f"   Deportes activos: {len(sports)}")
            console.print(f"   [green]✅ API funcionando correctamente[/green]")
        elif resp.status_code == 403 and "allowlist" in resp.text.lower():
            console.print(
                "\n   [bold red]❌ PROBLEMA: Clave API bloqueada por host[/bold red]\n"
                "   El servidor de GitHub Codespaces no está autorizado en esta clave.\n\n"
                "   [bold yellow]SOLUCIÓN — sigue estos pasos:[/bold yellow]\n"
                "   1. Ve a [cyan]https://the-odds-api.com[/cyan] en tu navegador\n"
                "   2. Crea una cuenta gratis (no necesitas tarjeta)\n"
                "   3. Copia tu nueva API Key\n"
                "   4. En la terminal del Codespace escribe:\n"
                "      [bold]sed -i 's/ODDS_API_KEY=.*/ODDS_API_KEY=TU_NUEVA_CLAVE/' .env[/bold]\n"
                "   5. Vuelve a correr: [bold]python main.py[/bold]"
            )
        elif resp.status_code == 401:
            console.print(
                "\n   [bold red]❌ PROBLEMA: Clave API inválida o expirada[/bold red]\n"
                "   Obtén una nueva clave gratis en [cyan]https://the-odds-api.com[/cyan]"
            )
        else:
            console.print(f"   [red]Respuesta inesperada ({resp.status_code}): {resp.text[:200]}[/red]")
    except Exception as e:
        console.print(f"   [red]Error de conexión: {e}[/red]")

    console.print()

    # 2. Probar fetch de eventos en distintos rangos
    console.print("[bold]2. Eventos disponibles ahora[/bold]")
    for min_o, max_o, hrs in [(1.40, 1.70, 24), (1.30, 2.00, 48), (1.0, 100.0, 72)]:
        data = get_events_in_range(odds_key, "all", min_o, max_o, hours_ahead=hrs, max_results=500)
        n = data.get("total_apuestas_encontradas", 0)
        deps = data.get("deportes_con_apuestas", 0)
        console.print(f"   Cuotas {min_o}-{max_o} en próximas {hrs}h: [cyan]{n} apuestas[/cyan] en {deps} deportes")
        errores = data.get("errores") or []
        if errores and "403" in str(errores[0]):
            console.print("      [red]→ Error 403: clave bloqueada (ver punto 1)[/red]")
            break
        elif errores:
            console.print(f"      [yellow]Errores: {errores[:2]}[/yellow]")

    console.print()


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
    args = parser.parse_args()

    _check_env()

    try:
        if args.diagnose:
            _run_diagnose()
        elif args.chat:
            _run_chat_mode()
        elif args.query:
            _run_match_mode(args.query)
        else:
            _run_general_mode()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelado por el usuario.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
