#!/usr/bin/env python3
"""
IXO — Agente de predicción de apuestas deportivas.
Ejecutar: python main.py
"""
import argparse
import os
import sys

from dotenv import load_dotenv
from rich.console import Console

console = Console()

load_dotenv()


def _check_env():
    required = ["ANTHROPIC_API_KEY", "ODDS_API_KEY", "API_SPORTS_KEY", "RAPIDAPI_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        console.print(
            f"[bold red]Faltan variables de entorno:[/bold red] {', '.join(missing)}\n"
            "Copia .env.example → .env y rellena los valores."
        )
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="IXO — Agente de predicción de apuestas deportivas"
    )
    parser.add_argument(
        "--sport",
        default="all",
        help="Deporte a analizar (default: all). Ej: soccer_epl, basketball_nba",
    )
    parser.add_argument(
        "--min-odds",
        type=float,
        default=1.40,
        help="Cuota mínima (default: 1.40)",
    )
    parser.add_argument(
        "--max-odds",
        type=float,
        default=1.70,
        help="Cuota máxima (default: 1.70)",
    )
    args = parser.parse_args()

    _check_env()

    from display import show_header, show_predictions, show_error, show_spinner_message
    import agent

    show_header()
    show_spinner_message(
        f"Analizando apuestas con cuotas {args.min_odds:.2f}–{args.max_odds:.2f} "
        f"en {'todos los deportes' if args.sport == 'all' else args.sport}…"
    )
    console.print()

    try:
        result = agent.run()
        show_predictions(result)
    except KeyboardInterrupt:
        console.print("\n[yellow]Análisis cancelado por el usuario.[/yellow]")
        sys.exit(0)
    except Exception as e:
        show_error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
