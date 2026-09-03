import streamlit as st
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import time

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------
st.set_page_config(page_title="GolAlert PRO LIVE", page_icon="⚽", layout="wide")
st.title("⚽ GolAlert PRO LIVE — Ligas Favoritas")
st.markdown("Partidos de hoy, estadísticas en directo y pronósticos LIVE.")

# ---------------------------------------------------------
# API KEY DESDE SECRETS
# ---------------------------------------------------------
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

if not API_KEY:
    st.error("❌ La API KEY NO se está cargando desde Secrets.")
    st.stop()
else:
    st.success("✅ API KEY cargada correctamente.")

# ---------------------------------------------------------
# LIGAS FAVORITAS
# ---------------------------------------------------------
LIGAS_FAVORITAS = [
    40,   # Championship
    62,   # Ligue 2
    39,   # Premier League
    140,  # LaLiga
    141,  # Segunda División
    135,  # Serie A
    78,   # Bundesliga
    61,   # Ligue 1
    94,   # Primeira Liga
    88,   # Eredivisie
    144   # Jupiler Pro League
]

# ---------------------------------------------------------
# CONVERTIR HORA UTC → ESPAÑA
# ---------------------------------------------------------
def convertir_hora_local(fecha_iso):
    fecha = datetime.fromisoformat(fecha_iso.replace("Z", "+00:00"))
    fecha_local = fecha.astimezone(ZoneInfo("Europe/Madrid"))
    return fecha_local.strftime("%H:%M")

# ---------------------------------------------------------
# PARTIDOS DE HOY
# ---------------------------------------------------------
def obtener_partidos_hoy():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoy}"
    resp = requests.get(url, headers=HEADERS).json()
    return [p for p in resp.get("response", []) if p["league"]["id"] in LIGAS_FAVORITAS]

# ---------------------------------------------------------
# ESTADÍSTICAS LIVE
# ---------------------------------------------------------
def obtener_stats_live(fixture_id):
    url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS).json()
    return resp.get("response", [])

# ---------------------------------------------------------
# EVENTOS LIVE
# ---------------------------------------------------------
def obtener_eventos_live(fixture_id):
    url = f"{BASE_URL}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS).json()
    return resp.get("response", [])

# ---------------------------------------------------------
# PREDICCIONES LIVE
# ---------------------------------------------------------
def prob_gol_live(minuto, tiros_totales, ataques_peligrosos):
    base = minuto * 0.6
    extra = tiros_totales * 4 + ataques_peligrosos * 2
    return round(np.clip(base + extra, 0, 100), 1)

def prob_btts_live(gl, gv, pg):
    if gl > 0 and gv > 0:
        return 92.0
    if gl > 0 or gv > 0:
        return round(pg * 0.65, 1)
    return round(pg * 0.35, 1)

def prob_over25_live(goles, pg):
    if goles >= 3:
        return 97.0
    if goles == 2:
        return round(pg * 0.85, 1)
    return round(pg * 0.45, 1)

# ---------------------------------------------------------
# MOSTRAR PARTIDOS
# ---------------------------------------------------------
st.header("📅 Partidos de HOY — Ligas Favoritas")

partidos_hoy = obtener_partidos_hoy()

if not partidos_hoy:
    st.warning("No hay partidos hoy en tus ligas favoritas.")
else:
    for p in partidos_hoy:
        f = p["fixture"]
        t = p["teams"]
        g = p["goals"]

        fixture_id = f["id"]
        hora_inicio = convertir_hora_local(f["date"])
        estado = f["status"]["short"]
        minuto = f["status"]["elapsed"] or 0

        gl = g["home"] or 0
        gv = g["away"] or 0
        gt = gl + gv

        st.subheader(f"{t['home']['name']} vs {t['away']['name']}")
        st.write(f"🏟 {p['league']['name']}")
        st.write(f"🕒 Hora: **{hora_inicio}**")
        st.write(f"📌 Estado: **{estado}**")

        # ---------------------------------------------------------
        # SI ESTÁ EN DIRECTO → MOSTRAR LIVE
        # ---------------------------------------------------------
        if estado in ["1H", "HT", "2H", "ET"]:
            st.write(f"⏱ Minuto: **{minuto}**")
            st.write(f"⚽ Marcador: **{gl} - {gv}**")

            # Estadísticas LIVE
            stats = obtener_stats_live(fixture_id)
            eventos = obtener_eventos_live(fixture_id)

            # Extraer estadísticas principales
            tiros_totales = 0
            ataques_peligrosos = 0

            for equipo in stats:
                for s in equipo["statistics"]:
                    if s["type"] == "Shots on Goal":
                        tiros_totales += s["value"] or 0
                    if s["type"] == "Dangerous Attacks":
                        ataques_peligrosos += s["value"] or 0

            # Pronósticos LIVE
            pg = prob_gol_live(minuto, tiros_totales, ataques_peligrosos)
            pb = prob_btts_live(gl, gv, pg)
            po = prob_over25_live(gt, pg)

            c1, c2, c3 = st.columns(3)
            c1.metric("Prob. gol LIVE", f"{pg}%")
            c2.metric("BTTS LIVE", f"{pb}%")
            c3.metric("Over 2.5 LIVE", f"{po}%")

            # Eventos LIVE
            st.write("📢 **Eventos en directo:**")
            for ev in eventos:
                st.write(f"- {ev['time']['elapsed']}’ — {ev['team']['name']} — {ev['detail']}")

        st.markdown("---")

# ---------------------------------------------------------
# AUTO-REFRESCO
# ---------------------------------------------------------
st.info("♻️ Actualizando cada 60 segundos…")
time.sleep(60)
st.experimental_rerun()
