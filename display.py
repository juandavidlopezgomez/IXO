from datetime import datetime
from zoneinfo import ZoneInfo
import os

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()


def _confianza_color(nivel: str) -> str:
    return {"ALTA": "green", "MEDIA": "yellow", "BAJA": "red"}.get(nivel.upper(), "white")


def _recomendar_icon(recomendar: bool) -> str:
    return "[bold green]✅ SÍ[/bold green]" if recomendar else "[bold red]❌ NO[/bold red]"


def _now_local_str() -> str:
    tz = ZoneInfo(os.environ.get("LOCAL_TZ", "America/Bogota"))
    return datetime.now(tz).strftime("%A %d %b %Y — %H:%M %Z")


def show_header():
    console.print(
        Panel.fit(
            "[bold cyan]🏆  IXO — Agente de Predicción de Apuestas[/bold cyan]\n"
            f"[dim]Cuotas objetivo: 1.40–1.70  |  Motor: Llama 3.3 70B (Groq)[/dim]\n"
            f"[dim]Ahora: {_now_local_str()}[/dim]",
            border_style="cyan",
        )
    )
    console.print()


def show_spinner_message(msg: str):
    console.print(f"[dim]⏳ {msg}[/dim]")


def show_error(msg: str):
    console.print(Panel(f"[bold red]Error:[/bold red] {msg}", border_style="red"))


def show_predictions(result: dict):
    """Muestra resultado del análisis general (todas las apuestas del día)."""
    predicciones = result.get("predicciones", [])
    resumen = result.get("resumen", "")

    if not predicciones:
        console.print(
            Panel(
                "[yellow]No se encontraron apuestas que cumplan el criterio "
                "(prob estimada > prob implícita + 5%).[/yellow]\n"
                f"[dim]{resumen}[/dim]",
                title="[bold yellow]Sin recomendaciones[/bold yellow]",
                border_style="yellow",
            )
        )
        if result.get("respuesta_raw"):
            console.print("\n[dim]Respuesta del agente:[/dim]")
            console.print(result["respuesta_raw"][:1000])
        return

    # ── tabla ────────────────────────────────────────────────────────────────
    table = Table(
        title="[bold]Predicciones[/bold]",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold magenta",
    )
    table.add_column("Cuándo", style="cyan", no_wrap=True)
    table.add_column("Deporte", style="dim", max_width=18)
    table.add_column("Partido", max_width=26)
    table.add_column("Selección", style="bold", max_width=18)
    table.add_column("Cuota", justify="center")
    table.add_column("P.Imp.", justify="center")
    table.add_column("P.IA", justify="center")
    table.add_column("Conf.", justify="center")
    table.add_column("OK", justify="center")

    recommended = [p for p in predicciones if p.get("recomendar")]
    not_recommended = [p for p in predicciones if not p.get("recomendar")]

    for p in recommended + not_recommended:
        nivel = p.get("nivel_confianza", "—")
        confianza_str = f"[{_confianza_color(nivel)}]{nivel}[/{_confianza_color(nivel)}]"

        table.add_row(
            p.get("cuando", "—"),
            p.get("deporte", "—"),
            p.get("partido", "—"),
            p.get("seleccion", "—"),
            f"[bold]{p.get('cuota', 0):.2f}[/bold]",
            f"{p.get('prob_implicita', 0):.0f}%",
            f"{p.get('prob_estimada', 0):.0f}%",
            confianza_str,
            _recomendar_icon(p.get("recomendar", False)),
        )

    console.print(table)
    console.print()

    # ── detalle de recomendadas ─────────────────────────────────────────────
    if recommended:
        console.print("[bold green]━━━  APUESTAS RECOMENDADAS  ━━━[/bold green]\n")
        for i, p in enumerate(recommended, 1):
            nivel = p.get("nivel_confianza", "—")
            color = _confianza_color(nivel)
            console.print(
                Panel(
                    f"[bold]{p.get('partido', '—')}[/bold]   [dim]{p.get('cuando', '')}[/dim]\n"
                    f"[dim]Mercado:[/dim] {p.get('mercado', '—')}  |  "
                    f"[dim]Selección:[/dim] [bold]{p.get('seleccion', '—')}[/bold]  |  "
                    f"[dim]Cuota:[/dim] [bold]{p.get('cuota', 0):.2f}[/bold]\n"
                    f"[dim]Prob. implícita:[/dim] {p.get('prob_implicita', 0):.1f}%  →  "
                    f"[dim]Prob. estimada IA:[/dim] [{color}]{p.get('prob_estimada', 0):.1f}%[/{color}]\n\n"
                    f"[italic]{p.get('razonamiento', '—')}[/italic]",
                    title=f"[bold green]#{i}  {p.get('deporte', '')}[/bold green]",
                    border_style="green",
                )
            )

    # ── resumen ──────────────────────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold]{resumen or f'{len(recommended)} recomendadas de {len(predicciones)} analizadas'}[/bold]",
            title="[bold]Resumen[/bold]",
            border_style="blue",
        )
    )


def show_match_analysis(result: dict):
    """Muestra el análisis de un partido específico."""
    if result.get("error"):
        console.print(
            Panel(
                f"[red]{result['error']}[/red]",
                title="[bold red]Error[/bold red]",
                border_style="red",
            )
        )
        if result.get("respuesta_raw"):
            console.print("\n[dim]Respuesta del agente:[/dim]")
            console.print(result["respuesta_raw"][:1000])
        return

    partido = result.get("partido_analizado", "—")
    cuando = result.get("cuando", "—")
    deporte = result.get("deporte", "—")
    analisis = result.get("analisis_general", "—")
    mejor = result.get("mejor_prediccion") or {}
    alternativas = result.get("alternativas") or []

    # ── header del partido ──────────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold cyan]{partido}[/bold cyan]\n"
            f"[dim]{deporte}  |  {cuando}[/dim]\n\n"
            f"[italic]{analisis}[/italic]",
            title="[bold]Análisis del partido[/bold]",
            border_style="cyan",
        )
    )
    console.print()

    # ── mejor predicción ─────────────────────────────────────────────────────
    if mejor:
        nivel = mejor.get("nivel_confianza", "—")
        color = _confianza_color(nivel)
        recomendar = mejor.get("recomendar", False)
        border = "green" if recomendar else "red"
        title_color = "green" if recomendar else "red"

        console.print(
            Panel(
                f"[bold]Mercado:[/bold] {mejor.get('mercado', '—')}\n"
                f"[bold]Selección:[/bold] [bold cyan]{mejor.get('seleccion', '—')}[/bold cyan]\n"
                f"[bold]Cuota:[/bold] [bold]{mejor.get('cuota', 0):.2f}[/bold]\n"
                f"[bold]Probabilidad implícita:[/bold] {mejor.get('prob_implicita', 0):.1f}%\n"
                f"[bold]Probabilidad estimada IA:[/bold] [{color}]{mejor.get('prob_estimada', 0):.1f}%[/{color}]\n"
                f"[bold]Confianza:[/bold] [{color}]{nivel}[/{color}]\n"
                f"[bold]¿Recomendar?:[/bold] {_recomendar_icon(recomendar)}\n\n"
                f"[italic]{mejor.get('razonamiento', '—')}[/italic]",
                title=f"[bold {title_color}]🎯 Mejor predicción[/bold {title_color}]",
                border_style=border,
            )
        )
        console.print()

    # ── alternativas ─────────────────────────────────────────────────────────
    if alternativas:
        console.print("[bold yellow]━━━  Alternativas a considerar  ━━━[/bold yellow]\n")
        for i, alt in enumerate(alternativas, 1):
            console.print(
                Panel(
                    f"[bold]{alt.get('mercado', '—')}[/bold]  |  "
                    f"Cuota: [bold]{alt.get('cuota', 0):.2f}[/bold]  |  "
                    f"Prob. estimada: [yellow]{alt.get('prob_estimada', 0):.1f}%[/yellow]\n"
                    f"[italic dim]{alt.get('razonamiento', '—')}[/italic dim]",
                    title=f"[yellow]Alternativa #{i}[/yellow]",
                    border_style="yellow",
                )
            )
