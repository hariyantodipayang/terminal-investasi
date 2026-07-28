<div align="center">

# Terminal Investasi

**A lightweight financial terminal that runs on your own computer.**
**No subscription. No credits. No API keys.**

![Version](https://img.shields.io/badge/version-1.0.0-e08b2a)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20·%20macOS%20·%20Linux-lightgrey)
![License](https://img.shields.io/badge/license-All%20rights%20reserved-red)

Stocks · Crypto · Forex — across 12 markets
Screener · Backtesting · Technical analysis · Portfolio · Trade journal

</div>

---

## Contents

1. [Why this exists](#why-this-exists)
2. [Installation](#installation)
3. [Your first 30 minutes](#your-first-30-minutes)
4. [Module guide](#module-guide)
5. [How to write symbols](#how-to-write-symbols)
6. [Where your data lives](#where-your-data-lives)
7. [Updating](#updating)
8. [Troubleshooting](#troubleshooting)
9. [Data sources](#data-sources)
10. [Honest limitations](#honest-limitations)
11. [Version history](#version-history)
12. [Technical notes](#technical-notes)

---

## Why this exists

Professional terminals charge for two things: data access and hosted services. But most of what a retail investor actually needs — prices, fundamentals, macro indicators, news — is already public and free. The expensive part is usually the convenience layer, not the data.

This project rebuilds that convenience layer, locally, for nothing.

Everything runs in Python on your own machine. Your portfolio, your journal, your wallet addresses — none of it leaves your computer.

Built in Indonesian. English support is planned.

---

## Installation

### What you need

**Python 3.9 or newer.** That is the only requirement.

Don't have it? Download from [python.org/downloads](https://www.python.org/downloads/).
**During installation, tick "Add Python to PATH"** — this is the step people miss, and skipping it causes almost every "Python not found" problem later.

To check what you have, open a terminal and run:

```
python --version
```

### Step by step

**1. Download the app**

Either clone the repository:

```
git clone https://github.com/hariyantodipayang/terminal-investasi.git
```

Or click the green **Code** button above → **Download ZIP** → extract it somewhere convenient.

**2. Start it**

| System | What to do |
|---|---|
| **Windows** | Double-click `MULAI.cmd` |
| **macOS / Linux** | `pip install -r requirements.txt` then `streamlit run terminal_ringan.py` |

**3. Wait**

The first run takes 2–3 minutes. It creates an isolated Python environment and installs the libraries. Subsequent runs take a few seconds.

**4. That's it**

Your browser opens at `http://localhost:8501`. If it doesn't open by itself, type that address in manually.

To stop the app, close the black console window, or press `Ctrl+C` inside it.

### A note for Windows users

If Windows shows **"These files can't be opened — Your Internet security settings prevented one or more files from being opened"**, it has flagged the file as downloaded from the internet.

Right-click `MULAI.cmd` → **Properties** → tick **Unblock** at the bottom → **OK**.

### Where the Python environment goes

On Windows it is created in `%LOCALAPPDATA%\terminal-ringan-venv`, deliberately **outside** the app folder. If the app folder sits inside OneDrive or Dropbox, a virtual environment inside it would mean thousands of tiny files syncing endlessly.

---

## Your first 30 minutes

Don't open everything at once. This order builds on itself.

**Minutes 1–5 — the sidebar.**
Try the light/dark toggle at the top. Look at the 13 modules. Don't click into them yet.

**Minutes 5–10 — Watchlist.**
Go to **Pasar** (Market), open the watchlist panel, and replace the defaults with 5–10 things you actually follow. Other modules read from this list, so it is the foundation.

**Minutes 10–15 — Market Pulse.**
Still on **Pasar**, work through the five tabs: world indices, crypto, forex, commodities, Indonesian equities. Just look. Let your eyes learn the layout.

**Minutes 15–25 — Charts & Analysis.**
Pick one symbol you know well. Look at the chart, then switch to the **Pembacaan Teknikal** (Technical Read) tab and compare what the app says against what you already believe. This is the fastest way to judge whether the data is trustworthy — and to notice which data sources aren't connected yet.

**Minutes 25–30 — Calculator.**
Open **Kalkulator → Ukuran Posisi** (Position Size). Enter your real capital and a trade you are actually considering. Most people are surprised by how few shares 2% risk allows. That surprise is the single most useful thing this app can give you on day one.

**Later, when you're ready:** Screener to find candidates, Backtest to test ideas, Jurnal to learn from your own decisions.

---

## Module guide

### Pasar — Market Pulse

Five tabs, each card carrying a 30-day trend sparkline coloured by direction.

- **Indeks Dunia** — six world indices including IHSG
- **Kripto** — global market cap, 24h volume, Bitcoin dominance, Fear & Greed index, and the top 12 coins
- **Forex** — 22 pairs in three groups: majors, IDR crosses, and cross rates
- **Komoditas & Kurs** — USD/IDR, gold, silver, WTI crude, dollar index, US 10-year
- **Saham Indonesia** — nine large-cap IDX names

Below the tabs sits your own **watchlist**.

### Grafik & Analisa — Charts & Analysis

**Charts tab:** candlesticks with SMA 20/50/200, EMA 20, Bollinger Bands, RSI, MACD, volume. Periods from one month to full history.

**Technical Read tab:** the app reads the chart for you. A trend line is fitted automatically, support and resistance levels are drawn from prior swing highs and lows with a count of how often each was touched, and every swing point is marked. Below the chart, a plain-language interpretation covering trend direction and strength (ADX), momentum (RSI), momentum direction (MACD), volatility (ATR and Bollinger width), volume, distance to key levels, and position within the 52-week range.

> This describes what *has* happened to price. It is not a forecast, and there are no buy or sell recommendations anywhere in this app.

### Screener

**Stocks:** 12 markets — Indonesia, US, Malaysia, Singapore, Thailand, Hong Kong, Japan, India, Australia, UK, Germany, South Korea (363 symbols). Filter by P/E, P/B, ROE, dividend yield, D/E, market cap, and sector. Each market uses its own currency, and the market-cap filter label changes accordingly.

Four **one-click presets**: Value, Dividend Hunter, High Quality, No Filter. A **0–100 composite score** ranks each stock on cheapness, profitability, balance-sheet health, and yield — with the four component scores shown separately so it isn't a black box. Results export to CSV, push straight to your watchlist, or open in a side-by-side comparison.

**Shariah screening** with two thresholds, AAOIFI and DSN-MUI/OJK. Read the caveat in [limitations](#honest-limitations) before relying on it.

**Crypto:** up to 250 coins filtered by market cap, 7-day change, and distance from all-time high.

### Fundamental — Fundamentals

Eight key ratios per stock, a visual 52-week range position indicator, and full annual financial statements: income statement, balance sheet, cash flow.

### Backtest

Four strategies — MA crossover, RSI, above-moving-average, buy and hold — across **eight timeframes** from monthly down to 1-minute, always benchmarked against simply buying and holding.

Results open with a verdict panel showing how much more or less you'd have than buy-and-hold, then: equity curve with an **underwater drawdown chart** beneath it, price chart with **holding periods shaded** green for profitable trades and red for losing ones, a **monthly returns heatmap**, the **distribution of individual trade results**, and a full trade list.

**Forex mode** prices costs in **pips** rather than percentage commission, because that is how forex brokers actually charge.

### Kalkulator — Calculators

- **Position size** — how many lots you may buy so that a loss stays within your chosen risk
- **Forex position** — pip value converted to your local currency, lot sizing, risk/reward
- **Averaging** — what adding to a position does to your average price
- **Break-even** — the minimum sell price to actually profit after all fees

### Berita & Makro — News & Macro

RSS from CNBC Indonesia, Kontan, Bisnis.com, plus global sources. A second tab carries World Bank long-run indicators — GDP growth, inflation, unemployment, exports, current account — for eight countries.

### Portofolio — Portfolio

Holdings with automatic P&L from live prices, allocation donut, and profit/loss per position.

### Dompet Kripto — Crypto Wallet

Paste a **public address** for Bitcoin, Ethereum, or Solana to see balances, local-currency value, transaction count, and ERC-20 token holdings.

> **Read-only.** This app will never ask for your seed phrase or private key. No application should — if one does, close it.

### Peringatan — Alerts

Price thresholds checked when you open the page. Entirely local; there is no server watching the market while the app is closed, and no phone notifications.

### Jurnal — Trade Journal

Record each trade along with **why** you made it and **how you felt** at the time. FIFO-matched statistics produce win rate, average win and loss, and expectancy per trade — plus a chart of average result grouped by emotional state. That chart is often the most revealing thing in the app.

### Laporan — Reports

Export portfolio, journal, wallet, or watchlist to a clean PDF under your own name.

### Tentang — About

App information, the author's profile, and the **update** panel.

---

## How to write symbols

| Type | Pattern | Examples |
|---|---|---|
| Indonesian stocks | code + `.JK` | `BBCA.JK` · `TLKM.JK` · `GOTO.JK` |
| US stocks | plain code | `AAPL` · `MSFT` · `NVDA` |
| Malaysia | code + `.KL` | `1155.KL` |
| Singapore | code + `.SI` | `D05.SI` |
| Thailand | code + `.BK` | `PTT.BK` |
| Hong Kong | code + `.HK` | `0700.HK` |
| Japan | code + `.T` | `7203.T` |
| India | code + `.NS` | `RELIANCE.NS` |
| UK | code + `.L` | `SHEL.L` |
| Germany | code + `.DE` | `SAP.DE` |
| Crypto | currency pair | `BTC-USD` · `ETH-USD` |
| Indices | leading `^` | `^JKSE` (IHSG) · `^GSPC` (S&P 500) |
| Forex | pair + `=X` | `USDIDR=X` · `EURUSD=X` |
| Commodities | code + `=F` | `GC=F` (gold) · `CL=F` (crude) |

---

## Where your data lives

Everything you create is stored in the `data/` folder as plain JSON you can open in any text editor:

| File | Contents |
|---|---|
| `watchlist.json` | Your tracked symbols |
| `portofolio.json` | Holdings, quantities, average prices |
| `jurnal.json` | Trade journal entries |
| `peringatan.json` | Price alerts |
| `dompet.json` | Crypto wallet addresses (public only) |
| `pengaturan.json` | Theme, update preferences |

Moving to another computer? Copy the `data/` folder. Want a clean slate? Delete it.

**Nothing is uploaded.** No account, no telemetry, no analytics. The only outbound requests are to the public data sources listed below, and — if you leave it enabled — a version check against this repository.

---

## Updating

The app checks this repository for a release manifest and shows a notice in the sidebar when a newer version exists. Open **Tentang → Pembaruan** to read what changed and install it.

**Nothing is downloaded or replaced until you tick a confirmation box and press the button.**

What happens when you do:

1. Every file is downloaded and its **SHA-256 hash** verified against the published value
2. If any hash mismatches, the entire update is cancelled and nothing is written
3. Your current version is backed up to `cadangan/`
4. New files are written
5. You restart the app

Only three files can ever be replaced: `terminal_ringan.py`, `requirements.txt`, and `BACA-DULU.md`. Your `data/` folder is never touched. A rollback button sits on the same page.

**The automatic check can be switched off** in the same panel. When enabled, the app fetches a small manifest from GitHub each time it starts (cached for six hours) — which means GitHub can see your IP address, as it would for any website. None of your data is sent.

---

## Troubleshooting

**"Python is not recognised" / "Python not found"**
Python isn't installed, or wasn't added to PATH. Reinstall from python.org and tick "Add Python to PATH".

**The browser doesn't open**
Go to `http://localhost:8501` manually.

**Everything shows a dash (—)**
No internet connection, or Yahoo Finance is having trouble. Press the **MUAT ULANG** (Reload) button.

**One symbol is blank but others work**
The symbol is probably misspelled. Check the [symbol table](#how-to-write-symbols) — Indonesian stocks need the `.JK` suffix.

**The crypto section is empty**
CoinGecko rate-limits free usage. Wait a minute and reload. Results are cached for three minutes, so normal use rarely hits the limit.

**The screener is slow**
The first run fetches each stock individually, taking 20–40 seconds. Results are then cached for an hour.

**Intraday backtest says "not enough data"**
Yahoo keeps 1-minute bars for 7 days, other sub-hourly bars for 60 days, and hourly for about two years. Choose a longer period or a coarser timeframe.

**"These files can't be opened" on Windows**
Right-click `MULAI.cmd` → Properties → tick **Unblock** → OK.

**Something broke after an update**
Open **Tentang → Pembaruan**, scroll to the bottom, and roll back to the previous version.

Still stuck? [Open an issue](https://github.com/hariyantodipayang/terminal-investasi/issues) with what you did, what you expected, and what happened.

---

## Data sources

| What | Source | Key required |
|---|---|---|
| Equities, crypto, indices, commodities, forex | Yahoo Finance | No |
| Crypto market data and screener | CoinGecko | No |
| Fear & Greed Index | alternative.me | No |
| Macroeconomic indicators | World Bank API | No |
| Market news | RSS feeds | No |
| Bitcoin balances | Blockstream | No |
| Ethereum balances and tokens | Ethplorer | No |
| Solana balances | Solana public RPC | No |

---

## Honest limitations

Please read this before relying on anything here.

- **Prices are delayed**, typically 15–20 minutes for equities. Fine for monitoring, not for fast trading.
- **Yahoo Finance is an unofficial source.** Its format changes occasionally and the app needs adjusting when it does.
- **Intraday data is limited and has no bid-ask**, so short-timeframe backtests are approximate.
- **Currencies are not converted.** Mixing IDR and USD positions in one portfolio produces a meaningless total.
- **Backtests exclude dividends and delisted companies**, both of which flatter historical results.
- **Forex backtests ignore overnight swap and leverage.** On positions held for months, swap can exceed the entire price gain. Margin-call risk is not modelled at all.
- **The Shariah screen is a first-pass filter, not a ruling.** It evaluates business activity and interest-bearing debt ratios, but cannot compute non-halal income or receivables — neither is available in free data. Indonesian investors should defer to the OJK's *Daftar Efek Syariah* (DES), or the ISSI and JII indices. A stock may pass here and be absent from DES, or the reverse.
- **Nothing here is investment advice.** There are deliberately no buy or sell signals. Automated signals encourage people to stop thinking, and that is usually where money goes.

---

## Version history

### 1.0.0 — July 2026

First public release.

- Market Pulse across indices, crypto, forex, commodities, and Indonesian equities
- Charts with six indicators plus automated technical reading
- Screener covering 12 markets, with presets, composite scoring, and Shariah filtering
- Fundamentals with full financial statements
- Backtesting across 8 timeframes with forex-aware cost modelling
- Position sizing, forex, averaging, and break-even calculators
- News and World Bank macro indicators
- Portfolio, read-only crypto wallet tracking, price alerts, trade journal
- PDF reporting
- Light and dark themes
- Signed opt-in in-app updater

---

## Technical notes

A single-file Python application (~5,000 lines) built on Streamlit, pandas, and Plotly.

Indicators — RSI, MACD, ATR, ADX with Wilder smoothing, swing detection, support/resistance clustering — are implemented from scratch with no TA library dependency.

The backtest engine shifts signals by one bar so today's decision executes at tomorrow's price, applies transaction costs on every position change, and derives annualisation from actual calendar dates rather than assuming a fixed number of bars per year. These are the details that separate a backtest from a fantasy.

Themes are driven by a single 29-colour palette; no colour is hardcoded anywhere else in the application.

---

## Author

**Hariyanto, S.Sos** — civil servant in Kepahiang, Indonesia. Developer, crypto educator, and currently pursuing a master's degree in Islamic Economics at IAIN Curup.

[Profile](https://dipayang.idcrypt.xyz/profil) · [IDCrypt](https://idcrypt.xyz) · [YouTube](https://www.youtube.com/@ardion_news) · [WhatsApp](https://wa.me/6285609326414)

If this tool is useful to you, support is welcome via DANA — the QR code is in **Tentang → Pembuat**.

---

## License

Copyright © 2026 Hariyanto. All rights reserved.

You may read and evaluate this code. Redistribution, modification, and commercial use require written permission. Get in touch if you'd like to discuss licensing.
