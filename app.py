import streamlit as st
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import csv
import pandas as pd

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

# PESTAÑAS
tab1, tab2 = st.tabs(["📡 Partidos en directo", "📊 Rentabilidad"])

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
# ARCHIVO DE LOG
# ---------------------------------------------------------
LOG_FILE = "avisos_golalert.csv"

if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["partido", "aviso", "minuto", "prob", "goles", "resultado_final"])

def registrar_aviso(partido, aviso, minuto, prob, goles, resultado_final):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([partido, aviso, minuto, prob, goles, resultado_final])

# ---------------------------------------------------------
# LIGAS FAVORITAS
# ---------------------------------------------------------
LIGAS_FAVORITAS = [
    40, 62, 140, 141, 135,
    78, 79, 61, 63, 94,
    88, 144
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
# DETECCIÓN DE MOMENTOS ÓPTIMOS
# ---------------------------------------------------------

# GOL del equipo ANTES del primer gol
def detectar_momento_gol_pre(momentum_eq, momentum_rival, prob_gol, goles):
    if goles == 0 and momentum_eq >= 22 and (momentum_eq - momentum_rival) >= 8 and prob_gol >= 55:
        return "🟩 Partido caliente — buen momento para entrar al GOL del equipo que domina"
    return None

# GOL del equipo DESPUÉS del primer gol (partido abierto)
def detectar_momento_gol_post(momentum_eq, momentum_rival, prob_gol, goles):
    if goles >= 1 and momentum_eq >= 25 and prob_gol >= 60:
        return "🟩 Partido abierto — buen momento para entrar al GOL del equipo que aprieta"
    return None

# BTTS ANTES del primer gol
def detectar_momento_btts_pre(momentum_home, momentum_away, btts, goles):
    if goles == 0 and momentum_home >= 18 and momentum_away >= 18 and btts >= 55:
        return "🟧 Partido abierto — buen momento para BTTS"
    return None

# BTTS DESPUÉS del primer gol
def detectar_momento_btts_post(momentum_home, momentum_away, btts, goles):
    if goles == 1 and btts >= 60 and momentum_home >= 20 and momentum_away >= 20:
        return "🟧 Partido caliente — buen momento para BTTS tras el primer gol"
    return None

# OVER 2.5 ANTES del primer gol
def detectar_momento_over_pre(over25, goles, momentum_total):
    if goles == 0 and over25 >= 60 and momentum_total >= 40:
        return "🟥 Partido caliente — buen momento para entrar al OVER 2.5"
    return None

# OVER 2.5 DESPUÉS del primer gol
def detectar_momento_over_post(over25, goles, momentum_total):
    if goles == 1 and over25 >= 65 and momentum_total >= 45:
        return "🟥 Partido abierto — buen momento para entrar al OVER 2.5 tras el primer gol"
    return None

# ---------------------------------------------------------
# TAB 1 — PARTIDOS EN DIRECTO
# ---------------------------------------------------------
with tab1:
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

            # ESTADO CON COLORES
            if estado in ["1H", "HT", "2H", "ET"]:
                estado_color = "🟩 En directo"
            elif estado in ["NS", "TBD"]:
                estado_color = "🟧 Por empezar"
            else:
                estado_color = "🟥 Finalizado"

            # INFO EN UNA SOLA LÍNEA (FLEXBOX)
            st.markdown(
                f"""
                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    padding:8px 12px;
                    font-size:18px;
                    font-weight:bold;
                ">
                    <div>🏟 {p['league']['name']}</div>
                    <div>🕒 {hora_inicio}</div>
                    <div>{estado_color}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            # LIVE
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

                momentum_total = momentum_home + momentum_away
                partido_nombre = f"{t['home']['name']} vs {t['away']['name']}"
                resultado_final = f"{gl}-{gv}"

                # MOMENTOS ÓPTIMOS

                # GOL
                aviso_gol_local_pre = detectar_momento_gol_pre(momentum_home, momentum_away, pg, gt)
                aviso_gol_visit_pre = detectar_momento_gol_pre(momentum_away, momentum_home, pg, gt)

                aviso_gol_local_post = detectar_momento_gol_post(momentum_home, momentum_away, pg, gt)
                aviso_gol_visit_post = detectar_momento_gol_post(momentum_away, momentum_home, pg, gt)

                # BTTS
                aviso_btts_pre = detectar_momento_btts_pre(momentum_home, momentum_away, pb, gt)
                aviso_btts_post = detectar_momento_btts_post(momentum_home, momentum_away, pb, gt)

                # OVER
                aviso_over_pre = detectar_momento_over_pre(po, gt, momentum_total)
                aviso_over_post = detectar_momento_over_post(po, gt, momentum_total)

                # Mostrar avisos con minuto y registrar
                if aviso_gol_local_pre:
                    st.success(f"⚽ {aviso_gol_local_pre} (LOCAL) — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_gol_local_pre, minuto, pg, gt, resultado_final)

                if aviso_gol_visit_pre:
                    st.success(f"⚽ {aviso_gol_visit_pre} (VISITANTE) — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_gol_visit_pre, minuto, pg, gt, resultado_final)

                if aviso_gol_local_post:
                    st.success(f"⚽ {aviso_gol_local_post} (LOCAL) — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_gol_local_post, minuto, pg, gt, resultado_final)

                if aviso_gol_visit_post:
                    st.success(f"⚽ {aviso_gol_visit_post} (VISITANTE) — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_gol_visit_post, minuto, pg, gt, resultado_final)

                if aviso_btts_pre:
                    st.warning(f"🔄 {aviso_btts_pre} — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_btts_pre, minuto, pb, gt, resultado_final)

                if aviso_btts_post:
                    st.warning(f"🔄 {aviso_btts_post} — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_btts_post, minuto, pb, gt, resultado_final)

                if aviso_over_pre:
                    st.error(f"🔥 {aviso_over_pre} — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_over_pre, minuto, po, gt, resultado_final)

                if aviso_over_post:
                    st.error(f"🔥 {aviso_over_post} — min {minuto}")
                    registrar_aviso(partido_nombre, aviso_over_post, minuto, po, gt, resultado_final)

            st.markdown("---")

# ---------------------------------------------------------
# TAB 2 — RENTABILIDAD
# ---------------------------------------------------------
with tab2:
    st.header("📊 Rentabilidad GolAlert PRO")

    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)

        st.subheader("📑 Historial de avisos")
        st.dataframe(df)

        # Cálculo de aciertos
        def es_acierto(row):
            goles_local, goles_visit = map(int, row["resultado_final"].split("-"))
            total_goles = goles_local + goles_visit

            aviso = row["aviso"]

            if "GOL" in aviso:
                return 1 if row["goles"] > 0 else 0
            if "BTTS" in aviso:
                return 1 if (goles_local > 0 and goles_visit > 0) else 0
            if "OVER" in aviso:
                return 1 if total_goles >= 3 else 0
            return 0

        df["acierto"] = df.apply(es_acierto, axis=1)
        aciertos = df["acierto"].mean() * 100 if len(df) > 0 else 0

        st.subheader("📈 Estadísticas")
        st.write(f"✔ Aciertos totales: {aciertos:.2f}%")

        # ROI simulado (apuesta fija 1 unidad)
        df["roi"] = df["acierto"].apply(lambda x: 1 if x == 1 else -1)
        roi_total = df["roi"].sum()

        st.write(f"💰 ROI total (simulado, 1 unidad por aviso): {roi_total} unidades")

        # Value medio (aprox: prob / 50%)
        df["value"] = df["prob"] / 50
        st.write(f"🔥 Value medio aproximado: {df['value'].mean():.2f}")

    else:
        st.info("Todavía no hay avisos registrados. Deja la app funcionando y vuelve más tarde a esta pestaña.")

# ---------------------------------------------------------
# PIE
# ---------------------------------------------------------
st.markdown("Creado por José — GolAlert PRO LIVE")
