---
title: GDMS Taiwan 台灣地震資料查詢
emoji: 🌏
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "4.44.1"
app_file: app.py
pinned: false
license: mit
short_description: 台灣地震與地球物理資料查詢（GDMS CWA）
---

# GDMS Taiwan 台灣地震資料查詢

整合 **中央氣象署 GDMS**（Taiwan Seismological and Geophysical Data Management System）資料的查詢介面。

## 功能
- 📋 **地震目錄查詢**：1940 年至今，支援時間/規模/深度/地區篩選
- 🌐 **觀測網路清單**：CWASN、TSMIP、GNSS、MAGNET、GW 等 7 個網路
- 📍 **測站清單**：各網路測站詳細資訊
- 📡 **通道清單**：波形通道查詢
- 🔧 **原始 JSON**：直接取得後端 JSON，方便程式爬取

## 資料說明
| 網路代碼 | 類型 | 測站數 |
|----------|------|--------|
| CWASN | 寬頻地震波形 | 152 |
| TSMIP | 強地動波形 | 533 |
| GNSS | 衛星定位 | 191 |
| GW | 地下水 | 6 |
| MAGNET | 地磁 | 20 |

資料來源：[gdms.cwa.gov.tw](https://gdms.cwa.gov.tw) · DOI: [10.7914/SN/T5](https://doi.org/10.7914/SN/T5)
