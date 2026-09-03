import streamlit as st
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------
st.set_page_config(page_title="GolAlert PRO", page_icon="⚽", layout="wide")
st.title("⚽ GolAlert PRO — Ligas Favoritas (HOY + Directos)")
st.markdown("Partidos de hoy, hora de inicio y predicciones en directo.")

# ---------------------------------------------------------
# API KEY DESDE SECRETS
# ---------------------------------------------------------
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

if not API_KEY:
    st.error("❌ La API KEY NO se está cargando desde Secrets.")
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
# PARTIDOS DE HOY (TODOS)
# ---------------------------------------------------------
def obtener_partidos_hoy():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoy}"
    resp = requests.get(url, headers=HEADERS).json()

    partidos = []
    for p in resp.get("response", []):
        if p["league"]["id"] in LIGAS_FAVORITAS:
            partidos.append(p)

    return partidos

# ---------------------------------------------------------
# PREDICCIONES SOLO EN DIRECTO
# ---------------------------------------------------------
def prob_gol(minuto, goles):
    return round(np.clip(minuto * 0.8 + goles * 10, 0, 100), 1)

def prob_btts(g1, g2, pg):
    if g1 > 0 and g2 > 0:
        return 90.0
    if g1 > 0 or g2 > 0:
        return round(pg * 0.6, 1)
    return round(pg * 0.4, 1)

def prob_over25(goles, pg):
    if goles >= 3:
        return 95.0
    if goles == 2:
        return round(pg * 0.8, 1)
    return round(pg * 0.5, 1)

# ---------------------------------------------------------
# MOSTRAR PARTIDOS DE HOY
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

        # Hora de inicio corregida
        hora_inicio = convertir_hora_local(f["date"])

        # Estado del partido
        estado = f["status"]["short"]
        minuto = f["status"]["elapsed"] or 0

        gl = g["home"] or 0
        gv = g["away"] or 0
        gt = gl + gv

        st.subheader(f"{t['home']['name']} vs {t['away']['name']}")
        st.write(f"🏟 {p['league']['name']}")
        st.write(f"🕒 Hora: **{hora_inicio}**")
        st.write(f"📌 Estado: **{estado}**")

        # Si está en directo → mostrar predicciones
        if estado in ["1H", "HT", "2H", "ET"]:
            st.write(f"⏱ Minuto: **{minuto}**")
            st.write(f"⚽ Marcador: **{gl} - {gv}**")

            pg = prob_gol(minuto, gt)
            pb = prob_btts(gl, gv, pg)
            po = prob_over25(gt, pg)

            c1, c2, c3 = st.columns(3)
            c1.metric("Prob. gol", f"{pg}%")
            c2.metric("BTTS", f"{pb}%")
            c3.metric("Over 2.5", f"{po}%")

        st.markdown("---")

# ---------------------------------------------------------
# PIE
# ---------------------------------------------------------
st.markdown("Creado por José — GolAlert PRO (HOY + Directos)")
