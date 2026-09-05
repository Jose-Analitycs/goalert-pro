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
    st.success("API KEY cargada correctamente.")

# ---------------------------------------------------------
# ARCHIVO DE LOG
# ---------------------------------------------------------
LOG_FILE = "avisos_golalert.csv"

if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
    with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["partido", "liga", "aviso", "minuto", "prob", "goles", "resultado_final"])

def registrar_aviso(partido, liga, aviso, minuto, prob, goles, resultado_final):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([partido, liga, aviso, minuto, prob, goles, resultado_final])

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
# PARSEAR ESTADÍSTICAS
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
# EVENTOS DEL PARTIDO
# ---------------------------------------------------------
@st.cache_data(ttl=20)
def obtener_eventos(fixture_id):
    url = f"{BASE_URL}/fixtures/events?fixture={fixture_id}"
    resp = requests.get(url, headers=HEADERS).json()
    return resp.get("response", [])

def stats_desde_eventos(eventos):
    stats = {
        "shots": 0,
        "shots_on": 0,
        "dangerous_attacks": 0,
        "corners": 0,
        "possession": 50,
        "xg": 0
    }

    for e in eventos:
        tipo = e["type"]
        detalle = e.get("detail", "")

        if tipo == "Shot":
            stats["shots"] += 1
            if detalle == "On Target":
                stats["shots_on"] += 1

        if tipo == "Attack":
            stats["dangerous_attacks"] += 1

        if tipo == "Corner":
            stats["corners"] += 1

        if tipo == "Goal":
            stats["xg"] += 0.25

    return stats

def minuto_real_gol(eventos):
    goles = [e for e in eventos if e["type"] == "Goal"]
    if not goles:
        return None
    return goles[-1]["time"]["elapsed"]

# ---------------------------------------------------------
# MOMENTUM
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

def momentum_hibrido(stats_equipo, eventos_equipo):
    if stats_equipo and any(stats_equipo.values()):
        return calcular_momentum(stats_equipo)
    stats_eventos = stats_desde_eventos(eventos_equipo)
    return calcular_momentum(stats_eventos)

# ---------------------------------------------------------
# PROBABILIDADES
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

def prob_gol_hibrida(minuto, stats_equipo, eventos_equipo):
    if stats_equipo and any(stats_equipo.values()):
        shots = stats_equipo.get("shots", 0)
        shots_on = stats_equipo.get("shots_on", 0)
        da = stats_equipo.get("dangerous_attacks", 0)
        poss = stats_equipo.get("possession", 50)
        return prob_gol_live(minuto, shots, shots_on, da, poss)

    stats_eventos = stats_desde_eventos(eventos_equipo)
    shots = stats_eventos["shots"]
    shots_on = stats_eventos["shots_on"]
    da = stats_eventos["dangerous_attacks"]
    poss = stats_eventos["possession"]

    return prob_gol_live(minuto, shots, shots_on, da, poss)

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
# PREDICCIONES EN TIEMPO REAL (PRE)
# ---------------------------------------------------------

predicciones = []

# GOL PRE
if pg >= 55 or mh > ma + 12:
    predicciones.append(f"⚽ Posible GOL — prob {pg}% — domina {'Local' if mh > ma else 'Visitante'}")

# BTTS PRE
if mh >= 25 and ma >= 25 and pb >= 45:
    predicciones.append(f"🔄 Posible BTTS — prob {pb}% — partido abierto")

# OVER PRE
momentum_total = mh + ma
if momentum_total >= 45 or po >= 50:
    predicciones.append(f"🔥 Posible OVER 2.5 — prob {po}% — ritmo alto")

# Mostrar predicciones
if predicciones:
    st.info("📡 **Predicciones en tiempo real:**")
    for p in predicciones:
        st.write(p)

# ---------------------------------------------------------
# DETECTORES PRO
# ---------------------------------------------------------
def detectar_momento_gol_pre(mh, ma, pg, goles):
    if goles == 0:
        if mh > ma + 15 and pg >= 70:
            return "GOL PRE (Local)"
        if ma > mh + 15 and pg >= 70:
            return "GOL PRE (Visitante)"
        if abs(mh - ma) < 10 and pg >= 80:
            return "GOL PRE (Partido caliente)"
    return None

def detectar_momento_gol_post(mh, ma, pg, goles):
    if goles >= 1:
        return "GOL POST"
    return None

def detectar_momento_btts_pre(mh, ma, pb, goles):
    if goles == 0:
        if mh >= 35 and ma >= 35 and pb >= 70:
            return "BTTS PRE (Ambos fuertes)"
        if abs(mh - ma) < 12 and pb >= 75:
            return "BTTS PRE (Partido caliente)"
    return None

def detectar_momento_btts_post(mh, ma, pb, goles):
    if goles == 1 and pb >= 70:
        return "BTTS POST"
    if goles >= 2:
        return "BTTS POST"
    return None

def detectar_momento_over_pre(po, goles, momentum_total):
    if goles <= 1:
        if momentum_total >= 55 and po >= 70:
            return "OVER PRE (Partido muy ofensivo)"
        if momentum_total >= 45 and po >= 80:
            return "OVER PRE (Caliente)"
    return None

def detectar_momento_over_post(po, goles, momentum_total):
    if goles >= 3:
        return "OVER POST"
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

            liga = p["league"]["name"]
            partido_nombre = f"{t['home']['name']} vs {t['away']['name']}"
            resultado_final = f"{gl}-{gv}"

            st.subheader(partido_nombre)

            if estado in ["1H", "HT", "2H", "ET"]:
                estado_color = "🟩 En directo"
            elif estado in ["NS", "TBD"]:
                estado_color = "🟧 Por empezar"
            else:
                estado_color = "🟥 Finalizado"

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
                    <div>🏟 {liga}</div>
                    <div>🕒 {hora_inicio}</div>
                    <div>{estado_color}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

            if estado in ["1H", "HT", "2H", "ET"]:
                st.write(f"⏱ Minuto: **{minuto}**")
                st.write(f"⚽ Marcador: **{gl} - {gv}**")

                stats = obtener_stats_live(fixture_id)
                home_stats, away_stats = parse_stats(stats)

                eventos = obtener_eventos(fixture_id)
                eventos_local = [e for e in eventos if e["team"]["id"] == t["home"]["id"]]
                eventos_visitante = [e for e in eventos if e["team"]["id"] == t["away"]["id"]]

                mh = momentum_hibrido(home_stats, eventos_local)
                ma = momentum_hibrido(away_stats, eventos_visitante)

                pg = prob_gol_hibrida(minuto, home_stats, eventos_local)
                pb = prob_btts_live(gl, gv, mh, ma, pg)
                po = prob_over25_live(gt, pg, mh, ma)

                st.markdown(
                    f"""
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        width:100%;
                        padding:10px;
                        font-size:18px;
                        font-weight:bold;
                    ">
                        <div>Prob. Gol LIVE: {pg}%</div>
                        <div>BTTS LIVE: {pb}%</div>
                        <div>Over 2.5 LIVE: {po}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown(
                    f"""
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        width:100%;
                        padding:10px;
                        font-size:18px;
                        font-weight:bold;
                    ">
                        <div>Momentum Local: {mh}</div>
                        <div>Momentum Visitante: {ma}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                momentum_total = mh + ma

                avisos = [
                    detectar_momento_gol_pre(mh, ma, pg, gt),
                    detectar_momento_gol_post(mh, ma, pg, gt),
                    detectar_momento_btts_pre(mh, ma, pb, gt),
                    detectar_momento_btts_post(mh, ma, pb, gt),
                    detectar_momento_over_pre(po, gt, momentum_total),
                    detectar_momento_over_post(po, gt, momentum_total)
                ]

                for aviso in avisos:
                    if aviso:
                        if "GOL" in aviso:
                            if "PRE" in aviso:
                                st.success(f"⚽ {aviso} — min {minuto} — prob {pg}%")
                                registrar_aviso(partido_nombre, liga, aviso, minuto, pg, gt, resultado_final)
                            else:
                                minuto_real = minuto_real_gol(eventos)
                                if minuto_real:
                                    st.success(f"⚽ {aviso} — gol real min {minuto_real}")
                                else:
                                    st.success(f"⚽ {aviso} — min {minuto}")
                                registrar_aviso(partido_nombre, liga, aviso, minuto, "-", gt, resultado_final)

                        elif "BTTS" in aviso:
                            if "PRE" in aviso:
                                st.warning(f"🔄 {aviso} — min {minuto} — prob {pb}%")
                                registrar_aviso(partido_nombre, liga, aviso, minuto, pb, gt, resultado_final)
                            else:
                                st.warning(f"🔄 {aviso} — min {minuto}")
                                registrar_aviso(partido_nombre, liga, aviso, minuto, "-", gt, resultado_final)

                        elif "OVER" in aviso:
                            if "PRE" in aviso:
                                st.error(f"🔥 {aviso} — min {minuto} — prob {po}%")
                                registrar_aviso(partido_nombre, liga, aviso, minuto, po, gt, resultado_final)
                            else:
                                st.error(f"🔥 {aviso} — min {minuto}")
                                registrar_aviso(partido_nombre, liga, aviso, minuto, "-", gt, resultado_final)

            st.markdown("---")

# ---------------------------------------------------------
# TAB 2 — RENTABILIDAD
# ---------------------------------------------------------
with tab2:
    st.header("📊 Rentabilidad GolAlert PRO")

    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 0:
        df = pd.read_csv(LOG_FILE)

        columnas = ["partido", "liga", "aviso", "minuto", "prob", "goles", "resultado_final"]
        if not all(col in df.columns for col in columnas):
            st.warning("El archivo de avisos es antiguo. Se actualizará cuando lleguen nuevos avisos.")
            st.stop()

        st.subheader("📑 Historial de avisos")
        st.dataframe(df)

        def es_acierto(row):
            try:
                gl, gv = map(int, row["resultado_final"].split("-"))
                total = gl + gv
            except:
                return 0

            aviso = row["aviso"]

            if "GOL" in aviso:
                return 1 if row["goles"] > 0 else 0
            if "BTTS" in aviso:
                return 1 if gl > 0 and gv > 0 else 0
            if "OVER" in aviso:
                return 1 if total >= 3 else 0
            return 0

        df["acierto"] = df.apply(es_acierto, axis=1)
        df["roi"] = df["acierto"].apply(lambda x: 1 if x == 1 else -1)
        df["value"] = df["prob"].apply(lambda p: 0 if p == "-" else float(p) / 50)

        st.subheader("📈 Estadísticas globales")
        st.write(f"✔ Aciertos totales: **{df['acierto'].mean()*100:.2f}%**")
        st.write(f"💰 ROI total: **{df['roi'].sum()} unidades**")
        st.write(f"🔥 Value medio: **{df['value'].mean():.2f}**")

        st.subheader("🏆 Rentabilidad por ligas")
        ligas = df["liga"].unique()
        tabla_ligas = []

        for liga in ligas:
            df_l = df[df["liga"] == liga]
            tabla_ligas.append([
                liga,
                f"{df_l['acierto'].mean()*100:.2f}%",
                df_l["roi"].sum()
            ])

        st.table(pd.DataFrame(tabla_ligas, columns=["Liga", "Acierto", "ROI"]))

        st.subheader("🎯 Rentabilidad por mercados")
        mercados = ["GOL", "BTTS", "OVER"]
        tabla_mercados = []

        for mercado in mercados:
            df_m = df[df["aviso"].str.contains(mercado)]
            if len(df_m) > 0:
                tabla_mercados.append([
                    mercado,
                    f"{df_m['acierto'].mean()*100:.2f}%",
                    df_m["roi"].sum(),
                    f"{df_m['value'].mean():.2f}"
                ])
            else:
                tabla_mercados.append([mercado, "0%", 0, "0.00"])

        st.table(pd.DataFrame(tabla_mercados, columns=["Mercado", "Acierto", "ROI", "Value"]))

        st.success("Rentabilidad calculada correctamente.")
    else:
        st.info("Todavía no hay avisos registrados. Deja la app funcionando y vuelve más tarde.")
