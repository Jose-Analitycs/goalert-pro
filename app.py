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

st.title("⚽ GolAlert PRO — LIVE + Predicciones (PLAN PRO)")
st.markdown("Usando API‑Football PLAN PRO (sin estadísticas avanzadas).")

# ---------------------------------------------------------
# API KEY DESDE SECRETS
# ---------------------------------------------------------
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

# ---------------------------------------------------------
# OBTENER PARTIDOS DE HOY Y FILTRAR LOS QUE ESTÁN EN JUEGO
# ---------------------------------------------------------
def obtener_partidos_live_pro():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoy}"
    resp = requests.get(url, headers=HEADERS).json()

    partidos = []
    for p in resp.get("response", []):
        estado = p["fixture"]["status"]["short"]
        # Estados que indican partido en juego
        if estado in ["1H", "HT", "2H", "ET"]:
            partidos.append(p)

    return partidos

# ---------------------------------------------------------
# MODELOS SENCILLOS DE PREDICCIÓN (SIN STATS LIVE)
# ---------------------------------------------------------
def prob_gol_simple(minuto, goles_totales):
    """
    Modelo muy simple:
    - A más minuto, más probabilidad de gol (por cansancio, riesgo, etc.)
    - Si ya hay goles, el partido es más abierto.
    """
    base = minuto * 0.8
    extra = goles_totales * 10
    prob = np.clip(base + extra, 0, 100)
    return round(prob, 1)

def prob_btts_simple(goles_local, goles_visitante, prob_gol_total):
    """
    BTTS simple:
    - Si ambos ya han marcado, prob alta.
    - Si solo uno ha marcado, depende de la probabilidad total de gol.
    """
    if goles_local > 0 and goles_visitante > 0:
        return 90.0
    elif goles_local > 0 or goles_visitante > 0:
        return round(prob_gol_total * 0.6, 1)
    else:
        return round(prob_gol_total * 0.4, 1)

def prob_over25_simple(goles_totales, prob_gol_total):
    """
    Over 2.5 simple:
    - Si ya hay 3 o más goles, casi asegurado.
    - Si hay 2, depende de probabilidad de gol.
    - Si hay menos, se ajusta.
    """
    if goles_totales >= 3:
        return 95.0
    elif goles_totales == 2:
        return round(prob_gol_total * 0.8, 1)
    else:
        return round(prob_gol_total * 0.5, 1)

# ---------------------------------------------------------
# MOSTRAR PARTIDOS EN DIRECTO (PLAN PRO)
# ---------------------------------------------------------
st.header("🔴 Partidos EN DIRECTO (PLAN PRO)")

partidos_live = obtener_partidos_live_pro()

if len(partidos_live) == 0:
    st.warning("No hay partidos en directo ahora mismo (según API‑Football PRO).")
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
        st.write(f"⏱ Minuto: **{minuto}**")
        st.write(f"⚽ Marcador: **{goles_local} - {goles_visitante}**")
        st.write(f"🏟 Estado: **{fixture['status']['short']}**")

        # Predicciones simples basadas en minuto y goles
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
st.markdown("Creado por José — GolAlert PRO (PLAN PRO, sin estadísticas avanzadas)")
