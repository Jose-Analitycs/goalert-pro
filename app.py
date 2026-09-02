import streamlit as st
import requests
import os
from datetime import datetime
import numpy as np

# ---------------------------------------------------------
# CONFIGURACIÓN DE LA APP
# ---------------------------------------------------------
st.set_page_config(
    page_title="GolAlert PRO",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ GolAlert PRO — Solo Ligas Favoritas (PLAN PRO)")
st.markdown("Partidos en directo + predicciones (sin estadísticas LIVE).")

# ---------------------------------------------------------
# API KEY DESDE SECRETS
# ---------------------------------------------------------
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

# ---------------------------------------------------------
# TUS LIGAS FAVORITAS (incluye Championship y Ligue 2)
# ---------------------------------------------------------
LIGAS_FAVORITAS = [
    140,  # LaLiga
    141,  # Segunda División
    39,   # Premier League
    40,   # Championship (ENG 2)
    135,  # Serie A
    78,   # Bundesliga
    79,   # 2. Bundesliga
    61,   # Ligue 1
    62,   # Ligue 2 (Francia 2)
    94,   # Primeira Liga
    88,   # Eredivisie
    144   # Jupiler Pro League
]

# ---------------------------------------------------------
# OBTENER PARTIDOS EN DIRECTO (PLAN PRO)
# ---------------------------------------------------------
def obtener_partidos_live_pro():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoy}"
    resp = requests.get(url, headers=HEADERS).json()

    partidos = []
    for p in resp.get("response", []):
        liga_id = p["league"]["id"]
        estado = p["fixture"]["status"]["short"]

        # Solo tus ligas favoritas
        if liga_id in LIGAS_FAVORITAS:
            # Solo partidos en directo
            if estado in ["1H", "HT", "2H", "ET"]:
                partidos.append(p)

    return partidos

# ---------------------------------------------------------
# MODELOS DE PREDICCIÓN (sin estadísticas LIVE)
# ---------------------------------------------------------
def prob_gol_simple(minuto, goles_totales):
    base = minuto * 0.8
    extra = goles_totales * 10
    prob = np.clip(base + extra, 0, 100)
    return round(prob, 1)

def prob_btts_simple(goles_local, goles_visitante, prob_gol_total):
    if goles_local > 0 and goles_visitante > 0:
        return 90.0
    elif goles_local > 0 or goles_visitante > 0:
        return round(prob_gol_total * 0.6, 1)
    else:
        return round(prob_gol_total * 0.4, 1)

def prob_over25_simple(goles_totales, prob_gol_total):
    if goles_totales >= 3:
        return 95.0
    elif goles_totales == 2:
        return round(prob_gol_total * 0.8, 1)
    else:
        return round(prob_gol_total * 0.5, 1)

# ---------------------------------------------------------
# MOSTRAR PARTIDOS EN DIRECTO
# ---------------------------------------------------------
st.header("🔴 Partidos EN DIRECTO — Solo Ligas Favoritas")

partidos_live = obtener_partidos_live_pro()

if len(partidos_live) == 0:
    st.warning("No hay partidos en directo en tus ligas favoritas.")
else:
    for p in partidos_live:
        fixture = p["fixture"]
        teams = p["teams"]
        goals = p["goals"]

        minuto = fixture["status"]["elapsed"] or 0
        goles_local = goals["home"] or 0
        goles_visitante = goals["away"] or 0
        goles_totales = goles_local + goles_visitante

        st.subheader(f"{teams['home']['name']} vs {teams['away']['name']}")
        st.write(f"🏟 Liga: **{p['league']['name']}**")
        st.write(f"⏱ Minuto: **{minuto}**")
        st.write(f"⚽ Marcador: **{goles_local} - {goles_visitante}**")

        # Predicciones
        prob_gol_total = prob_gol_simple(minuto, goles_totales)
        prob_btts = prob_btts_simple(goles_local, goles_visitante, prob_gol_total)
        prob_over25 = prob_over25_simple(goles_totales, prob_gol_total)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Prob. gol (próx. min)", f"{prob_gol_total}%")

        with col2:
            st.metric("BTTS", f"{prob_btts}%")

        with col3:
            st.metric("Over 2.5", f"{prob_over25}%")

        st.markdown("---")

# ---------------------------------------------------------
# PIE DE PÁGINA
# ---------------------------------------------------------
st.markdown("Creado por José — GolAlert PRO (Solo Ligas Favoritas, PLAN PRO)")
