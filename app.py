import streamlit as st
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np

# ---------------------------------------------------------
# AUTO‑REFRESCO CADA 60 SEGUNDOS
# ---------------------------------------------------------
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()

if (datetime.now() - st.session_state.last_refresh).seconds >= 60:
    st.session_state.last_refresh = datetime.now()
    st.experimental_rerun()

# ---------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------
st.set_page_config(page_title="GolAlert PRO LIVE", page_icon="⚽", layout="wide")
st.title("⚽ GolAlert PRO LIVE — Ligas Favoritas")
st.markdown("Partidos de hoy, estadísticas en directo y pronósticos LIVE.")

# ---------------------------------------------------------
# API KEY
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
LIGAS_FAVORITAS = [40, 62, 39, 140, 141, 135, 78, 61, 94, 88, 144]

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
@st.cache_data(ttl=30)
def obtener_partidos_hoy():
    hoy = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE_URL}/fixtures?date={hoy}"
    resp = requests.get(url, headers=HEADERS).json()
    return [p for p in resp.get("response", []) if p["league"]["id"] in LIGAS_FAVORITAS]

# ---------------------------------------------------------
# ESTADÍSTICAS LIVE
# ---------------------------------------------------------
@st.cache_data(ttl=20)
def obtener_stats_live(fixture_id):
    url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS).json()
    return resp.get("response", [])

# ---------------------------------------------------------
# PARSEAR ESTADÍSTICAS POR EQUIPO
# ---------------------------------------------------------
def parse_stats(stats):
    home = {}
    away = {}

    if not stats:
        return home, away

    home_id = stats[0]["team"]["id"]

    for equipo in stats:
        datos = equipo["statistics"]
        target = home if equipo["team"]["id"] == home_id else away

        for s in datos:
            tipo = s["type"]
            val = s["value"] or 0

            if tipo == "Shots on Goal":
                target["shots_on"] = val
            elif tipo == "Total Shots":
                target["shots"] = val
            elif tipo == "Dangerous Attacks":
                target["dangerous_attacks"] = val
            elif tipo == "Corner Kicks":
                target["corners"] = val
            elif tipo == "expected_goals":
                target["xg"] = val
            elif tipo == "Ball Possession":
                try:
                    target["possession"] = float(str(val).replace("%", ""))
                except:
                    target["possession"] = 0

    return home, away

# ---------------------------------------------------------
# MOMENTUM POR EQUIPO
# ---------------------------------------------------------
def calcular_momentum(stats_equipo):
    xg = stats_equipo.get("xg", 0)
    shots = stats_equipo.get("shots", 0)
    shots_on = stats_equipo.get("shots_on", 0)
    da = stats_equipo.get("dangerous_attacks", 0)
    corners = stats_equipo.get("corners", 0)
    poss = stats_equipo.get("possession", 0)

    momentum = (
        xg * 4 +
        shots_on * 3 +
        shots * 1.5 +
        da * 0.8 +
        corners * 1.2 +
        poss * 0.1
    )
    return round(momentum, 1)

# ---------------------------------------------------------
# PROBABILIDADES LIVE
# ---------------------------------------------------------
def prob_gol_live(minuto, shots, shots_on, da, poss):
    score = (
        minuto * 0.4 +
        shots * 1.2 +
        shots_on * 3.5 +
        da * 0.8 +
        poss * 0.15
    )
    return round(np.clip(score, 0, 100), 1)

def prob_btts_live(gl, gv, mh, ma, pg):
    if gl > 0 and gv > 0:
        return 95.0

    if gl > 0 and ma > mh:
        return round(pg * 0.85, 1)

    if gv > 0 and mh > ma:
        return round(pg * 0.85, 1)

    if abs(mh - ma) < 10:
        return round(pg * 0.55, 1)

    return round(pg * 0.35, 1)

def prob_over25_live(goles, pg, mh, ma):
    if goles >= 3:
        return 98.0

    momentum_total = mh + ma

    if goles == 2:
        return round(pg * 0.9 + momentum_total * 0.05, 1)

    return round(pg * 0.45 + momentum_total * 0.03, 1)

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

        # ---------------------------------------------------------
        # ESTADO CON COLORES
        # ---------------------------------------------------------
        if estado in ["1H", "HT", "2H", "ET"]:
            estado_color = "🟩 Partido en directo"
        elif estado in ["NS", "TBD"]:
            estado_color = "🟧 Partido por empezar"
        else:
            estado_color = "🟥 Partido finalizado"

        # ---------------------------------------------------------
        # INFO EN UNA SOLA LÍNEA (HTML)
        # ---------------------------------------------------------
        col_info1, col_info2, col_info3 = st.columns([3, 1, 2])

        col_info1.markdown(
            f"<div style='font-size:18px; font-weight:bold;'>🏟 {p['league']['name']}</div>",
            unsafe_allow_html=True
        )

        col_info2.markdown(
            f"<div style='font-size:18px; font-weight:bold;'>🕒 {hora_inicio}</div>",
            unsafe_allow_html=True
        )

        col_info3.markdown(
            f"<div style='font-size:18px; font-weight:bold;'>{estado_color}</div>",
            unsafe_allow_html=True
        )

        # ---------------------------------------------------------
        # LIVE
        # ---------------------------------------------------------
        if estado in ["1H", "HT", "2H", "ET"]:
            st.write(f"⏱ Minuto: **{minuto}**")
            st.write(f"⚽ Marcador: **{gl} - {gv}**")

            stats = obtener_stats_live(fixture_id)
            home_stats, away_stats = parse_stats(stats)

            momentum_home = calcular_momentum(home_stats)
            momentum_away = calcular_momentum(away_stats)

            shots = home_stats.get("shots", 0) + away_stats.get("shots", 0)
            shots_on = home_stats.get("shots_on", 0) + away_stats.get("shots_on", 0)
            da = home_stats.get("dangerous_attacks", 0) + away_stats.get("dangerous_attacks", 0)
            poss = (home_stats.get("possession", 0) + away_stats.get("possession", 0)) / 2

            pg = prob_gol_live(minuto, shots, shots_on, da, poss)
            pb = prob_btts_live(gl, gv, momentum_home, momentum_away, pg)
            po = prob_over25_live(gt, pg, momentum_home, momentum_away)

            c1, c2, c3 = st.columns(3)
            c1.metric("Prob. gol LIVE", f"{pg}%")
            c2.metric("BTTS LIVE", f"{pb}%")
            c3.metric("Over 2.5 LIVE", f"{po}%")

            c4, c5 = st.columns(2)
            c4.metric("Momentum Local", momentum_home)
            c5.metric("Momentum Visitante", momentum_away)

            if momentum_home > momentum_away:
                st.success("🔥 El equipo LOCAL domina el partido")
            elif momentum_away > momentum_home:
                st.success("🔥 El equipo VISITANTE domina el partido")
            else:
                st.info("Partido equilibrado")

        st.markdown("---")

# ---------------------------------------------------------
# PIE
# ---------------------------------------------------------
st.markdown("Creado por José — GolAlert PRO LIVE")
