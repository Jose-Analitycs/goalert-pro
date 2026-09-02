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

st.title("⚽ GolAlert PRO — LIVE + Predicciones")
st.markdown("Conexión segura a API‑Football usando Secrets.")

# ---------------------------------------------------------
# API KEY DESDE SECRETS
# ---------------------------------------------------------
API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

# ---------------------------------------------------------
# FUNCIÓN: PARTIDOS EN DIRECTO
# ---------------------------------------------------------
def obtener_partidos_live():
    url = f"{BASE_URL}/fixtures?live=all"
    resp = requests.get(url, headers=HEADERS).json()
    return resp.get("response", [])

# ---------------------------------------------------------
# FUNCIÓN: ESTADÍSTICAS LIVE DE UN PARTIDO
# ---------------------------------------------------------
def obtener_stats_live(fixture_id):
    url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS).json()
    stats = resp.get("response", [])
    if len(stats) < 2:
        return None, None

    home = stats[0]["statistics"]
    away = stats[1]["statistics"]
    return home, away

# ---------------------------------------------------------
# EXTRAER VALORES DE ESTADÍSTICAS
# ---------------------------------------------------------
def get_stat(stats, name):
    for s in stats:
        if s["type"] == name:
            return s["value"] if s["value"] is not None else 0
    return 0

# ---------------------------------------------------------
# MODELO SIMPLE DE PREDICCIÓN DE GOL (sin pickle)
# ---------------------------------------------------------
def prediccion_gol(attacks, dangerous, shots_on, possession):
    # Modelo simple basado en ponderaciones
    score = (
        attacks * 0.02 +
        dangerous * 0.05 +
        shots_on * 0.12 +
        possession * 0.01
    )
    prob = np.clip(score, 0, 100)
    return round(prob, 1)

# ---------------------------------------------------------
# PREDICCIÓN BTTS
# ---------------------------------------------------------
def prediccion_btts(prob_home, prob_away):
    btts = (prob_home * prob_away) / 100
    return round(btts, 1)

# ---------------------------------------------------------
# PREDICCIÓN OVER 2.5
# ---------------------------------------------------------
def prediccion_over25(prob_home, prob_away):
    total = prob_home + prob_away
    over = np.clip(total * 0.6, 0, 100)
    return round(over, 1)

# ---------------------------------------------------------
# MOSTRAR PARTIDOS EN DIRECTO
# ---------------------------------------------------------
st.header("🔴 Partidos EN DIRECTO con estadísticas y predicciones")

partidos_live = obtener_partidos_live()

if len(partidos_live) == 0:
    st.warning("No hay partidos en directo ahora mismo.")
else:
    for p in partidos_live:
        fixture = p["fixture"]
        teams = p["teams"]
        goals = p["goals"]

        fixture_id = fixture["id"]

        st.subheader(f"{teams['home']['name']} vs {teams['away']['name']}")
        st.write(f"⏱ Minuto: **{fixture['status']['elapsed']}**")
        st.write(f"⚽ Marcador: **{goals['home']} - {goals['away']}**")

        # Obtener estadísticas LIVE
        home_stats, away_stats = obtener_stats_live(fixture_id)

        if home_stats is None:
            st.info("Sin estadísticas LIVE disponibles.")
            st.markdown("---")
            continue

        # Extraer estadísticas
        h_att = get_stat(home_stats, "Attacks")
        a_att = get_stat(away_stats, "Attacks")

        h_dang = get_stat(home_stats, "Dangerous Attacks")
        a_dang = get_stat(away_stats, "Dangerous Attacks")

        h_shots = get_stat(home_stats, "Shots on Goal")
        a_shots = get_stat(away_stats, "Shots on Goal")

        h_pos = get_stat(home_stats, "Ball Possession")
        a_pos = get_stat(away_stats, "Ball Possession")

        # Predicciones
        prob_home = prediccion_gol(h_att, h_dang, h_shots, h_pos)
        prob_away = prediccion_gol(a_att, a_dang, a_shots, a_pos)

        prob_btts = prediccion_btts(prob_home, prob_away)
        prob_over25 = prediccion_over25(prob_home, prob_away)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Prob. gol local (5 min)", f"{prob_home}%")

        with col2:
            st.metric("Prob. gol visitante (5 min)", f"{prob_away}%")

        with col3:
            st.metric("BTTS", f"{prob_btts}%")

        st.metric("Over 2.5", f"{prob_over25}%")

        st.markdown("---")

# ---------------------------------------------------------
# PIE DE PÁGINA
# ---------------------------------------------------------
st.markdown("Creado por José — GolAlert PRO (LIVE + Predicciones)")

