"""
GDMS Taiwan — FastAPI + Gradio 整合版
支援 Render.com 免費部署
"""

import json
import io
import os
import tempfile
import sys

import gradio as gr
import pandas as pd
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from gdms_client import (
    ensure_login,
    get_networks,
    get_stations,
    get_locations,
    get_channels,
    get_catalog,
)

TODAY     = date.today().isoformat()
MONTH_AGO = (date.today() - timedelta(days=30)).isoformat()

CSS = """
:root {
    --accent:  #0ea5e9;
    --bg:      #0f172a;
    --card:    #1e293b;
    --border:  #334155;
    --text:    #e2e8f0;
    --muted:   #94a3b8;
}
body, .gradio-container {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', 'Noto Sans TC', sans-serif !important;
}
.gr-panel, .gr-box, .gr-form, .block {
    background: var(--card) !important;
    border-color: var(--border) !important;
    border-radius: 12px !important;
}
h1, h2, h3 { color: var(--accent) !important; }
.gr-button-primary {
    background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 700 !important;
}
.gr-button-primary:hover { opacity:.85 !important; }
label { color: var(--muted) !important; font-size:.85rem !important; }
"""

# ── 轉換函式 ──────────────────────────────────────────────────────────────

def catalog_to_df(data: list) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    rename = {
        "event_id":"事件ID","date":"日期","time":"時間",
        "latitude":"緯度","longitude":"經度","depth":"深度(km)",
        "ML":"規模ML","nstn":"測站數","dmin":"最近站距(km)",
        "gap":"方位角間距","trms":"殘差(s)",
        "ERH":"水平誤差","ERZ":"垂直誤差",
        "fixed":"深度固定","nph":"震相數","quality":"品質",
    }
    return df.rename(columns={k:v for k,v in rename.items() if k in df.columns})

def networks_to_df(data: list) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
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

# ── 狀態 Tab ─────────────────────────────────────────────────────────────

def check_status():
    ok = ensure_login()
    if not ok:
        return "## ❌ 連線失敗\n\n無法登入 GDMS，請稍後再試。"
    nets = get_networks()
    total = sum(n.get("station_number",0) for n in nets)
    latest = max((n.get("latest","") for n in nets), default="—")
    msg = (
        f"## ✅ 連線正常\n\n"
        f"| 項目 | 值 |\n|---|---|\n"
        f"| 登入 | 成功 |\n"
        f"| 觀測網路數 | {len(nets)} 個 |\n"
        f"| 總測站數 | {total} 站 |\n"
        f"| 最新資料 | {latest} |\n\n"
        f"### 可用網路\n"
    )
    for n in nets:
        nm = n.get("name",{})
        zh = nm.get("zh","") if isinstance(nm,dict) else ""
        msg += f"- **{n.get('network_code')}** — {zh} （{n.get('station_number')} 站，至 {n.get('latest')}）\n"
    return msg

# ── 地震目錄 Tab ─────────────────────────────────────────────────────────

def query_catalog(
    stdate, sttime, eddate, edtime,
    min_ml, max_ml, min_dep, max_dep,
    min_lon, max_lon, min_lat, max_lat,
    use_circle, cir_lon, cir_lat, cir_rad,
    fmt,
):
    kw = dict(
        stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
        min_ml=float(min_ml), max_ml=float(max_ml),
        min_dep=float(min_dep), max_dep=float(max_dep),
    )
    if use_circle:
        kw.update(cir_lon=float(cir_lon), cir_lat=float(cir_lat), cir_rad=float(cir_rad))
    else:
        kw.update(min_lon=float(min_lon), max_lon=float(max_lon),
                  min_lat=float(min_lat), max_lat=float(max_lat))
    data = get_catalog(**kw)
    df   = catalog_to_df(data)
    if df.empty:
        return None, "⚠️ 查無資料（0 筆）", None
    info = (
        f"✅ 共 **{len(df)} 筆**\n\n"
        f"- 期間：{df['日期'].min()} ～ {df['日期'].max()}\n"
        f"- 規模：{pd.to_numeric(df['規模ML'],errors='coerce').min():.2f}"
        f" ～ {pd.to_numeric(df['規模ML'],errors='coerce').max():.2f}\n"
        f"- 深度：{pd.to_numeric(df['深度(km)'],errors='coerce').min():.1f}"
        f" ～ {pd.to_numeric(df['深度(km)'],errors='coerce').max():.1f} km\n"
    )
    if fmt == "CSV":
        content, ext = df.to_csv(index=False, encoding="utf-8-sig"), "csv"
    else:
        content, ext = df.to_json(orient="records", force_ascii=False, indent=2), "json"
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=f"_gdms_{stdate}_{eddate}.{ext}",
        mode="w", encoding="utf-8-sig",
    )
    tmp.write(content); tmp.close()
    return df, info, tmp.name

# ── 觀測網路 Tab ─────────────────────────────────────────────────────────

def query_networks():
    data = get_networks()
    df   = networks_to_df(data)
    if df.empty:
        return None, "⚠️ 無資料"
    return df, f"✅ 共 **{len(df)} 個**觀測網路，總測站 **{df['測站數'].sum()}** 站"

# ── 測站清單 Tab ─────────────────────────────────────────────────────────

def query_stations(network):
    data = get_stations(network.strip() if network else "")
    df   = pd.DataFrame(data) if data else pd.DataFrame()
    if df.empty:
        return None, f"⚠️ 網路 [{network}] 無資料"
    return df, f"✅ 網路 **{network}** 共 **{len(df)} 站**"

# ── 通道清單 Tab ─────────────────────────────────────────────────────────

def query_channels(network, station, location):
    data = get_channels(
        network.strip()  if network  else "",
        station.strip()  if station  else "",
        location.strip() if location else "",
    )
    df = pd.DataFrame(data) if data else pd.DataFrame()
    if df.empty:
        return None, "⚠️ 無通道資料"
    return df, f"✅ 共 **{len(df)} 個**通道"

# ── 原始 JSON Tab ────────────────────────────────────────────────────────

def raw_catalog(stdate, sttime, eddate, edtime, min_ml, max_ml):
    data = get_catalog(
        stdate=stdate, sttime=sttime, eddate=eddate, edtime=edtime,
        min_ml=float(min_ml), max_ml=float(max_ml),
    )
    return json.dumps(data, ensure_ascii=False, indent=2) if data else "[]"

def raw_networks():
    return json.dumps(get_networks(), ensure_ascii=False, indent=2)

def raw_stations(network):
    return json.dumps(get_stations(network.strip() if network else ""), ensure_ascii=False, indent=2)

# ── Gradio UI ─────────────────────────────────────────────────────────────

with gr.Blocks(
    theme=gr.themes.Base(
        primary_hue="sky", secondary_hue="indigo", neutral_hue="slate",
        font=["Inter","Noto Sans TC", gr.themes.GoogleFont("Inter")],
    ),
    css=CSS,
    title="GDMS Taiwan 地震資料查詢",
) as demo:

    gr.HTML("""
    <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#0f172a 100%);
        padding:2rem;border-radius:16px;margin-bottom:1rem;
        border:1px solid #334155;text-align:center">
        <div style="font-size:3rem">🌏</div>
        <h1 style="color:#38bdf8;font-size:2rem;font-weight:800;margin:.25rem 0">GDMS Taiwan</h1>
        <p style="color:#94a3b8;margin:.4rem 0 0">
            台灣地震與地球物理資料管理系統<br>
            <small>資料來源：中央氣象署 CWA + 中研院地球所 IES</small>
        </p>
        <div style="margin-top:.8rem;display:flex;gap:.5rem;justify-content:center;flex-wrap:wrap">
            <span style="background:#0ea5e9;color:#fff;padding:.2rem .8rem;border-radius:999px;font-size:.75rem">📡 CWASN 152站</span>
            <span style="background:#6366f1;color:#fff;padding:.2rem .8rem;border-radius:999px;font-size:.75rem">📡 TSMIP 533站</span>
            <span style="background:#10b981;color:#fff;padding:.2rem .8rem;border-radius:999px;font-size:.75rem">🛰 GNSS 191站</span>
            <span style="background:#f59e0b;color:#fff;padding:.2rem .8rem;border-radius:999px;font-size:.75rem">📅 資料始於 1940年</span>
        </div>
    </div>
    """)

    with gr.Tabs():

        # Tab 1 系統狀態
        with gr.Tab("🔌 系統狀態"):
            st_btn = gr.Button("檢查連線狀態", variant="primary")
            st_out = gr.Markdown()
            st_btn.click(check_status, outputs=st_out)
            demo.load(check_status, outputs=st_out)

        # Tab 2 地震目錄
        with gr.Tab("📋 地震目錄"):
            gr.Markdown("### 查詢條件")
            with gr.Row():
                with gr.Column(scale=1):
                    c_stdate  = gr.Textbox(label="起始日期", value=MONTH_AGO, placeholder="1973-01-01")
                    c_sttime  = gr.Textbox(label="起始時間", value="00:00:00")
                    c_eddate  = gr.Textbox(label="結束日期", value=TODAY)
                    c_edtime  = gr.Textbox(label="結束時間", value="23:59:59")
                    c_fmt     = gr.Radio(["CSV","JSON"], label="下載格式", value="CSV")
                with gr.Column(scale=1):
                    c_minml   = gr.Number(label="最小規模ML", value=4.0, minimum=-1, maximum=10)
                    c_maxml   = gr.Number(label="最大規模ML", value=10.0, minimum=-1, maximum=10)
                    c_mindep  = gr.Number(label="最小深度(km)", value=0, minimum=0, maximum=700)
                    c_maxdep  = gr.Number(label="最大深度(km)", value=700, minimum=0, maximum=700)
                with gr.Column(scale=1):
                    c_circle  = gr.Checkbox(label="圓形搜尋（否=矩形）", value=False)
                    c_minlon  = gr.Number(label="最小經度", value=118.0)
                    c_maxlon  = gr.Number(label="最大經度", value=126.0)
                    c_minlat  = gr.Number(label="最小緯度", value=20.0)
                    c_maxlat  = gr.Number(label="最大緯度", value=27.0)
                    c_clon    = gr.Number(label="圓心經度", value=121.0)
                    c_clat    = gr.Number(label="圓心緯度", value=23.5)
                    c_crad    = gr.Number(label="圓半徑(km)", value=200)
            c_btn   = gr.Button("🔍 查詢地震目錄", variant="primary", size="lg")
            c_info  = gr.Markdown()
            c_table = gr.DataFrame(label="查詢結果", interactive=False, wrap=True)
            c_file  = gr.File(label="下載檔案")
            c_btn.click(
                query_catalog,
                inputs=[c_stdate,c_sttime,c_eddate,c_edtime,
                        c_minml,c_maxml,c_mindep,c_maxdep,
                        c_minlon,c_maxlon,c_minlat,c_maxlat,
                        c_circle,c_clon,c_clat,c_crad,c_fmt],
                outputs=[c_table,c_info,c_file],
            )

        # Tab 3 觀測網路
        with gr.Tab("🌐 觀測網路"):
            n_btn   = gr.Button("取得觀測網路清單", variant="primary")
            n_info  = gr.Markdown()
            n_table = gr.DataFrame(label="網路清單", interactive=False)
            n_btn.click(query_networks, outputs=[n_table,n_info])
            demo.load(query_networks, outputs=[n_table,n_info])

        # Tab 4 測站清單
        with gr.Tab("📍 測站清單"):
            gr.Markdown("輸入網路代碼：`CWASN` / `TSMIP` / `GNSS` / `MAGNET` / `GW` / `GNSS_IES`")
            with gr.Row():
                s_net = gr.Textbox(label="網路代碼", value="CWASN")
                s_btn = gr.Button("查詢測站", variant="primary")
            s_info  = gr.Markdown()
            s_table = gr.DataFrame(label="測站清單", interactive=False)
            s_btn.click(query_stations, inputs=[s_net], outputs=[s_table,s_info])

        # Tab 5 通道清單
        with gr.Tab("📡 通道清單"):
            with gr.Row():
                ch_net = gr.Textbox(label="網路代碼", placeholder="CWASN")
                ch_sta = gr.Textbox(label="測站代碼", placeholder="NACB")
                ch_loc = gr.Textbox(label="位置代碼", placeholder="*（選填）")
                ch_btn = gr.Button("查詢通道", variant="primary")
            ch_info  = gr.Markdown()
            ch_table = gr.DataFrame(label="通道清單", interactive=False)
            ch_btn.click(query_channels, inputs=[ch_net,ch_sta,ch_loc], outputs=[ch_table,ch_info])

        # Tab 6 原始 JSON
        with gr.Tab("🔧 原始 JSON"):
            gr.Markdown("直接取得後端 JSON，方便程式爬取。")
            with gr.Accordion("地震目錄 JSON", open=True):
                with gr.Row():
                    j_stdate = gr.Textbox(label="起始日期", value=MONTH_AGO)
                    j_sttime = gr.Textbox(label="起始時間", value="00:00:00")
                    j_eddate = gr.Textbox(label="結束日期", value=TODAY)
                    j_edtime = gr.Textbox(label="結束時間", value="23:59:59")
                    j_minml  = gr.Number(label="最小規模", value=4.0)
                    j_maxml  = gr.Number(label="最大規模", value=10.0)
                j_btn = gr.Button("取得目錄 JSON", variant="primary")
                j_out = gr.Code(language="json", label="JSON 回應")
                j_btn.click(raw_catalog, inputs=[j_stdate,j_sttime,j_eddate,j_edtime,j_minml,j_maxml], outputs=j_out)
            with gr.Accordion("觀測網路 JSON", open=False):
                rn_btn = gr.Button("取得網路 JSON", variant="primary")
                rn_out = gr.Code(language="json", label="JSON 回應")
                rn_btn.click(raw_networks, outputs=rn_out)
            with gr.Accordion("測站清單 JSON", open=False):
                rs_net = gr.Textbox(label="網路代碼", value="CWASN")
                rs_btn = gr.Button("取得測站 JSON", variant="primary")
                rs_out = gr.Code(language="json", label="JSON 回應")
                rs_btn.click(raw_stations, inputs=[rs_net], outputs=rs_out)

        # Tab 7 說明
        with gr.Tab("📖 說明"):
            gr.Markdown("""
## GDMS Taiwan 資料查詢系統

### 時間覆蓋範圍
| 時期 | 筆數（ML≥4）| 備註 |
|------|------------|------|
| 1940 年 | 40 筆 | 早期稀疏資料 |
| 1973–1977 | 449 筆 | 測站開始建置 |
| 1983–1987 | 1,819 筆 | 測站擴展 |
| 1998–2002 | 1,795 筆 | 含 921 大地震 |
| 2023–2026 | 1,994 筆 | 含 2024 花蓮 M7.4 |
| **合計** | **~14,000 筆** | |

### 地震目錄欄位
| 欄位 | 說明 |
|------|------|
| event_id | 事件唯一 ID |
| date / time | 發生日期時間 |
| latitude / longitude | 震央座標 |
| depth | 震源深度 (km) |
| ML | 芮氏規模 |
| nstn | 使用測站數 |
| quality | 品質等級 A>B>C>D |

### 資料來源
- 中央氣象署：https://gdms.cwa.gov.tw
- DOI：https://doi.org/10.7914/SN/T5
            """)

    gr.HTML("""
    <div style="text-align:center;color:#475569;font-size:.78rem;
        margin-top:1.5rem;border-top:1px solid #334155;padding-top:1rem">
        資料來源：Taiwan GDMS（CWA + IES）· © CWA 2024 · DOI: 10.7914/SN/T5
    </div>
    """)

# ── 啟動 ──────────────────────────────────────────────────────────────────
port = int(os.environ.get("PORT", 7860))
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=port)
