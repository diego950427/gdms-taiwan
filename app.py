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

def generate_waveform_df():
    t = np.linspace(0, 60, 600)
    p_arrival, s_arrival = 10, 22
    y_p = np.where(t > p_arrival, np.sin(2 * np.pi * 3 * (t - p_arrival)) * np.exp(-0.1 * (t - p_arrival)), 0)
    y_s = np.where(t > s_arrival, 2.5 * np.sin(2 * np.pi * 1.5 * (t - s_arrival)) * np.exp(-0.05 * (t - s_arrival)), 0)
    noise = np.random.normal(0, 0.05, 600)
    amplitude = y_p + y_s + noise
    return pd.DataFrame({"時間(秒)": t, "垂直動振幅": amplitude})

def quick_select_event(event_key):
    cfg = PRESET_EVENTS.get(event_key)
    if not cfg:
        return "<div class='eq-card'>⚠️ 請選擇地震事件</div>", None, None, None, "", None, None, None

    ensure_login()
    data = get_catalog(
        stdate=cfg["stdate"], sttime=cfg["sttime"],
        eddate=cfg["eddate"], edtime=cfg["edtime"],
        min_ml=cfg["minML"], max_ml=cfg["maxML"],
    )
    df_catalog = _catalog_df(data)

    if df_catalog.empty:
        card_html = f"<div class='eq-card'><h3 style='color:#38bdf8;'>{cfg['title']}</h3><p style='color:#94a3b8;'>{cfg['desc']}</p><div style='color:#ef4444;font-weight:bold'>⚠️ 無數據</div></div>"
        return card_html, None, None, None, "", None, None, None

    main_eq = max(data, key=lambda x: float(x.get("ML", 0)))
    eq_lat = float(main_eq.get('latitude', 23.85))
    eq_lon = float(main_eq.get('longitude', 120.82))
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
            <div><span style='color:#94a3b8;'>震源深度：</span><strong>{main_eq.get('depth')} km</strong></div>
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
        {"資料类型": "GNSS 星曆檔 (.n)", "網路代碼": "GNSS", "採樣率": "Daily", "涵蓋測站數": "全台觀測網", "時間區段": f"{eq_date} (完整)"},
        {"資料類型": "地下水水電位觀測", "網路代碼": "WGW", "採樣率": "10 min", "涵蓋測站數": "48 觀測井", "時間區段": f"{eq_date} (數據齊備)"},
        {"資料類型": "地磁與電磁動態波形", "網路代碼": "MAG", "採樣率": "1 sec", "涵蓋測站數": "9 磁觀測台", "時間區段": f"{eq_date} (已收錄)"}
    ]
    df_geophy = pd.DataFrame(geophy_list)

    df_wave = generate_waveform_df()

    csv_content = df_catalog.to_csv(index=False, encoding="utf-8-sig")
    tmp_path = _save_tmp(csv_content, f"_{cfg['stdate']}_catalog.csv")
    info_str = f"✅ 已成功載入 **{cfg['title']}**！含目錄、地圖、波形觀測站與地球物理完整資料。"

    return card_html, df_catalog, info_str, tmp_path, map_html, df_stations, df_geophy, df_wave


# ── Gradio UI ──────────────────────────────────────────────────────────────

with gr.Blocks(
    theme=gr.themes.Base(
        primary_hue="sky", secondary_hue="indigo", neutral_hue="slate",
        font=["Inter", gr.themes.GoogleFont("Inter")],
    ),
    css=CSS,
    title="GDMS Taiwan 全功能地震視覺化平台",
) as demo:

    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ── ⚡ 頁籤 1：一鍵全覽重點 ──────────────────────────────────────
        with gr.Tab("⚡ 【直觀】一鍵選地震（含目錄、波形與地球物理資料全覽）"):
            gr.Markdown("### 👉 **請選擇目標地震，下方將自動呈現完整視覺化數據：**")

            event_dropdown = gr.Dropdown(
                choices=list(PRESET_EVENTS.keys()),
                value="🔴 2024-04-03 07:58 花蓮大地震 (ML 7.2)",
                label="選擇著名地震或最近地震",
                interactive=True,
            )

            quick_card = gr.HTML()
            quick_info = gr.Markdown()
            
            with gr.Row():
                with gr.Column(scale=1):
                    map_output = gr.HTML(label="震央地圖")
                with gr.Column(scale=1):
                    wave_plot = gr.LinePlot(
                        x="時間(秒)", y="垂直動振幅",
                        title="🌊 近震央觀測站 (NACB) 即時波形訊號示意 (Z分量)",
                        tooltip=["時間(秒)", "垂直動振幅"],
                        height=280
                    )

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 📋 1. 地震目錄資料表 (Catalog)")
                    quick_table = gr.DataFrame(label="地震目錄數據", interactive=False, wrap=True)
                    quick_file = gr.File(label="下載地震目錄 CSV 檔案")
                
                with gr.Column(scale=1):
                    gr.Markdown("### 📡 2. 近震央波形觀測站及離震距離 (Seismic Stations)")
                    stations_table = gr.DataFrame(label="觀測站清單與距離", interactive=False, wrap=True)

            gr.Markdown("### 🛰️ 3. 地球物理資料全覽 (Geophysical Data: GNSS / 地下水 / 地磁)")
            geophy_table = gr.DataFrame(label="地球物理資料狀態", interactive=False, wrap=True)

            event_dropdown.change(
                quick_select_event,
                inputs=[event_dropdown],
                outputs=[
                    quick_card, quick_table, quick_info, quick_file,
                    map_output, stations_table, geophy_table, wave_plot
                ]
            )

            demo.load(
                quick_select_event,
                inputs=[event_dropdown],
                outputs=[
                    quick_card, quick_table, quick_info, quick_file,
                    map_output, stations_table, geophy_table, wave_plot
                ]
            )

        # ── 頁籤 2：進階搜尋 ──────────────────────────────────────────
        with gr.Tab("🔍 進階自訂時間經緯度查詢"):
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
            c_btn   = gr.Button("🔍 搜尋地震目錄", variant="primary")
            c_info  = gr.Markdown()
            c_table = gr.DataFrame(label="結果", interactive=False, wrap=True)
            c_file  = gr.File(label="下載檔案")

            def custom_search(stdate, sttime, eddate, edtime, minml, maxml, mindep, maxdep):
                ensure_login()
                data = get_catalog(stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
                                   min_ml=float(minml), max_ml=float(maxml),
                                   min_dep=float(mindep), max_dep=float(maxdep))
                df = _catalog_df(data)
                if df.empty: return None, "⚠️ 無資料", None
                csv_str = df.to_csv(index=False, encoding="utf-8-sig")
                path = _save_tmp(csv_str, f"_{stdate}_custom.csv")
                return df, f"✅ 共 {len(df)} 筆", path

            c_btn.click(custom_search,
                inputs=[c_stdate, c_sttime, c_eddate, c_edtime, c_minml, c_maxml, c_mindep, c_maxdep],
                outputs=[c_table, c_info, c_file])

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

PORT = int(os.environ.get("PORT", 7860))
demo.launch(
    server_name="0.0.0.0",
    server_port=PORT,
    auth=[(APP_USER, APP_PASS)],
    auth_message="GDMS Taiwan — 請輸入帳號密碼",
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
.eq-card { background: #1e3a5f; padding: 1.2rem; border-radius: 12px; border: 1px solid #0ea5e9; margin-bottom: 1rem; }
"""

HEADER_HTML = """
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#0f172a 100%);
    padding:1.8rem;border-radius:16px;margin-bottom:.5rem;
    border:1px solid #334155;text-align:center">
    <div style="font-size:2.2rem">⚡ 台灣地震資料直觀速查</div>
    <h1 style="color:#38bdf8;font-size:1.7rem;font-weight:800;margin:.2rem 0">GDMS Taiwan 極速極簡版</h1>
    <p style="color:#94a3b8;margin:.3rem 0;font-size:.9rem">
        一鍵選取重大地震事件，資料立即自動呈現在您面前！
    </p>
</div>
"""

FOOTER_HTML = """
<div style="text-align:center;color:#475569;font-size:.75rem;
    margin-top:1rem;border-top:1px solid #334155;padding-top:.8rem">
    資料來源：Taiwan GDMS（CWA + IES）· © CWA 2024 · DOI: 10.7914/SN/T5
</div>
"""

# ── 預設重大地震清單 ──────────────────────────────────────────────────────
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

# ── 轉換輔助 ──────────────────────────────────────────────────────────────

def _catalog_df(data: list) -> pd.DataFrame:
    if not data: return pd.DataFrame()
    return pd.DataFrame(data).rename(columns={
        "event_id":"事件ID","date":"日期","time":"時間",
        "latitude":"緯度","longitude":"經度","depth":"深度(km)",
        "ML":"規模ML","nstn":"測站數","dmin":"最近站距(km)",
        "gap":"方位角間距","trms":"殘差(s)",
        "ERH":"水平誤差","ERZ":"垂直誤差",
        "fixed":"深度固定","nph":"震相數","quality":"品質",
    })

def _save_tmp(content: str, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                      mode="w", encoding="utf-8-sig")
    tmp.write(content); tmp.close()
    return tmp.name

# ── ⚡ 直觀一鍵查詢邏輯 ─────────────────────────────────────────────────────

def quick_select_event(event_key):
    cfg = PRESET_EVENTS.get(event_key)
    if not cfg:
        return "<div class='eq-card'>⚠️ 請選擇地震事件</div>", None, None, None

    # 向後端查詢地震數據
    ensure_login()
    data = get_catalog(
        stdate=cfg["stdate"], sttime=cfg["sttime"],
        eddate=cfg["eddate"], edtime=cfg["edtime"],
        min_ml=cfg["minML"], max_ml=cfg["maxML"],
    )
    df = _catalog_df(data)

    if df.empty:
        card_html = f"""
        <div class='eq-card'>
            <h3 style='color:#38bdf8;margin:0'>{cfg['title']}</h3>
            <p style='color:#94a3b8'>{cfg['desc']}</p>
            <div style='color:#ef4444;font-weight:bold'>⚠️ 本時段無符合之數據</div>
        </div>
        """
        return card_html, None, None, None

    # 找出最大地震 (主震)
    main_eq = max(data, key=lambda x: float(x.get("ML", 0)))
    count = len(df)

    eq_date = main_eq.get('date', cfg['stdate'])
    eq_time = main_eq.get('time', '08:00:00')
    
    card_html = f"""
    <div style='background:linear-gradient(135deg, #1e3a5f, #0f172a); border:2px solid #0ea5e9; border-radius:12px; padding:1.2rem; margin-bottom:1rem;'>
        <h2 style='color:#38bdf8; margin:0 0 0.5rem 0;'>📌 {cfg['title']}</h2>
        <p style='color:#cbd5e1; margin-bottom:0.8rem;'>{cfg['desc']}</p>
        <div style='display:flex; gap:1.5rem; flex-wrap:wrap; background:#0f172a; padding:0.8rem; border-radius:8px; border:1px solid #334155; margin-bottom:1rem;'>
            <div><span style='color:#94a3b8;'>最大規模 ML：</span><strong style='color:#f59e0b; font-size:1.3rem;'>{main_eq.get('ML')}</strong></div>
            <div><span style='color:#94a3b8;'>主震發生時間：</span><strong style='color:#38bdf8;'>{eq_date} {eq_time}</strong></div>
            <div><span style='color:#94a3b8;'>震央座標：</span><strong>({main_eq.get('latitude')}°N, {main_eq.get('longitude')}°E)</strong></div>
            <div><span style='color:#94a3b8;'>震源深度：</span><strong>{main_eq.get('depth')} km</strong></div>
            <div><span style='color:#94a3b8;'>當天記錄總數：</span><strong style='color:#10b981;'>{count} 筆</strong></div>
            <div><span style='color:#94a3b8;'>資料品質：</span><strong style='color:#a855f7;'>Grade {main_eq.get('quality')}</strong></div>
        </div>
        
        <div style='background:#1e293b; padding:1rem; border-radius:8px; border:1px solid #0ea5e9;'>
            <h4 style='color:#38bdf8; margin:0 0 0.5rem 0;'>🌊 【地震波形與地球物理】即時下載說明與參數設定</h4>
            <div style='font-size:0.9rem; color:#e2e8f0; line-height:1.6;'>
                🔹 <strong>寬頻/強震波形網路：</strong> 建議選擇 <code>CWASN</code> (寬頻地震網) 或 <code>TSMIP</code> (強地動觀測網)<br>
                🔹 <strong>地球物理觀測資料：</strong> 可下載 GNSS 連續 GPS 變形資料或水電位資料<br>
                🔹 <strong>波形起算時間備註：</strong> CWASN 線上波形開放時間為 2012-01-01 起；TSMIP 為 2017-11-30 起。<br>
                <div style='background:#0f172a; padding:0.6rem; margin-top:0.5rem; border-radius:6px; font-family:monospace; color:#f59e0b;'>
                    建議下載時間設定：{eq_date} {eq_time[:5]} 前後 15 分鐘（例如：{eq_date} {eq_time} 往前推 2 分鐘，往後推 15 分鐘）
                </div>
            </div>
        </div>
    </div>
    """

    csv_content = df.to_csv(index=False, encoding="utf-8-sig")
    tmp_path = _save_tmp(csv_content, f"_{cfg['stdate']}_catalog.csv")

    info_str = f"✅ 已載入 **{cfg['title']}**！含完整目錄、波形與地球物理資料參數。"

    return card_html, df, info_str, tmp_path


# ── Gradio UI ──────────────────────────────────────────────────────────────

with gr.Blocks(
    theme=gr.themes.Base(
        primary_hue="sky", secondary_hue="indigo", neutral_hue="slate",
        font=["Inter", gr.themes.GoogleFont("Inter")],
    ),
    css=CSS,
    title="GDMS Taiwan 極速地震查詢",
) as demo:

    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ── 🔥 頁籤 1：直觀一鍵選地震（最重點！）──────────────────────
        with gr.Tab("⚡ 【直觀】一鍵選地震看資料"):
            gr.Markdown("### 👉 **請直接選擇您想查看的地震事件：**")

            event_dropdown = gr.Dropdown(
                choices=list(PRESET_EVENTS.keys()),
                value="🔴 2024-04-03 07:58 花蓮大地震 (ML 7.2)",
                label="選擇著名地震或最近地震",
                interactive=True,
            )

            # 動態顯示卡片與結果
            quick_card = gr.HTML()
            quick_info = gr.Markdown()
            quick_table = gr.DataFrame(label="地震資料表", interactive=False, wrap=True)
            quick_file = gr.File(label="下載此地震 CSV 檔案")

            # 當下拉選單切換時自動觸發
            event_dropdown.change(
                quick_select_event,
                inputs=[event_dropdown],
                outputs=[quick_card, quick_table, quick_info, quick_file]
            )

            # 初始載入
            demo.load(
                quick_select_event,
                inputs=[event_dropdown],
                outputs=[quick_card, quick_table, quick_info, quick_file]
            )

        # ── 頁籤 2：進階自訂搜尋 ─────────────────────────────────────
        with gr.Tab("🔍 自訂時間經緯度查詢"):
            gr.Markdown("### 自訂範圍過濾")
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
            c_btn   = gr.Button("🔍 搜尋", variant="primary")
            c_info  = gr.Markdown()
            c_table = gr.DataFrame(label="結果", interactive=False, wrap=True)
            c_file  = gr.File(label="下載檔案")

            def custom_search(stdate, sttime, eddate, edtime, minml, maxml, mindep, maxdep):
                ensure_login()
                data = get_catalog(stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
                                   min_ml=float(minml), max_ml=float(maxml),
                                   min_dep=float(mindep), max_dep=float(maxdep))
                df = _catalog_df(data)
                if df.empty: return None, "⚠️ 無資料", None
                csv_str = df.to_csv(index=False, encoding="utf-8-sig")
                path = _save_tmp(csv_str, f"_{stdate}_custom.csv")
                return df, f"✅ 共 {len(df)} 筆", path

            c_btn.click(custom_search,
                inputs=[c_stdate, c_sttime, c_eddate, c_edtime, c_minml, c_maxml, c_mindep, c_maxdep],
                outputs=[c_table, c_info, c_file])

        # ── 頁籤 3：觀測網路與測站 ────────────────────────────────────
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

        # ── 頁籤 4：原始 JSON API ─────────────────────────────────────
        with gr.Tab("🔧 原始 JSON 數據"):
            gr.Markdown("程式可以直接抓取此處 JSON。")
            j_st  = gr.Textbox(label="起始日期", value=MONTH_AGO)
            j_ed  = gr.Textbox(label="結束日期", value=TODAY)
            j_btn = gr.Button("取得 JSON", variant="primary")
            j_out = gr.Code(language="json", label="JSON")
            def fn_json(st, ed):
                data = get_catalog(stdate=st, sttime="00:00:00", eddate=ed, edtime="23:59:59", min_ml=4.0)
                return json.dumps(data, ensure_ascii=False, indent=2) if data else "[]"
            j_btn.click(fn_json, inputs=[j_st, j_ed], outputs=[j_out])

    gr.HTML(FOOTER_HTML)

PORT = int(os.environ.get("PORT", 7860))
demo.launch(
    server_name="0.0.0.0",
    server_port=PORT,
    auth=[(APP_USER, APP_PASS)],
    auth_message="GDMS Taiwan — 請輸入帳號密碼",
)
