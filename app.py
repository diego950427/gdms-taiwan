"""
GDMS Taiwan — 完整 Gradio Web App
功能：地震目錄 / 多站波形 / 連續波形 / 儀器響應 / 地球物理 / 下載清單
安全：帳密存在環境變數；網頁加入登入保護
"""

import json, os, sys, tempfile
import gradio as gr
import pandas as pd
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

# ── 網頁登入密碼（從環境變數讀取，預設 gdms2024）─────────────────────────
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
label { color: #94a3b8 !important; font-size:.82rem !important; }
.tabs > .tab-nav > button { color:#64748b !important; border-radius:8px 8px 0 0 !important; }
.tabs > .tab-nav > button.selected { color:#38bdf8 !important; border-bottom:2px solid #38bdf8 !important; background:#1e293b !important; }
textarea, input[type=text], input[type=number] { background:#0f172a !important; color:#e2e8f0 !important; border-color:#334155 !important; }
.dataframe table { background:#0f172a !important; }
.dataframe th { background:#1e3a5f !important; color:#38bdf8 !important; }
.dataframe td { color:#e2e8f0 !important; border-color:#334155 !important; }
"""

HEADER_HTML = """
<div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#0f172a 100%);
    padding:1.8rem;border-radius:16px;margin-bottom:.5rem;
    border:1px solid #334155;text-align:center">
    <div style="font-size:2.2rem">🌏</div>
    <h1 style="color:#38bdf8;font-size:1.7rem;font-weight:800;margin:.2rem 0">GDMS Taiwan</h1>
    <p style="color:#94a3b8;margin:.3rem 0;font-size:.85rem">
        台灣地震與地球物理資料管理系統<br>
        <small>中央氣象署 CWA + 中研院地球所 IES</small>
    </p>
    <div style="margin-top:.6rem;display:flex;gap:.35rem;justify-content:center;flex-wrap:wrap;font-size:.7rem">
        <span style="background:#0ea5e9;color:#fff;padding:.15rem .6rem;border-radius:999px">📡 CWASN 152站</span>
        <span style="background:#6366f1;color:#fff;padding:.15rem .6rem;border-radius:999px">📡 TSMIP 533站</span>
        <span style="background:#10b981;color:#fff;padding:.15rem .6rem;border-radius:999px">🛰 GNSS 191站</span>
        <span style="background:#ef4444;color:#fff;padding:.15rem .6rem;border-radius:999px">🧲 MAGNET 20站</span>
        <span style="background:#f59e0b;color:#fff;padding:.15rem .6rem;border-radius:999px">💧 GW 6站</span>
        <span style="background:#8b5cf6;color:#fff;padding:.15rem .6rem;border-radius:999px">📅 資料始於 1940年</span>
    </div>
</div>
"""

FOOTER_HTML = """
<div style="text-align:center;color:#475569;font-size:.73rem;
    margin-top:1rem;border-top:1px solid #334155;padding-top:.8rem">
    資料來源：Taiwan GDMS（CWA + IES）· © CWA 2024 · DOI:
    <a href="https://doi.org/10.7914/SN/T5" style="color:#38bdf8">10.7914/SN/T5</a>
</div>
"""

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

def _networks_df(data: list) -> pd.DataFrame:
    if not data: return pd.DataFrame()
    rows = []
    for n in data:
        nm = n.get("name", {})
        rows.append({
            "網路代碼": n.get("network_code",""),
            "類型":     n.get("type",""),
            "名稱":     nm.get("zh","") if isinstance(nm,dict) else str(nm),
            "測站數":   n.get("station_number",""),
            "資料起始": n.get("release_start",""),
            "最新資料": n.get("latest",""),
        })
    return pd.DataFrame(rows)

def _save_tmp(content: str, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                      mode="w", encoding="utf-8-sig")
    tmp.write(content); tmp.close()
    return tmp.name

# ── Tab 函式 ──────────────────────────────────────────────────────────────

def fn_status():
    try:
        ok = ensure_login()
        if not ok:
            return "## ❌ 連線失敗\n\nGDMS 帳號無法登入，請確認環境變數設定。"
        nets = get_networks()
        total = sum(n.get("station_number",0) for n in nets)
        latest = max((n.get("latest","") for n in nets), default="—")
        msg = (
            f"## ✅ 連線正常\n\n"
            f"| 項目 | 值 |\n|---|---|\n"
            f"| 登入狀態 | ✅ 成功 |\n"
            f"| 觀測網路數 | {len(nets)} 個 |\n"
            f"| 總測站數 | {total} 站 |\n"
            f"| 最新資料 | {latest} |\n\n### 觀測網路\n"
        )
        for n in nets:
            nm = n.get("name",{})
            zh = nm.get("zh","") if isinstance(nm,dict) else ""
            msg += f"- **{n.get('network_code')}** — {zh} （{n.get('station_number')} 站，至 {n.get('latest')}）\n"
        return msg
    except Exception as e:
        return f"## ❌ 錯誤\n```\n{e}\n```"

def fn_catalog(stdate, sttime, eddate, edtime,
               min_ml, max_ml, min_dep, max_dep,
               min_lon, max_lon, min_lat, max_lat,
               use_circle, cir_lon, cir_lat, cir_rad, fmt):
    try:
        kw = dict(stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
                  min_ml=float(min_ml), max_ml=float(max_ml),
                  min_dep=float(min_dep), max_dep=float(max_dep))
        if use_circle:
            kw.update(cir_lon=float(cir_lon), cir_lat=float(cir_lat), cir_rad=float(cir_rad))
        else:
            kw.update(min_lon=float(min_lon), max_lon=float(max_lon),
                      min_lat=float(min_lat), max_lat=float(max_lat))
        data = get_catalog(**kw)
        df = _catalog_df(data)
        if df.empty:
            return None, "⚠️ 查無資料（0 筆）", None
        ml_num = pd.to_numeric(df["規模ML"], errors="coerce")
        dep_num = pd.to_numeric(df["深度(km)"], errors="coerce")
        info = (
            f"✅ 共 **{len(df)} 筆**\n\n"
            f"| 期間 | {df['日期'].min()} ～ {df['日期'].max()} |\n"
            f"|------|------|\n"
            f"| 規模 | {ml_num.min():.2f} ～ {ml_num.max():.2f} |\n"
            f"| 深度 | {dep_num.min():.1f} ～ {dep_num.max():.1f} km |"
        )
        if fmt == "CSV":
            content, ext = df.to_csv(index=False, encoding="utf-8-sig"), "csv"
        else:
            content, ext = df.to_json(orient="records", force_ascii=False, indent=2), "json"
        return df, info, _save_tmp(content, f"_gdms_{stdate}_{eddate}.{ext}")
    except Exception as e:
        return None, f"❌ 錯誤：{e}", None

def fn_networks():
    try:
        data = get_networks()
        df = _networks_df(data)
        if df.empty: return None, "⚠️ 無資料"
        return df, f"✅ 共 **{len(df)} 個**觀測網路，總測站 **{df['測站數'].sum()}** 站"
    except Exception as e:
        return None, f"❌ {e}"

def fn_stations(network):
    try:
        data = get_stations(network.strip() if network else "")
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if df.empty: return None, f"⚠️ [{network}] 無資料"
        return df, f"✅ **{network}** 共 **{len(df)} 站**"
    except Exception as e:
        return None, f"❌ {e}"

def fn_channels(network, station, location):
    try:
        data = get_channels(
            network.strip() if network else "",
            station.strip() if station else "",
            location.strip() if location else "",
        )
        df = pd.DataFrame(data) if data else pd.DataFrame()
        if df.empty: return None, "⚠️ 無通道資料"
        return df, f"✅ 共 **{len(df)} 個**通道"
    except Exception as e:
        return None, f"❌ {e}"

def fn_eq_download(stations, sttime, edtime, network, location, channel, output, label, all_sta):
    try:
        result = submit_eq_download(
            stations=stations, sttime=sttime, edtime=edtime,
            network=network, location=location, channel=channel,
            output=output, label=label, all_station=all_sta,
        )
        if result.get("success") or result.get("status") == "success":
            return f"✅ 送出成功！\n\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```\n\n請至「📥 下載清單」頁面查看進度。"
        else:
            msg = result.get("message","") or result.get("msg","") or json.dumps(result, ensure_ascii=False)
            return f"⚠️ 回應：\n\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"
    except Exception as e:
        return f"❌ 錯誤：{e}"

def fn_resp_download(stations, sttime, edtime, network, location, channel, label):
    try:
        result = submit_resp_download(
            stations=stations, sttime=sttime, edtime=edtime,
            network=network, location=location, channel=channel, label=label,
        )
        return f"回應：\n\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```"
    except Exception as e:
        return f"❌ 錯誤：{e}"

def fn_geophy_download(stations, sttime, edtime, network, gnss_type, label, all_sta):
    try:
        result = submit_geophy_download(
            stations=stations, sttime=sttime, edtime=edtime,
            network=network, gnss_type=gnss_type, label=label, all_station=all_sta,
        )
        return f"回應：\n\n```json\n{json.dumps(result, ensure_ascii=False, indent=2)}\n```\n\n請至「📥 下載清單」查看進度。"
    except Exception as e:
        return f"❌ 錯誤：{e}"

def fn_download_list():
    try:
        data = get_download_list()
        if not data:
            return None, "⚠️ 目前無下載記錄，或頁面結構變更"
        df = pd.DataFrame(data)
        return df, f"✅ 共 **{len(df)} 筆**下載記錄"
    except Exception as e:
        return None, f"❌ {e}"

def raw_catalog(stdate, sttime, eddate, edtime, min_ml, max_ml,
                min_lon, max_lon, min_lat, max_lat):
    try:
        data = get_catalog(
            stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
            min_ml=float(min_ml), max_ml=float(max_ml),
            min_lon=float(min_lon), max_lon=float(max_lon),
            min_lat=float(min_lat), max_lat=float(max_lat),
        )
        return json.dumps(data, ensure_ascii=False, indent=2) if data else "[]"
    except Exception as e:
        return f"Error: {e}"

def raw_networks():
    try:
        return json.dumps(get_networks(), ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"

def raw_stations(network):
    try:
        return json.dumps(get_stations(network.strip() if network else ""), ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"

def raw_channels(network, station, location):
    try:
        return json.dumps(get_channels(
            network.strip() if network else "",
            station.strip() if station else "",
            location.strip() if location else "",
        ), ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error: {e}"

# ── Gradio UI ──────────────────────────────────────────────────────────────

with gr.Blocks(
    theme=gr.themes.Base(
        primary_hue="sky", secondary_hue="indigo", neutral_hue="slate",
        font=["Inter", gr.themes.GoogleFont("Inter")],
    ),
    css=CSS,
    title="GDMS Taiwan 地震資料查詢",
) as demo:

    gr.HTML(HEADER_HTML)

    with gr.Tabs():

        # ── Tab 1 系統狀態 ─────────────────────────────────────────────
        with gr.Tab("🔌 系統狀態"):
            st_btn = gr.Button("檢查 GDMS 連線狀態", variant="primary")
            st_out = gr.Markdown()
            st_btn.click(fn_status, outputs=st_out)
            demo.load(fn_status, outputs=st_out)

        # ── Tab 2 地震目錄 ─────────────────────────────────────────────
        with gr.Tab("📋 地震目錄"):
            gr.Markdown("### 查詢條件（資料範圍：1940 年至今）")
            with gr.Row():
                with gr.Column(scale=1):
                    c_stdate = gr.Textbox(label="起始日期", value=MONTH_AGO, placeholder="1973-01-01")
                    c_sttime = gr.Textbox(label="起始時間", value="00:00:00")
                    c_eddate = gr.Textbox(label="結束日期", value=TODAY)
                    c_edtime = gr.Textbox(label="結束時間", value="23:59:59")
                    c_fmt    = gr.Radio(["CSV","JSON"], label="下載格式", value="CSV")
                with gr.Column(scale=1):
                    c_minml  = gr.Number(label="最小規模 ML", value=4.0, minimum=-1, maximum=10)
                    c_maxml  = gr.Number(label="最大規模 ML", value=10.0, minimum=-1, maximum=10)
                    c_mindep = gr.Number(label="最小深度 (km)", value=0, minimum=0, maximum=700)
                    c_maxdep = gr.Number(label="最大深度 (km)", value=700, minimum=0, maximum=700)
                with gr.Column(scale=1):
                    c_circle = gr.Checkbox(label="使用圓形搜尋（否則為矩形）", value=False)
                    with gr.Group():
                        gr.Markdown("**矩形範圍**")
                        c_minlon = gr.Number(label="最小經度", value=118.0)
                        c_maxlon = gr.Number(label="最大經度", value=126.0)
                        c_minlat = gr.Number(label="最小緯度", value=20.0)
                        c_maxlat = gr.Number(label="最大緯度", value=27.0)
                    with gr.Group():
                        gr.Markdown("**圓形範圍**")
                        c_clon = gr.Number(label="圓心經度", value=121.0)
                        c_clat = gr.Number(label="圓心緯度", value=23.5)
                        c_crad = gr.Number(label="半徑 (km)", value=200)
            c_btn   = gr.Button("🔍 查詢地震目錄", variant="primary", size="lg")
            c_info  = gr.Markdown()
            c_table = gr.DataFrame(label="查詢結果", interactive=False, wrap=True)
            c_file  = gr.File(label="下載檔案")
            c_btn.click(fn_catalog,
                inputs=[c_stdate,c_sttime,c_eddate,c_edtime,
                        c_minml,c_maxml,c_mindep,c_maxdep,
                        c_minlon,c_maxlon,c_minlat,c_maxlat,
                        c_circle,c_clon,c_clat,c_crad,c_fmt],
                outputs=[c_table,c_info,c_file])

        # ── Tab 3 觀測網路 ─────────────────────────────────────────────
        with gr.Tab("🌐 觀測網路"):
            n_btn   = gr.Button("取得觀測網路清單", variant="primary")
            n_info  = gr.Markdown()
            n_table = gr.DataFrame(label="網路清單", interactive=False)
            n_btn.click(fn_networks, outputs=[n_table,n_info])
            demo.load(fn_networks, outputs=[n_table,n_info])

        # ── Tab 4 測站清單 ─────────────────────────────────────────────
        with gr.Tab("📍 測站清單"):
            gr.Markdown("網路代碼：`CWASN` / `TSMIP` / `GNSS` / `MAGNET` / `GW` / `GNSS_IES` / `GNSS_ETEC`")
            with gr.Row():
                s_net = gr.Textbox(label="網路代碼", value="CWASN")
                s_btn = gr.Button("查詢測站", variant="primary")
            s_info  = gr.Markdown()
            s_table = gr.DataFrame(label="測站清單", interactive=False)
            s_btn.click(fn_stations, inputs=[s_net], outputs=[s_table,s_info])

        # ── Tab 5 通道清單 ─────────────────────────────────────────────
        with gr.Tab("📡 通道清單"):
            gr.Markdown("查詢指定測站的波形通道（HHZ、HHE、HHN、EHZ 等）")
            with gr.Row():
                ch_net = gr.Textbox(label="網路代碼", placeholder="CWASN")
                ch_sta = gr.Textbox(label="測站代碼", placeholder="NACB")
                ch_loc = gr.Textbox(label="位置代碼", placeholder="*")
                ch_btn = gr.Button("查詢通道", variant="primary")
            ch_info  = gr.Markdown()
            ch_table = gr.DataFrame(label="通道清單", interactive=False)
            ch_btn.click(fn_channels, inputs=[ch_net,ch_sta,ch_loc], outputs=[ch_table,ch_info])

        # ── Tab 6 多站波形下載 ─────────────────────────────────────────
        with gr.Tab("🌊 波形下載"):
            gr.Markdown("""
### 多站波形資料下載（CWASN / TSMIP）
送出請求後，請至「📥 下載清單」查看進度並取得檔案。
> 時間格式：`YYYY-MM-DD HH:MM:SS`
            """)
            with gr.Row():
                with gr.Column():
                    eq_net    = gr.Textbox(label="網路代碼", value="CWASN")
                    eq_sta    = gr.Textbox(label="測站代碼（逗號分隔）", placeholder="NACB,WGKF,YULB")
                    eq_allsta = gr.Checkbox(label="全部測站", value=False)
                with gr.Column():
                    eq_st   = gr.Textbox(label="起始時間", placeholder="2024-04-03 07:58:00")
                    eq_ed   = gr.Textbox(label="結束時間", placeholder="2024-04-03 08:10:00")
                    eq_loc  = gr.Textbox(label="位置代碼", value="*")
                    eq_ch   = gr.Textbox(label="通道代碼", placeholder="HH* (留空=全部)")
                with gr.Column():
                    eq_fmt  = gr.Radio(
                        ["MiniSEED","SAC binary","ASCII: 1 column format","ASCII: 2 column format"],
                        label="輸出格式", value="MiniSEED")
                    eq_lbl  = gr.Textbox(label="標籤名稱", value="GDMSData")
            eq_btn = gr.Button("📤 送出波形下載請求", variant="primary", size="lg")
            eq_out = gr.Markdown()
            eq_btn.click(fn_eq_download,
                inputs=[eq_sta,eq_st,eq_ed,eq_net,eq_loc,eq_ch,eq_fmt,eq_lbl,eq_allsta],
                outputs=eq_out)

        # ── Tab 7 儀器響應 ─────────────────────────────────────────────
        with gr.Tab("⚙️ 儀器響應"):
            gr.Markdown("### 儀器響應資料下載（Instrument Response）")
            with gr.Row():
                with gr.Column():
                    rp_net = gr.Textbox(label="網路代碼", value="CWASN")
                    rp_sta = gr.Textbox(label="測站代碼（逗號分隔）", placeholder="NACB,WGKF")
                with gr.Column():
                    rp_st  = gr.Textbox(label="起始時間", placeholder="2024-04-03 00:00:00")
                    rp_ed  = gr.Textbox(label="結束時間", placeholder="2024-04-03 23:59:59")
                    rp_loc = gr.Textbox(label="位置代碼", value="*")
                    rp_ch  = gr.Textbox(label="通道代碼", placeholder="HH*")
                    rp_lbl = gr.Textbox(label="標籤名稱", value="GDMSData")
            rp_btn = gr.Button("📤 送出儀器響應下載請求", variant="primary")
            rp_out = gr.Markdown()
            rp_btn.click(fn_resp_download,
                inputs=[rp_sta,rp_st,rp_ed,rp_net,rp_loc,rp_ch,rp_lbl],
                outputs=rp_out)

        # ── Tab 8 地球物理資料 ─────────────────────────────────────────
        with gr.Tab("🛰 地球物理"):
            gr.Markdown("""
### 地球物理資料下載
支援：GNSS 衛星定位、地磁（MAGNET）、地下水（GW）
            """)
            with gr.Row():
                with gr.Column():
                    gp_net  = gr.Dropdown(
                        choices=["GNSS","GNSS_IES","GNSS_ETEC","MAGNET","GW"],
                        label="網路代碼", value="GNSS")
                    gp_sta  = gr.Textbox(label="測站代碼（逗號分隔）", placeholder="TWTF,YMSM")
                    gp_all  = gr.Checkbox(label="全部測站", value=False)
                with gr.Column():
                    gp_st   = gr.Textbox(label="起始時間", placeholder="2024-04-01 00:00:00")
                    gp_ed   = gr.Textbox(label="結束時間", placeholder="2024-04-01 23:59:59")
                    gp_type = gr.Radio(
                        ["Observation file (.o)","Navigation file (.n)"],
                        label="GNSS 檔案類型", value="Observation file (.o)")
                    gp_lbl  = gr.Textbox(label="標籤名稱", value="GDMSData")
            gp_btn = gr.Button("📤 送出地球物理資料下載請求", variant="primary")
            gp_out = gr.Markdown()
            gp_btn.click(fn_geophy_download,
                inputs=[gp_sta,gp_st,gp_ed,gp_net,gp_type,gp_lbl,gp_all],
                outputs=gp_out)

        # ── Tab 9 下載清單 ─────────────────────────────────────────────
        with gr.Tab("📥 下載清單"):
            gr.Markdown("### 用戶下載任務清單（波形 / 地球物理資料）")
            dl_btn   = gr.Button("🔄 重新整理下載清單", variant="primary")
            dl_info  = gr.Markdown()
            dl_table = gr.DataFrame(label="下載清單", interactive=False)
            dl_btn.click(fn_download_list, outputs=[dl_table,dl_info])
            demo.load(fn_download_list, outputs=[dl_table,dl_info])

        # ── Tab 10 原始 JSON ───────────────────────────────────────────
        with gr.Tab("🔧 原始 JSON"):
            gr.Markdown("直接取得後端 JSON 回應，方便程式爬取。")

            with gr.Accordion("📋 地震目錄 JSON", open=True):
                with gr.Row():
                    j_st  = gr.Textbox(label="起始日期", value=MONTH_AGO)
                    j_st2 = gr.Textbox(label="起始時間", value="00:00:00")
                    j_ed  = gr.Textbox(label="結束日期", value=TODAY)
                    j_ed2 = gr.Textbox(label="結束時間", value="23:59:59")
                    j_mml = gr.Number(label="最小規模", value=4.0)
                    j_xml = gr.Number(label="最大規模", value=10.0)
                with gr.Row():
                    j_mlon = gr.Number(label="最小經度", value=118.0)
                    j_xlon = gr.Number(label="最大經度", value=126.0)
                    j_mlat = gr.Number(label="最小緯度", value=20.0)
                    j_xlat = gr.Number(label="最大緯度", value=27.0)
                j_btn = gr.Button("取得目錄 JSON", variant="primary")
                j_out = gr.Code(language="json", label="JSON 回應")
                j_btn.click(raw_catalog,
                    inputs=[j_st,j_st2,j_ed,j_ed2,j_mml,j_xml,j_mlon,j_xlon,j_mlat,j_xlat],
                    outputs=j_out)

            with gr.Accordion("🌐 觀測網路 JSON", open=False):
                rn_btn = gr.Button("取得網路 JSON", variant="primary")
                rn_out = gr.Code(language="json", label="JSON 回應")
                rn_btn.click(raw_networks, outputs=rn_out)

            with gr.Accordion("📍 測站清單 JSON", open=False):
                rs_net = gr.Textbox(label="網路代碼", value="CWASN")
                rs_btn = gr.Button("取得測站 JSON", variant="primary")
                rs_out = gr.Code(language="json", label="JSON 回應")
                rs_btn.click(raw_stations, inputs=[rs_net], outputs=rs_out)

            with gr.Accordion("📡 通道清單 JSON", open=False):
                with gr.Row():
                    rc_net = gr.Textbox(label="網路代碼", placeholder="CWASN")
                    rc_sta = gr.Textbox(label="測站代碼", placeholder="NACB")
                    rc_loc = gr.Textbox(label="位置代碼", placeholder="*")
                rc_btn = gr.Button("取得通道 JSON", variant="primary")
                rc_out = gr.Code(language="json", label="JSON 回應")
                rc_btn.click(raw_channels, inputs=[rc_net,rc_sta,rc_loc], outputs=rc_out)

        # ── Tab 11 說明 ────────────────────────────────────────────────
        with gr.Tab("📖 說明"):
            gr.Markdown("""
## GDMS Taiwan 資料說明

### 可用資料類型
| 類型 | 說明 | 格式 |
|------|------|------|
| 地震目錄 | 1940 年至今，ML≥4 約 14,000 筆 | JSON / CSV |
| 多站波形 | CWASN 152站 / TSMIP 533站 | MiniSEED / SAC |
| 連續波形 | 同上 | MiniSEED |
| 儀器響應 | 各站儀器頻率響應 | RESP / StationXML |
| GNSS | CWA 191站 / IES 73站 | Rinex .o .n |
| 地磁 | 20 站 | 原始格式 |
| 地下水 | 6 站 | 原始格式 |

### 地震目錄欄位
| 欄位 | 說明 |
|------|------|
| event_id | 事件唯一識別碼 |
| date / time | 發生日期時間（UTC+8） |
| latitude / longitude | 震央座標（WGS84） |
| depth | 震源深度（km） |
| ML | 芮氏規模 |
| quality | 品質 A > B > C > D |

### 使用說明
1. **地震目錄** → 直接查詢並下載 CSV/JSON
2. **波形/地球物理** → 送出請求後至「📥 下載清單」取得檔案連結
3. **原始 JSON** → 程式直接爬取用

資料來源：[gdms.cwa.gov.tw](https://gdms.cwa.gov.tw) · DOI：[10.7914/SN/T5](https://doi.org/10.7914/SN/T5)
            """)

    gr.HTML(FOOTER_HTML)

# ── 啟動（支援 Render PORT 環境變數 + 網頁登入保護）──────────────────────
PORT = int(os.environ.get("PORT", 7860))
demo.launch(
    server_name="0.0.0.0",
    server_port=PORT,
    share=False,
    show_error=True,
    auth=[(APP_USER, APP_PASS)],          # 網頁登入保護
    auth_message="GDMS Taiwan — 請輸入帳號密碼",
)
