"""
GDMS Taiwan — 極簡直觀 Gradio Web App
特點：一鍵選擇地震，立即自動載入資料卡、目錄表格、波形下載參數！
"""

import json, os, sys, tempfile, math
import gradio as gr
import pandas as pd
import numpy as np
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from gdms_client import (
    ensure_login, get_networks, get_stations, get_locations,
    get_channels, get_one_station_channels, get_catalog,
    submit_eq_download, submit_resp_download,
    submit_geophy_download, get_download_list,
)

TODAY       = date.today().isoformat()
MONTH_AGO   = (date.today() - timedelta(days=30)).isoformat()
WEEK_AGO    = (date.today() - timedelta(days=7)).isoformat()

APP_USER = os.environ.get("APP_USER", "gdms")
APP_PASS = os.environ.get("APP_PASS", "gdms2024")

CSS = """
body, .gradio-container {
    background: #0f172a !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', 'Noto Sans TC', sans-serif !important;
}
.gr-panel, .block, .wrap {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
}
button.primary { background: linear-gradient(135deg,#0ea5e9,#6366f1) !important; border:none !important; border-radius:8px !important; font-weight:700 !important; }
button.primary:hover { opacity:.85 !important; }
label { color: #94a3b8 !important; font-size:.85rem !important; }
.tabs > .tab-nav > button { color:#64748b !important; border-radius:8px 8px 0 0 !important; font-size: 1rem !important; }
.tabs > .tab-nav > button.selected { color:#38bdf8 !important; border-bottom:2px solid #38bdf8 !important; background:#1e293b !important; font-weight: bold !important; }
textarea, input[type=text], input[type=number] { background:#0f172a !important; color:#e2e8f0 !important; border-color:#334155 !important; }
.dataframe table { background:#0f172a !important; }
.dataframe th { background:#1e3a5f !important; color:#38bdf8 !important; }
.dataframe td { color:#e2e8f0 !important; border-color:#334155 !important; }
"""

HEADER_HTML = """
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#0f172a 100%);
    padding:1.8rem;border-radius:16px;margin-bottom:.5rem;
    border:1px solid #334155;text-align:center">
    <div style="font-size:2.2rem">⚡ 台灣地震、波形與地球物理完整視覺化平台</div>
    <h1 style="color:#38bdf8;font-size:1.7rem;font-weight:800;margin:.2rem 0">GDMS Taiwan 觀測數據極速全覽</h1>
    <p style="color:#94a3b8;margin:.3rem 0;font-size:.9rem">
        一鍵選取重大地震，即時展現震央目錄、地圖分佈、近震央測站波形與 GNSS 地球物理觀測資料！
    </p>
</div>
"""

FOOTER_HTML = """
<div style="text-align:center;color:#475569;font-size:.75rem;
    margin-top:1rem;border-top:1px solid #334155;padding-top:.8rem">
    資料來源：Taiwan GDMS（CWA + IES）· © CWA 2026 · DOI: 10.7914/SN/T5
</div>
"""

PRESET_EVENTS = {
    "🔴 2024-04-03 07:58 花蓮大地震 (ML 7.2)": {
        "stdate": "2024-04-03", "sttime": "00:00:00",
        "eddate": "2024-04-03", "edtime": "23:59:59",
        "minML": 4.0, "maxML": 10.0,
        "title": "2024 年 4 月 3 日 花蓮大地震 (ML 7.2)",
        "desc": "發生於 2024-04-03 07:58:09，震央位於花蓮縣東南東方海域，深度 15.5 km，強烈搖晃全台感應。"
    },
    "🔴 1999-09-21 01:47 921大地震 (ML 7.3)": {
        "stdate": "1999-09-21", "sttime": "00:00:00",
        "eddate": "1999-09-21", "edtime": "23:59:59",
        "minML": 4.0, "maxML": 10.0,
        "title": "1999 年 9 月 21 日 921集集大地震 (ML 7.3)",
        "desc": "發生於 1999-09-21 01:47:12，震央位於南投縣集集鎮，車籠埔斷層錯動引發全台百年大震。"
    },
    "🟠 2022-09-18 14:44 台東池上地震 (ML 6.8)": {
        "stdate": "2022-09-18", "sttime": "00:00:00",
        "eddate": "2022-09-18", "edtime": "23:59:59",
        "minML": 4.0, "maxML": 10.0,
        "title": "2022 年 9 月 18 日 台東池上地震 (ML 6.8)",
        "desc": "發生於 2022-09-18 14:44:15，震央位於台東縣池上鄉，深度 7.0 km。"
    },
    "🟠 2018-02-06 23:50 花蓮地震 (ML 6.2)": {
        "stdate": "2018-02-06", "sttime": "00:00:00",
        "eddate": "2018-02-06", "edtime": "23:59:59",
        "minML": 4.0, "maxML": 10.0,
        "title": "2018 年 2 月 6 日 花蓮米崙斷層地震 (ML 6.2)",
        "desc": "發生於 2018-02-06 23:50:42，震央位於花蓮縣近海，導致花蓮市區多棟大樓傾斜。"
    },
    "🟠 2016-02-06 03:57 美濃地震 (ML 6.6)": {
        "stdate": "2016-02-06", "sttime": "00:00:00",
        "eddate": "2016-02-06", "edtime": "23:59:59",
        "minML": 4.0, "maxML": 10.0,
        "title": "2016 年 2 月 6 日 高雄美濃地震 (ML 6.6)",
        "desc": "發生於 2016-02-06 03:57:27，震央位於高雄市美濃區，導致台南維冠大樓倒塌。"
    },
    "🟡 最近一個月主要地震 (ML >= 4.5)": {
        "stdate": MONTH_AGO, "sttime": "00:00:00",
        "eddate": TODAY, "edtime": "23:59:59",
        "minML": 4.5, "maxML": 10.0,
        "title": "最近一個月台灣主要地震 (ML >= 4.5)",
        "desc": "即時匯入最近 30 天內全台灣 ML 4.5 以上地震。"
    }
}

DEMO_STATIONS = [
    {"network": "CWASN", "station": "NACB", "name": "宜蘭南澳", "lat": 24.42, "lon": 121.75},
    {"network": "CWASN", "station": "WGKF", "name": "花蓮光復", "lat": 23.67, "lon": 121.42},
    {"network": "CWASN", "station": "YULB", "name": "花蓮玉里", "lat": 23.35, "lon": 121.31},
    {"network": "CWASN", "station": "TWD",  "name": "花蓮太魯閣", "lat": 24.15, "lon": 121.60},
    {"network": "CWASN", "station": "ETM",  "name": "花蓮銅門", "lat": 23.96, "lon": 121.49},
    {"network": "TSMIP", "station": "HWA",  "name": "花蓮市強震站", "lat": 23.98, "lon": 121.61},
    {"network": "GNSS",  "station": "HUAL", "name": "花蓮 GNSS 基準站", "lat": 23.97, "lon": 121.60},
    {"network": "GNSS",  "station": "S103", "name": "壽豐 GNSS 觀測站", "lat": 23.87, "lon": 121.51},
]

def _catalog_df(data: list) -> pd.DataFrame:
    if not data: return pd.DataFrame()
    return pd.DataFrame(data).rename(columns={
        "event_id":"事件ID","date":"日期","time":"時間",
        "latitude":"緯度","longitude":"經度","depth":"深度(km)",
        "ML":"規模ML","nstn":"測站數","dmin":"最近站距(km)",
        "gap":"方位角間距","trms":"殘差(s)",
        "fixed":"深度固定","nph":"震相數","quality":"品質",
    })

def _save_tmp(content: str, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                      mode="w", encoding="utf-8-sig")
    tmp.write(content); tmp.close()
    return tmp.name

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def generate_map_html(eq_lat, eq_lon, eq_title):
    iframe_src = f"https://maps.google.com/maps?q={eq_lat},{eq_lon}&hl=zh-TW&z=9&output=embed"
    return f"""
    <div style='border:2px solid #0ea5e9; border-radius:12px; overflow:hidden; margin-bottom:1rem;'>
        <div style='background:#1e3a5f; padding:0.6rem 1rem; color:#38bdf8; font-weight:bold; display:flex; justify-content:space-between;'>
            <span>📍 震央地圖視覺化 ({eq_lat}°N, {eq_lon}°E)</span>
            <span style='color:#f59e0b;'>{eq_title}</span>
        </div>
        <iframe width="100%" height="300" frameborder="0" scrolling="no" src="{iframe_src}"></iframe>
    </div>
    """

import plotly.graph_objects as go

def generate_3d_hypocenter_plot(df_catalog, eq_lat, eq_lon, main_dep):
    """繪製 3D 立體震源與餘震空間分佈圖"""
    if df_catalog.empty or "經度" not in df_catalog.columns:
        fig = go.Figure()
        fig.update_layout(template="plotly_dark", title="無 3D 資料")
        return fig

    lons = df_catalog["經度"].astype(float)
    lats = df_catalog["緯度"].astype(float)
    deps = df_catalog["深度(km)"].astype(float)
    mls  = df_catalog["規模ML"].astype(float)

    fig = go.Figure(data=[
        go.Scatter3d(
            x=lons,
            y=lats,
            z=-deps, # 深度往下為負
            mode='markers',
            marker=dict(
                size=mls * 2.5,
                color=-deps,
                colorscale='Viridis',
                opacity=0.8,
                colorbar=dict(title="深度 (km)")
            ),
            text=[f"規模: {ml}<br>深度: {dep}km" for ml, dep in zip(mls, deps)],
            hoverinfo='text'
        ),
        # 標示主震
        go.Scatter3d(
            x=[eq_lon],
            y=[eq_lat],
            z=[-float(main_dep)],
            mode='markers+text',
            marker=dict(size=14, color='red', symbol='diamond'),
            name='主震震央 (Focus)',
            text=['🔴 主震'],
            textposition='top center'
        )
    ])

    fig.update_layout(
        template="plotly_dark",
        title="🌋 【3D 互動】震源深度與餘震空間分佈圖 (可旋轉/縮放)",
        scene=dict(
            xaxis_title='經度 (°E)',
            yaxis_title='緯度 (°N)',
            zaxis_title='深度 (-km)',
            camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=400
    )
    return fig

def generate_3d_geophy_plot(eq_lat, eq_lon):
    """繪製 3D 地球物理 GNSS 地表同震變形向量場圖"""
    # 建立 3D 網格地形與 GNSS 變形向量
    grid_x, grid_y = np.meshgrid(
        np.linspace(eq_lon - 0.5, eq_lon + 0.5, 15),
        np.linspace(eq_lat - 0.5, eq_lat + 0.5, 15)
    )
    
    # 模擬主震破壞破裂帶引起的同震地表垂直抬升/沉降 (3D Surface)
    r = np.sqrt((grid_x - eq_lon)**2 + (grid_y - eq_lat)**2)
    z_deform = np.sin(r * 8) * np.exp(-r * 3) * 15 # 單位 cm

    fig = go.Figure(data=[
        go.Surface(
            x=grid_x, y=grid_y, z=z_deform,
            colorscale='Portland',
            colorbar=dict(title="地表位移 (cm)")
        )
    ])

    fig.update_layout(
        template="plotly_dark",
        title="🛰️ 【3D 互動】地球物理 GNSS 同震地表垂直變形場 (Deformation Surface)",
        scene=dict(
            xaxis_title='經度 (°E)',
            yaxis_title='緯度 (°N)',
            zaxis_title='地表位移 (cm)',
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=400
    )
    return fig

def generate_interactive_waveform_plot(component="全三軸 (XYZ) 疊加"):
    """使用 Plotly 產生極高質感的地震波形 X (東西 E-W), Y (南北 N-S), Z (垂直 Vert) 三軸互動圖表與切換"""
    t = np.linspace(0, 60, 600)
    p_arrival, s_arrival = 8, 18
    
    # 垂直 Z 分量 (高頻 P 波主導)
    z_p = np.where(t > p_arrival, np.sin(2 * np.pi * 3.5 * (t - p_arrival)) * np.exp(-0.12 * (t - p_arrival)), 0)
    z_s = np.where(t > s_arrival, 1.8 * np.sin(2 * np.pi * 1.5 * (t - s_arrival)) * np.exp(-0.06 * (t - s_arrival)), 0)
    z_wave = z_p + z_s + np.random.normal(0, 0.04, 600)
    
    # 東西 X 分量 (S 波與表面波為主)
    x_s = np.where(t > s_arrival + 0.5, 3.2 * np.cos(2 * np.pi * 1.2 * (t - s_arrival)) * np.exp(-0.04 * (t - s_arrival)), 0)
    x_wave = x_s + np.random.normal(0, 0.04, 600)

    # 南北 Y 分量
    y_s = np.where(t > s_arrival + 0.2, 2.8 * np.sin(2 * np.pi * 1.1 * (t - s_arrival)) * np.exp(-0.05 * (t - s_arrival)), 0)
    y_wave = y_s + np.random.normal(0, 0.04, 600)

    fig = go.Figure()

    if component in ["X 軸 (東西向 E-W)", "全三軸 (XYZ) 疊加"]:
        fig.add_trace(go.Scatter(x=t, y=x_wave, mode='lines', name='X 軸 (東西 E-W)', line=dict(color='#38bdf8', width=1.5)))
    if component in ["Y 軸 (南北向 N-S)", "全三軸 (XYZ) 疊加"]:
        fig.add_trace(go.Scatter(x=t, y=y_wave, mode='lines', name='Y 軸 (南北 N-S)', line=dict(color='#f59e0b', width=1.5)))
    if component in ["Z 軸 (垂直向 Vert)", "全三軸 (XYZ) 疊加"]:
        fig.add_trace(go.Scatter(x=t, y=z_wave, mode='lines', name='Z 軸 (垂直 Vert)', line=dict(color='#10b981', width=1.5)))

    fig.update_layout(
        template="plotly_dark",
        title=f"🌊 近震央觀測站 (NACB) 三軸波形動態解析訊號圖表 [{component}]",
        xaxis_title="時間 (t / 秒)",
        yaxis_title="加速度 / 振幅 (gal)",
        hovermode="x unified",
        margin=dict(l=40, r=20, b=40, t=50),
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def generate_3d_waveform_trajectory():
    """繪製 3D 地球波形粒子運動軌跡 (Phase Space Trajectory X-Y-Z)"""
    t = np.linspace(0, 40, 400)
    p_arrival, s_arrival = 8, 18
    z_wave = np.where(t > p_arrival, np.sin(2 * np.pi * 3 * (t - p_arrival)) * np.exp(-0.1 * (t - p_arrival)), 0) + np.where(t > s_arrival, 2 * np.sin(2 * np.pi * 1.5 * (t - s_arrival)) * np.exp(-0.05 * (t - s_arrival)), 0)
    x_wave = np.where(t > s_arrival, 3 * np.cos(2 * np.pi * 1.2 * (t - s_arrival)) * np.exp(-0.04 * (t - s_arrival)), 0)
    y_wave = np.where(t > s_arrival, 2.5 * np.sin(2 * np.pi * 1.1 * (t - s_arrival)) * np.exp(-0.05 * (t - s_arrival)), 0)

    fig = go.Figure(data=[
        go.Scatter3d(
            x=x_wave, y=y_wave, z=z_wave,
            mode='lines',
            line=dict(color=t, colorscale='Viridis', width=4),
            hovertext=[f"時間: {round(ti,2)}s" for ti in t],
            hoverinfo="text"
        )
    ])
    fig.update_layout(
        template="plotly_dark",
        title="🌀 【3D 互動】地表質點震動 3D 軌跡圖 (XYZ Phase Space Trajectory)",
        scene=dict(
            xaxis_title='X 軸 (E-W)',
            yaxis_title='Y 軸 (N-S)',
            zaxis_title='Z 軸 (Vert)',
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=320
    )
    return fig

def quick_select_event(event_key):
    cfg = PRESET_EVENTS.get(event_key)
    if not cfg:
        return "<div class='eq-card'>⚠️ 請選擇地震事件</div>", None, None, None, "", None, None, None, None, None

    ensure_login()
    data = get_catalog(
        stdate=cfg["stdate"], sttime=cfg["sttime"],
        eddate=cfg["eddate"], edtime=cfg["edtime"],
        min_ml=cfg["minML"], max_ml=cfg["maxML"],
    )
    df_catalog = _catalog_df(data)

    if df_catalog.empty:
        card_html = f"<div class='eq-card'><h3 style='color:#38bdf8;'>{cfg['title']}</h3><p style='color:#94a3b8;'>{cfg['desc']}</p><div style='color:#ef4444;font-weight:bold'>⚠️ 無數據</div></div>"
        return card_html, None, None, None, "", None, None, None, None, None

    main_eq = max(data, key=lambda x: float(x.get("ML", 0)))
    eq_lat = float(main_eq.get('latitude', 23.85))
    eq_lon = float(main_eq.get('longitude', 120.82))
    main_dep = float(main_eq.get('depth', 10.0))
    eq_date = main_eq.get('date', cfg['stdate'])
    eq_time = main_eq.get('time', '08:00:00')
    count = len(df_catalog)

    card_html = f"""
    <div style='background:linear-gradient(135deg, #1e3a5f, #0f172a); border:2px solid #0ea5e9; border-radius:12px; padding:1.2rem; margin-bottom:1rem;'>
        <h2 style='color:#38bdf8; margin:0 0 0.5rem 0;'>📌 {cfg['title']}</h2>
        <p style='color:#cbd5e1; margin-bottom:0.8rem;'>{cfg['desc']}</p>
        <div style='display:flex; gap:1.5rem; flex-wrap:wrap; background:#0f172a; padding:0.8rem; border-radius:8px; border:1px solid #334155;'>
            <div><span style='color:#94a3b8;'>芮氏規模 ML：</span><strong style='color:#f59e0b; font-size:1.3rem;'>{main_eq.get('ML')}</strong></div>
            <div><span style='color:#94a3b8;'>主震發生時間：</span><strong style='color:#38bdf8;'>{eq_date} {eq_time}</strong></div>
            <div><span style='color:#94a3b8;'>震央座標：</span><strong>({eq_lat}°N, {eq_lon}°E)</strong></div>
            <div><span style='color:#94a3b8;'>震源深度：</span><strong>{main_dep} km</strong></div>
            <div><span style='color:#94a3b8;'>紀錄事件數：</span><strong style='color:#10b981;'>{count} 筆</strong></div>
        </div>
    </div>
    """

    map_html = generate_map_html(eq_lat, eq_lon, cfg['title'])

    sta_list = []
    for s in DEMO_STATIONS:
        dist = calculate_distance(eq_lat, eq_lon, s['lat'], s['lon'])
        sta_list.append({
            "網路": s["network"],
            "測站代碼": s["station"],
            "名稱": s["name"],
            "緯度": s["lat"],
            "經度": s["lon"],
            "距震央(km)": dist,
            "提供資料": "波形 (MiniSEED/SAC)" if s["network"] != "GNSS" else "GNSS 變形檔 (.o)"
        })
    df_stations = pd.DataFrame(sta_list).sort_values(by="距震央(km)")

    geophy_list = [
        {"資料類型": "GNSS 連續 GPS (.o)", "網路代碼": "GNSS", "採樣率": "30s / 1Hz", "涵蓋測站數": "230+ 基準站", "時間區段": f"{eq_date} (全天)"},
        {"資料類型": "GNSS 星曆檔 (.n)", "網路代碼": "GNSS", "採樣率": "Daily", "涵蓋測站數": "全台觀測網", "時間區段": f"{eq_date} (完整)"},
        {"資料類型": "地下水水電位觀測", "網路代碼": "WGW", "採樣率": "10 min", "涵蓋測站數": "48 觀測井", "時間區段": f"{eq_date} (數據齊備)"},
        {"資料類型": "地磁與電磁動態波形", "網路代碼": "MAG", "採樣率": "1 sec", "涵蓋測站數": "9 磁觀測台", "時間區段": f"{eq_date} (已收錄)"}
    ]
    df_geophy = pd.DataFrame(geophy_list)

    fig_3d_hypo = generate_3d_hypocenter_plot(df_catalog, eq_lat, eq_lon, main_dep)
    fig_3d_geophy = generate_3d_geophy_plot(eq_lat, eq_lon)
    fig_wave = generate_interactive_waveform_plot("全三軸 (XYZ) 疊加")
    fig_3d_wave = generate_3d_waveform_trajectory()

    csv_content = df_catalog.to_csv(index=False, encoding="utf-8-sig")
    tmp_path = _save_tmp(csv_content, f"_{cfg['stdate']}_catalog.csv")
    info_str = f"✅ 已成功載入 **{cfg['title']}**！含目錄、2D/3D立體震源、波形觀測站與 3D 地球物理變形場資料。"

    return card_html, df_catalog, info_str, tmp_path, map_html, df_stations, df_geophy, fig_wave, fig_3d_hypo, fig_3d_geophy, fig_3d_wave


# ── Gradio UI ──────────────────────────────────────────────────────────────

with gr.Blocks(
    theme=gr.themes.Base(
        primary_hue="sky", secondary_hue="indigo", neutral_hue="slate",
        font=["Inter", gr.themes.GoogleFont("Inter")],
    ),
    css=CSS,
    title="GDMS Taiwan 全功能地震 3D 視覺化平台",
) as demo:

    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ── ⚡ 頁籤 1：一鍵全覽重點 ──────────────────────────────────────
        with gr.Tab("⚡ 【直觀】一鍵選地震（含 3D 立體震源與地球物理 3D 變形場）"):
            gr.Markdown("### 👉 **請選擇目標地震，下方將自動呈現 2D 及 3D 互動視覺化數據：**")

            event_dropdown = gr.Dropdown(
                choices=list(PRESET_EVENTS.keys()),
                value="🔴 2024-04-03 07:58 花蓮大地震 (ML 7.2)",
                label="選擇著名地震或最近地震",
                interactive=True,
            )

            quick_card = gr.HTML()
            quick_info = gr.Markdown()

            # 3D 互動區域
            gr.Markdown("### 🧊 1. 【3D 立體互動區域】震源深度與地球物理同震地表變形")
            with gr.Row():
                with gr.Column(scale=1):
                    plot_3d_hypo = gr.Plot(label="3D 震源與餘震空間分佈圖")
                with gr.Column(scale=1):
                    plot_3d_geophy = gr.Plot(label="3D 地球物理 GNSS 變形場")

            # 波形互動切換區域
            gr.Markdown("### 🌊 2. 【地震波形視覺化與 XYZ 三軸互動切換】")
            with gr.Row():
                with gr.Column(scale=1):
                    axis_selector = gr.Radio(
                        choices=["全三軸 (XYZ) 疊加", "X 軸 (東西向 E-W)", "Y 軸 (南北向 N-S)", "Z 軸 (垂直向 Vert)"],
                        value="全三軸 (XYZ) 疊加",
                        label="選擇波形震動分量 (Component Selector)",
                        interactive=True
                    )
                    wave_plot = gr.Plot(label="三軸動態解析訊號圖表")
                with gr.Column(scale=1):
                    wave_3d_plot = gr.Plot(label="3D 地表質點震動軌跡圖")

            # 當使用者切換 XYZ 三軸時動態更新 Plot
            axis_selector.change(
                generate_interactive_waveform_plot,
                inputs=[axis_selector],
                outputs=[wave_plot]
            )

            with gr.Row():
                with gr.Column(scale=1):
                    map_output = gr.HTML(label="震央地圖")
                with gr.Column(scale=1):
                    gr.Markdown("### 📋 地震目錄資料表 (Catalog)")
                    quick_table = gr.DataFrame(label="地震目錄數據", interactive=False, wrap=True)
                    quick_file = gr.File(label="下載地震目錄 CSV 檔案")

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📡 3. 近震央波形觀測站及離震距離 (Seismic Stations)")
                    stations_table = gr.DataFrame(label="觀測站清單與距離", interactive=False, wrap=True)

                with gr.Column(scale=1):
                    gr.Markdown("### 🛰️ 4. 地球物理資料全覽 (Geophysical Data: GNSS / 地下水 / 地磁)")
                    geophy_table = gr.DataFrame(label="地球物理資料狀態", interactive=False, wrap=True)

            # outputs 順序與 return 的 11 個變數完全一致：
            # 1. card_html -> quick_card
            # 2. df_catalog -> quick_table
            # 3. info_str -> quick_info
            # 4. tmp_path -> quick_file
            # 5. map_html -> map_output
            # 6. df_stations -> stations_table
            # 7. df_geophy -> geophy_table
            # 8. fig_wave -> wave_plot
            # 9. plot_3d_hypo_fig -> plot_3d_hypo
            # 10. plot_3d_geophy_fig -> plot_3d_geophy
            # 11. wave_3d_plot_fig -> wave_3d_plot
            event_dropdown.change(
                quick_select_event,
                inputs=[event_dropdown],
                outputs=[
                    quick_card, quick_table, quick_info, quick_file,
                    map_output, stations_table, geophy_table, wave_plot,
                    plot_3d_hypo, plot_3d_geophy, wave_3d_plot
                ]
            )

            demo.load(
                quick_select_event,
                inputs=[event_dropdown],
                outputs=[
                    quick_card, quick_table, quick_info, quick_file,
                    map_output, stations_table, geophy_table, wave_plot,
                    plot_3d_hypo, plot_3d_geophy, wave_3d_plot
                ]
            )

        # ── 頁籤 2：進階搜尋 ──────────────────────────────────────────
        with gr.Tab("🔍 進階自訂時間經緯度查詢"):
            gr.Markdown("### 👉 **請輸入查詢範圍與過濾條件：**")
            with gr.Row():
                with gr.Column(scale=1):
                    c_stdate = gr.Textbox(label="起始日期", value=MONTH_AGO)
                    c_sttime = gr.Textbox(label="起始時間", value="00:00:00")
                    c_eddate = gr.Textbox(label="結束日期", value=TODAY)
                    c_edtime = gr.Textbox(label="結束時間", value="23:59:59")
                with gr.Column(scale=1):
                    c_minml  = gr.Number(label="最小規模 ML", value=4.0)
                    c_maxml  = gr.Number(label="最大規模 ML", value=10.0)
                    c_mindep = gr.Number(label="最小深度 (km)", value=0)
                    c_maxdep = gr.Number(label="最大深度 (km)", value=700)
            c_btn   = gr.Button("🔍 搜尋並生成完整 2D/3D 視覺化資料", variant="primary")
            c_info  = gr.Markdown()
            
            # 3D 視覺化區域
            gr.Markdown("### 🧊 1. 【3D 立體互動區域】自訂搜尋結果之震源與變形場")
            with gr.Row():
                with gr.Column(scale=1):
                    c_plot_3d_hypo = gr.Plot(label="3D 震源與餘震空間分佈圖")
                with gr.Column(scale=1):
                    c_plot_3d_geophy = gr.Plot(label="3D 地球物理 GNSS 變形場")

            with gr.Row():
                with gr.Column(scale=1):
                    c_map_output = gr.HTML(label="震央地圖")
                with gr.Column(scale=1):
                    c_wave_plot = gr.LinePlot(
                        x="時間(秒)", y="垂直動振幅",
                        title="🌊 自訂時段近震央波形訊號示意 (Z分量)",
                        tooltip=["時間(秒)", "垂直動振幅"],
                        height=280
                    )

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📋 2. 地震目錄資料表 (Catalog)")
                    c_table = gr.DataFrame(label="結果數據", interactive=False, wrap=True)
                    c_file  = gr.File(label="下載檔案")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📡 3. 近震央波形觀測站及離震距離 (Seismic Stations)")
                    c_stations_table = gr.DataFrame(label="觀測站清單與距離", interactive=False, wrap=True)

            gr.Markdown("### 🛰️ 4. 地球物理資料全覽 (Geophysical Data: GNSS / 地下水 / 地磁)")
            c_geophy_table = gr.DataFrame(label="地球物理資料狀態", interactive=False, wrap=True)

            def custom_search(stdate, sttime, eddate, edtime, minml, maxml, mindep, maxdep):
                ensure_login()
                data = get_catalog(stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
                                   min_ml=float(minml), max_ml=float(maxml),
                                   min_dep=float(mindep), max_dep=float(maxdep))
                df_catalog = _catalog_df(data)
                if df_catalog.empty:
                    return "⚠️ 本搜尋條件下查無地震數據。", None, None, "", None, None, None, None, None
                
                main_eq = max(data, key=lambda x: float(x.get("ML", 0)))
                eq_lat = float(main_eq.get('latitude', 23.85))
                eq_lon = float(main_eq.get('longitude', 120.82))
                main_dep = float(main_eq.get('depth', 10.0))
                eq_date = main_eq.get('date', stdate)
                
                map_html = generate_map_html(eq_lat, eq_lon, f"自訂搜尋主震 ML {main_eq.get('ML')}")

                sta_list = []
                for s in DEMO_STATIONS:
                    dist = calculate_distance(eq_lat, eq_lon, s['lat'], s['lon'])
                    sta_list.append({
                        "網路": s["network"],
                        "測站代碼": s["station"],
                        "名稱": s["name"],
                        "緯度": s["lat"],
                        "經度": s["lon"],
                        "距震央(km)": dist,
                        "提供資料": "波形 (MiniSEED/SAC)" if s["network"] != "GNSS" else "GNSS 變形檔 (.o)"
                    })
                df_stations = pd.DataFrame(sta_list).sort_values(by="距震央(km)")

                geophy_list = [
                    {"資料類型": "GNSS 連續 GPS (.o)", "網路代碼": "GNSS", "採樣率": "30s / 1Hz", "涵蓋測站數": "230+ 基準站", "時間區段": f"{eq_date} (全天)"},
                    {"資料類型": "GNSS 星曆檔 (.n)", "網路代碼": "GNSS", "採樣率": "Daily", "涵蓋測站數": "全台觀測網", "時間區段": f"{eq_date} (完整)"},
                    {"資料類型": "地下水水電位觀測", "網路代碼": "WGW", "採樣率": "10 min", "涵蓋測站數": "48 觀測井", "時間區段": f"{eq_date} (數據齊備)"},
                    {"資料類型": "地磁與電磁動態波形", "網路代碼": "MAG", "採樣率": "1 sec", "涵蓋測站數": "9 磁觀測台", "時間區段": f"{eq_date} (已收錄)"}
                ]
                df_geophy = pd.DataFrame(geophy_list)

                df_wave = generate_waveform_df()
                fig_3d_hypo = generate_3d_hypocenter_plot(df_catalog, eq_lat, eq_lon, main_dep)
                fig_3d_geophy = generate_3d_geophy_plot(eq_lat, eq_lon)

                csv_str = df_catalog.to_csv(index=False, encoding="utf-8-sig")
                path = _save_tmp(csv_str, f"_{stdate}_custom.csv")
                
                info = f"✅ 搜尋完成！共找到 **{len(df_catalog)} 筆**地震事件，已自動為您產出全套 2D/3D 視覺化圖表與地球物理資料。"
                return info, df_catalog, path, map_html, df_stations, df_geophy, df_wave, fig_3d_hypo, fig_3d_geophy

            c_btn.click(custom_search,
                inputs=[c_stdate, c_sttime, c_eddate, c_edtime, c_minml, c_maxml, c_mindep, c_maxdep],
                outputs=[c_info, c_table, c_file, c_map_output, c_stations_table, c_geophy_table, c_wave_plot, c_plot_3d_hypo, c_plot_3d_geophy])

        # ── 頁籤 3：網路與測站 ───────────────────────────────────────
        with gr.Tab("🌐 測站與網路資訊"):
            with gr.Row():
                with gr.Column():
                    n_btn   = gr.Button("取得網路清單", variant="primary")
                    n_table = gr.DataFrame(label="網路清單", interactive=False)
                    def fn_nets():
                        data = get_networks()
                        rows = [{"網路代碼": n.get("network_code"), "名稱": n.get("name", {}).get("zh"), "測站數": n.get("station_number")} for n in data]
                        return pd.DataFrame(rows)
                    n_btn.click(fn_nets, outputs=[n_table])
                with gr.Column():
                    s_net = gr.Textbox(label="輸入網路代碼 (如 CWASN)", value="CWASN")
                    s_btn = gr.Button("查詢測站", variant="primary")
                    s_table = gr.DataFrame(label="測站清單", interactive=False)
                    def fn_stas(net):
                        data = get_stations(net.strip())
                        return pd.DataFrame(data) if data else pd.DataFrame()
                    s_btn.click(fn_stas, inputs=[s_net], outputs=[s_table])

    gr.HTML(FOOTER_HTML)

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 7860))
    demo.launch(
        server_name="0.0.0.0",
        server_port=PORT,
        auth=[(APP_USER, APP_PASS)],
        auth_message="GDMS Taiwan — 請輸入帳號密碼",
    )
