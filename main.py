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


def main():
    parser = argparse.ArgumentParser(
        description="IXO — Agente de predicción de apuestas deportivas",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python main.py\n"
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
    args = parser.parse_args()

    _check_env()

    try:
        if args.chat:
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
