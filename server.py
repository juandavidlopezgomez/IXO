#!/usr/bin/env python3
"""
IXO — Servidor web para acceder desde el navegador del celular.
Uso: python server.py
Luego abre el puerto 5000 en GitHub Codespaces.
"""
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template_string

load_dotenv()
import agent

app = Flask(__name__)

_cache: dict = {"data": None, "ts": None}


def _get_bets(force: bool = False) -> dict:
    """Retorna apuestas desde cache (5 min) o llama la API."""
    now = datetime.now()
    if not force and _cache["data"] and _cache["ts"]:
        diff = (now - _cache["ts"]).total_seconds()
        if diff < 300:  # 5 minutos de cache
            return _cache["data"]
    try:
        result = agent.run_general(n=10)
    except Exception as e:
        result = {"predicciones": [], "resumen": f"Error: {e}", "ahora_local": ""}
    _cache["data"] = result
    _cache["ts"] = now
    return result


HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IXO — Apuestas</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f0f17; color: #e0e0e0; min-height: 100vh; }
  header { background: linear-gradient(135deg, #1a1a2e, #16213e);
           padding: 16px 20px; border-bottom: 2px solid #00b4d8;
           display: flex; justify-content: space-between; align-items: center; }
  header h1 { font-size: 1.3rem; color: #00b4d8; font-weight: 700; }
  header .hora { font-size: 0.75rem; color: #888; }
  .container { padding: 16px; max-width: 600px; margin: 0 auto; }
  .btn-refresh { background: #00b4d8; color: #000; border: none; padding: 8px 18px;
                 border-radius: 20px; font-weight: 700; cursor: pointer;
                 font-size: 0.85rem; text-decoration: none; display: inline-block; }
  .btn-refresh:active { opacity: 0.7; }
  .summary { background: #1a1a2e; border-radius: 12px; padding: 12px 16px;
             margin-bottom: 16px; font-size: 0.8rem; color: #aaa;
             border-left: 3px solid #00b4d8; }
  .card { background: #1e1e2e; border-radius: 14px; padding: 16px;
          margin-bottom: 12px; border: 1px solid #2a2a3e; }
  .card.green { border-left: 4px solid #4ade80; }
  .card.yellow { border-left: 4px solid #facc15; }
  .card.red { border-left: 4px solid #f87171; }
  .card-header { display: flex; justify-content: space-between; align-items: flex-start;
                 margin-bottom: 10px; gap: 8px; }
  .partido { font-size: 0.95rem; font-weight: 700; color: #fff; flex: 1; }
  .cuando { font-size: 0.72rem; color: #00b4d8; white-space: nowrap;
            background: #0d2137; padding: 3px 8px; border-radius: 10px; }
  .deporte { font-size: 0.7rem; color: #888; margin-bottom: 6px; }
  .seleccion { font-size: 1rem; color: #4ade80; font-weight: 700; margin: 4px 0; }
  .card.yellow .seleccion { color: #facc15; }
  .card.red .seleccion { color: #f87171; }
  .meta { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 8px; }
  .badge { background: #2a2a3e; padding: 4px 10px; border-radius: 8px;
           font-size: 0.75rem; }
  .badge span { color: #aaa; }
  .badge b { color: #fff; }
  .mercado { font-size: 0.75rem; color: #888; margin-top: 6px; }
  .ok { font-size: 0.8rem; font-weight: 700; margin-top: 10px; }
  .ok.si { color: #4ade80; }
  .ok.no { color: #f87171; }
  .empty { text-align: center; padding: 40px 20px; color: #666; }
  .empty h2 { color: #aaa; margin-bottom: 12px; }
  .loading { text-align: center; padding: 40px; color: #00b4d8; font-size: 1.1rem; }
  .razon { font-size: 0.72rem; color: #777; margin-top: 8px; line-height: 1.4; }
</style>
</head>
<body>
<header>
  <div>
    <h1>🏆 IXO Apuestas</h1>
    <div class="hora" id="hora">{{ hora }}</div>
  </div>
  <a href="/refresh" class="btn-refresh">⟳ Actualizar</a>
</header>

<div class="container">
  {% if not predicciones %}
    <div class="empty">
      <h2>Sin recomendaciones</h2>
      <p style="font-size:0.85rem; margin-bottom:16px;">{{ resumen }}</p>
      <a href="/refresh" class="btn-refresh">Reintentar</a>
    </div>
  {% else %}
    <div class="summary">{{ resumen }}</div>
    {% for p in predicciones %}
      {% if p.nivel_confianza == 'ALTA' %}{% set cls = 'green' %}
      {% elif p.nivel_confianza == 'MEDIA' %}{% set cls = 'yellow' %}
      {% else %}{% set cls = 'red' %}{% endif %}
      <div class="card {{ cls }}">
        <div class="card-header">
          <div class="partido">{{ p.partido }}</div>
          <div class="cuando">{{ p.cuando }}</div>
        </div>
        <div class="deporte">{{ p.deporte }} &nbsp;·&nbsp; {{ p.mercado }}</div>
        <div class="seleccion">{{ p.seleccion }}</div>
        <div class="meta">
          <div class="badge"><span>Cuota </span><b>{{ "%.2f"|format(p.cuota) }}</b></div>
          <div class="badge"><span>P.Impl. </span><b>{{ "%.0f"|format(p.prob_implicita) }}%</b></div>
          <div class="badge"><span>P.Est. </span><b>{{ "%.0f"|format(p.prob_estimada) }}%</b></div>
        </div>
        <div class="mercado">{{ p.comienza_en }}</div>
        <div class="ok {{ 'si' if p.recomendar else 'no' }}">
          {{ '✅ APOSTAR' if p.recomendar else '❌ No apostar' }}
        </div>
        {% if p.razonamiento %}
          <div class="razon">{{ p.razonamiento }}</div>
        {% endif %}
      </div>
    {% endfor %}
  {% endif %}
</div>

<script>
  function updateHora() {
    const el = document.getElementById('hora');
    if (el) el.textContent = new Date().toLocaleString('es-CO', {timeZone:'America/Bogota',
      weekday:'short', day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit'});
  }
  updateHora();
  setInterval(updateHora, 60000);
  // Auto-refresh cada 10 minutos
  setTimeout(() => location.reload(), 600000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    result = _get_bets()
    tz = ZoneInfo(os.environ.get("LOCAL_TZ", "America/Bogota"))
    hora = datetime.now(tz).strftime("%A %d %b — %H:%M")
    return render_template_string(
        HTML,
        predicciones=result.get("predicciones", []),
        resumen=result.get("resumen", ""),
        hora=hora,
    )


@app.route("/refresh")
def refresh():
    _get_bets(force=True)
    from flask import redirect
    return redirect("/")


@app.route("/api/bets")
def api_bets():
    result = _get_bets()
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🏆 IXO servidor iniciado en http://localhost:{port}")
    print("   En Codespaces: abre el puerto 5000 desde la pestaña 'Ports'\n")
    app.run(host="0.0.0.0", port=port, debug=False)
