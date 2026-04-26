from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


def _confianza_color(nivel: str) -> str:
    return {"ALTA": "green", "MEDIA": "yellow", "BAJA": "red"}.get(nivel.upper(), "white")


def _recomendar_icon(recomendar: bool) -> str:
    return "[bold green]✅ SÍ[/bold green]" if recomendar else "[bold red]❌ NO[/bold red]"


def show_header():
    console.print(
        Panel.fit(
            "[bold cyan]🏆  IXO — Agente de Predicción de Apuestas[/bold cyan]\n"
            "[dim]Cuotas objetivo: 1.40 – 1.70  |  Motor: Claude claude-sonnet-4-6[/dim]",
            border_style="cyan",
        )
    )
    console.print()


def show_predictions(result: dict):
    predicciones = result.get("predicciones", [])
    resumen = result.get("resumen", "")

    if not predicciones:
        console.print(
            Panel(
                "[yellow]No se encontraron apuestas recomendables en este momento.\n"
                "Prueba más tarde o amplía el rango de cuotas.[/yellow]",
                title="[bold yellow]Sin predicciones[/bold yellow]",
                border_style="yellow",
            )
        )
        if result.get("respuesta_raw"):
            console.print("\n[dim]Respuesta del agente:[/dim]")
            console.print(result["respuesta_raw"])
        return

    # ── tabla de todas las predicciones ──────────────────────────────────────
    table = Table(
        title="[bold]Predicciones del día[/bold]",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold magenta",
    )
    table.add_column("Deporte / Liga", style="cyan", no_wrap=True, max_width=22)
    table.add_column("Partido", max_width=28)
    table.add_column("Selección", style="bold", max_width=18)
    table.add_column("Cuota", justify="center")
    table.add_column("Prob.\nImplícita", justify="center")
    table.add_column("Confianza\nIA", justify="center")
    table.add_column("Recomendar", justify="center")

    recommended = [p for p in predicciones if p.get("recomendar")]
    not_recommended = [p for p in predicciones if not p.get("recomendar")]

    for p in recommended + not_recommended:
        nivel = p.get("nivel_confianza", "—")
        recomendar = p.get("recomendar", False)
        cuota = p.get("cuota", 0)
        prob_imp = p.get("prob_implicita", 0)
        prob_est = p.get("prob_estimada", 0)

        cuota_str = f"[bold]{cuota:.2f}[/bold]"
        prob_imp_str = f"{prob_imp:.1f}%"
        confianza_str = (
            f"[{_confianza_color(nivel)}]{nivel}[/{_confianza_color(nivel)}]\n"
            f"[dim]{prob_est:.1f}%[/dim]"
        )

        table.add_row(
            p.get("deporte", "—"),
            p.get("partido", "—"),
            p.get("seleccion", "—"),
            cuota_str,
            prob_imp_str,
            confianza_str,
            _recomendar_icon(recomendar),
        )

    console.print(table)
    console.print()

    # ── panel de detalle para apuestas recomendadas ───────────────────────────
    if recommended:
        console.print("[bold green]━━━  APUESTAS RECOMENDADAS  ━━━[/bold green]\n")
        for i, p in enumerate(recommended, 1):
            nivel = p.get("nivel_confianza", "—")
            color = _confianza_color(nivel)
            razon = p.get("razonamiento", "Sin detalles")

            console.print(
                Panel(
                    f"[bold]{p.get('partido')}[/bold]\n"
                    f"[dim]Mercado:[/dim] {p.get('mercado', '—')}  |  "
                    f"[dim]Selección:[/dim] [bold]{p.get('seleccion')}[/bold]  |  "
                    f"[dim]Cuota:[/dim] [bold]{p.get('cuota', 0):.2f}[/bold]\n"
                    f"[dim]Prob. implícita:[/dim] {p.get('prob_implicita', 0):.1f}%  →  "
                    f"[dim]Prob. estimada IA:[/dim] [{color}]{p.get('prob_estimada', 0):.1f}%[/{color}]\n\n"
                    f"[italic]{razon}[/italic]",
                    title=f"[bold green]#{i}  {p.get('deporte', '')}[/bold green]",
                    border_style="green",
                )
            )

    # ── resumen final ─────────────────────────────────────────────────────────
    console.print(
        Panel(
            f"[bold]{resumen or f'{len(recommended)} recomendadas de {len(predicciones)} analizadas'}[/bold]",
            title="[bold]Resumen[/bold]",
            border_style="blue",
        )
    )


def show_error(msg: str):
    console.print(
        Panel(f"[bold red]Error:[/bold red] {msg}", border_style="red")
    )


def show_spinner_message(msg: str):
    console.print(f"[dim]⏳ {msg}[/dim]")
