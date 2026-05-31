# S&P 500 Top-1 Simulator

> **What if you had always invested in the single largest company in the S&P 500?**

This simulator backtests a simple strategy: at all times, hold only the stock with the highest market capitalization in the S&P 500, rebalancing weekly. Monthly contributions are supported. Results are compared against a passive buy-and-hold of SPY over the same period.

---

## How the strategy works

The S&P 500 has had a clear #1 company at any given time. This simulator tracks that leadership history and automatically switches holdings whenever the top position changes:

| Period | Leader |
|---|---|
| 1985 – 1989 | IBM |
| 1990 – 1992 | ExxonMobil |
| 1993 – 1995 | General Electric |
| 1996 | ExxonMobil |
| 1997 – 1998 | General Electric |
| 1999 | Microsoft |
| 2000 – 2001 | General Electric |
| 2002 – 2004 | ExxonMobil |
| 2005 | General Electric |
| 2006 – Oct 2011 | ExxonMobil |
| Oct 2011 – Aug 2012 | Apple |
| Aug – Sep 2012 | ExxonMobil |
| Sep 2012 – Dec 2018 | Apple |
| Jan – Jun 2019 | Microsoft |
| Jul 2019 – Oct 2021 | Apple |
| Nov 2021 – Dec 2021 | Microsoft |
| 2022 – Dec 2023 | Apple |
| Jan – Jun 2024 | Microsoft |
| Jul – Sep 2024 | Apple |
| Oct – Dec 2024 | NVIDIA |
| Jan 2025 – present | Apple |

**Rebalancing:** every Friday (last trading day of the week).  
**Contributions:** added on the first trading day of each month.  
**Transaction cost:** 0.1% per trade (buy and sell), applied to every switch.

---

## Output

The simulator prints a full metrics table to the console and saves a chart to `sp500_top1_simulation.png`:

```
────────────────────────────────────────────────────────────
  METRIC                          TOP-1          SPY
────────────────────────────────────────────────────────────
  Total Return                +983145.73%  +109459.79%
  CAGR (on invested)              +11.85%       +6.84%
  Annual Volatility               +28.42%      +21.06%
  Sharpe Ratio                      0.881        1.008
  Sortino Ratio                     0.504        0.333
  Calmar Ratio                      0.247        0.130
  Max Drawdown                    -48.09%      -52.55%
  VaR 95% (daily)                  -2.55%       -1.79%
  Best Day                        +25.06%      +30.71%
  Worst Day                       -23.52%      -10.94%
  Skewness                          0.643        3.003
  Excess Kurtosis                  16.058       60.057
  Days Simulated                   10,076        8,390
  Years Simulated                    40.0         40.0
────────────────────────────────────────────────────────────
  Final Value                $12,782,194    $1,094,502
  Total invested             $   145,000    $  121,000
  Net Gain                  $+12,637,194   $  +973,502
────────────────────────────────────────────────────────────
```

The saved chart includes six panels:

- **Portfolio value over time** — Top-1 vs SPY vs capital invested, with colored bands showing which company held the top spot
- **Key metrics panel** — side-by-side comparison table
- **Drawdown** — underwater equity curve for both strategies
- **Daily return distribution** — histogram overlay
- **Annual returns by year** — grouped bar chart
- **Days as leader** — pie chart showing how long each company held the #1 position

---

## Requirements

Python 3.9 or higher.

```
yfinance>=0.2
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
scipy>=1.10
```

Install all dependencies:

```bash
pip install -r requirements.txt
```

---

## Installation

```bash
git clone https://github.com/your-username/sp500-top1-simulator.git
cd sp500-top1-simulator
pip install -r requirements.txt
```

---

## Usage

```bash
python sp500_top1_investor.py
```

The simulator will prompt you for three inputs:

```
💰 Initial capital to invest (USD) [10000]:
📅 Monthly additional contribution (USD, 0 = none) [500]:
📆 How many years back to simulate? (1-41) [15]:
```

Press **Enter** to accept the default value shown in brackets. The simulation can go back up to 1985, the earliest year with complete data for all companies in the leadership history.

### Example runs

**Quick 10-year test with defaults:**
```
Initial capital:      $10,000
Monthly contribution: $500
Years:                10
```

**Full 40-year backtest, lump sum only:**
```
Initial capital:      $50,000
Monthly contribution: $0
Years:                40
```

---

## How it compares to SPY

Both strategies start on the same date and receive the same monthly contributions on the same days, so the comparison is fair. The SPY simulation is trimmed to begin exactly when the Top-1 simulation begins, ensuring identical time horizons and years simulated.

---

## Data source

All price data is downloaded live from **Yahoo Finance** via `yfinance`. An internet connection is required. Data for IBM, XOM, GE, MSFT, AAPL, and NVDA goes back to the mid-1980s. SPY data starts in January 1993 (its IPO date), which sets the practical limit for the benchmark comparison when simulating periods before 1993.

---

## Limitations and disclaimers

- **Survivorship bias:** this strategy is constructed with hindsight. In reality, you would not have known in 1985 that IBM would be overtaken by ExxonMobil in 1990.
- **Market impact not modeled:** the simulation assumes trades execute at the closing price with no slippage. In practice, a large position in a single stock would move the market.
- **Dividends:** `yfinance` is configured with `auto_adjust=True`, which adjusts historical prices for dividends and stock splits. Dividend income is therefore reflected in the price series.
- **Tax:** no tax on capital gains is modeled.
- **Transaction costs:** a flat 0.1% per trade is applied. Modern brokers often charge zero commission, so this is conservative.

> **This project is for educational and research purposes only. It does not constitute financial advice. Past performance is not indicative of future results.**

---

## Project structure

```
sp500-top1-simulator/
├── sp500_top1_investor.py   # Main simulator
├── requirements.txt         # Python dependencies
└── README.md
```

---

## License

MIT
