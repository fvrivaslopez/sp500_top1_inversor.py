"""
=============================================================================
  SIMULATOR: "ONLY THE #1 OF THE S&P 500" STRATEGY
  Always invests in the company with the largest market capitalization.
  Weekly rebalancing (Fridays). Configurable monthly contributions.
=============================================================================

Dependencies:
    pip install yfinance pandas numpy matplotlib scipy

Usage:
    python sp500_top1_investor.py
"""

import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.ticker import FuncFormatter
from scipy import stats
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

# =============================================================================
# FIXED CONSTANTS
# =============================================================================

TRANSACTION_COST  = 0.001   # 0.1% per trade
BENCHMARK_TICKER  = "SPY"

# Historical record of S&P 500 #1 by market capitalization
TOP1_HISTORICAL = [
    ("1985-01-01", "IBM",  "IBM"),
    ("1990-01-01", "XOM",  "ExxonMobil"),
    ("1993-01-01", "GE",   "General Electric"),
    ("1996-01-01", "XOM",  "ExxonMobil"),
    ("1997-01-01", "GE",   "General Electric"),
    ("1999-01-01", "MSFT", "Microsoft"),
    ("2000-01-01", "GE",   "General Electric"),
    ("2002-01-01", "XOM",  "ExxonMobil"),
    ("2005-01-01", "GE",   "General Electric"),
    ("2006-01-01", "XOM",  "ExxonMobil"),
    ("2011-10-01", "AAPL", "Apple"),
    ("2012-08-01", "XOM",  "ExxonMobil"),
    ("2012-09-01", "AAPL", "Apple"),
    ("2019-01-01", "MSFT", "Microsoft"),
    ("2019-07-01", "AAPL", "Apple"),
    ("2021-11-01", "MSFT", "Microsoft"),
    ("2022-01-01", "AAPL", "Apple"),
    ("2024-01-01", "MSFT", "Microsoft"),
    ("2024-07-01", "AAPL", "Apple"),
    ("2024-10-01", "NVDA", "NVIDIA"),
    ("2025-01-01", "AAPL", "Apple"),
]

TICKER_COLORS = {
    "IBM":  "#1f77b4",
    "GE":   "#9467bd",
    "XOM":  "#e05e00",
    "AAPL": "#a8b8c8",
    "MSFT": "#00a4ef",
    "NVDA": "#76b900",
}

COLORS = {
    "bg":      "#0d0f14",
    "panel":   "#13161e",
    "grid":    "#1e2230",
    "text":    "#e8eaf0",
    "muted":   "#6b7280",
    "accent1": "#00d4aa",
    "accent2": "#6366f1",
    "accent3": "#f59e0b",
    "red":     "#f43f5e",
    "yellow":  "#f59e0b",
    "white":   "#ffffff",
}

# =============================================================================
# USER CONFIGURATION
# =============================================================================

def ask_configuration() -> dict:
    """Prompts the user for simulation parameters interactively."""

    sep = "─" * 60
    print("\n" + "=" * 60)
    print("   SIMULATION CONFIGURATOR")
    print("=" * 60)
    print("  Answer the following questions to customize")
    print("  your simulation. Press Enter to use the default value.")
    print()

    # ── Initial capital ───────────────────────────────────────────────────────
    while True:
        try:
            raw = input("  💰 Initial capital to invest (USD) [10000]: ").strip()
            initial_capital = float(raw.replace(",", "").replace("$", "")) if raw else 10_000
            if initial_capital <= 0:
                print("     ⚠️  Capital must be greater than 0.")
                continue
            break
        except ValueError:
            print("     ⚠️  Please enter a valid number (e.g. 5000).")

    # ── Monthly contribution ──────────────────────────────────────────────────
    while True:
        try:
            raw = input("  📅 Monthly additional contribution (USD, 0 = none) [500]: ").strip()
            monthly_contribution = float(raw.replace(",", "").replace("$", "")) if raw else 500
            if monthly_contribution < 0:
                print("     ⚠️  Contribution cannot be negative.")
                continue
            break
        except ValueError:
            print("     ⚠️  Please enter a valid number (e.g. 200).")

    # ── Years to simulate ─────────────────────────────────────────────────────
    max_years = (datetime.today() - datetime(1985, 1, 1)).days // 365
    while True:
        try:
            raw = input(f"  📆 How many years back to simulate? (1-{max_years}) [15]: ").strip()
            years = int(raw) if raw else 15
            if years < 1 or years > max_years:
                print(f"     ⚠️  Must be between 1 and {max_years} years.")
                continue
            break
        except ValueError:
            print("     ⚠️  Please enter a whole number (e.g. 20).")

    # ── Calculate dates ───────────────────────────────────────────────────────
    end_date   = datetime.today()
    start_date = datetime(end_date.year - years, end_date.month, end_date.day)
    # Clamp to the earliest date available in the historical record
    min_hist   = datetime(1985, 1, 1)
    if start_date < min_hist:
        start_date = min_hist

    print()
    print(sep)
    print(f"  Configuration summary:")
    print(f"    Initial capital:       ${initial_capital:,.2f}")
    print(f"    Monthly contribution:  ${monthly_contribution:,.2f}")
    print(f"    Period:                {start_date.strftime('%m/%d/%Y')} → {end_date.strftime('%m/%d/%Y')} ({years} years)")
    print(sep)
    print()

    return {
        "initial_capital":       initial_capital,
        "monthly_contribution":  monthly_contribution,
        "years":                 years,
        "start_date":            start_date.strftime("%Y-%m-%d"),
        "end_date":              end_date.strftime("%Y-%m-%d"),
    }


# =============================================================================
# DATA DOWNLOAD
# =============================================================================

def download_prices(tickers: list, start: str, end: str) -> pd.DataFrame:
    print(f"\n📥 Downloading prices for: {', '.join(tickers)} ...")
    data = yf.download(tickers, start=start, end=end,
                       auto_adjust=True, progress=False)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame(name=tickers[0])
    data.dropna(how="all", inplace=True)
    print(f"   ✅ {len(data)} days ({data.index[0].date()} → {data.index[-1].date()})")
    return data


# =============================================================================
# TOP-1 CALENDAR
# =============================================================================

def build_top1_calendar(historical: list, idx: pd.DatetimeIndex) -> pd.Series:
    df_hist = pd.DataFrame(historical, columns=["date", "ticker", "name"])
    df_hist["date"] = pd.to_datetime(df_hist["date"])
    df_hist = df_hist.sort_values("date").reset_index(drop=True)

    cal = pd.Series(index=idx, dtype=object)
    for i, row in df_hist.iterrows():
        end = df_hist.loc[i + 1, "date"] if i + 1 < len(df_hist) else idx[-1] + timedelta(days=1)
        mask = (idx >= row["date"]) & (idx < end)
        cal[mask] = row["ticker"]

    cal.ffill(inplace=True)
    cal.bfill(inplace=True)
    return cal


# =============================================================================
# SIMULATION — with monthly contributions
# =============================================================================

def simulate_strategy(prices: pd.DataFrame,
                      cal_top1: pd.Series,
                      initial_capital: float,
                      monthly_contribution: float,
                      cost: float) -> pd.DataFrame:
    """
    Simulates the Top-1 strategy with weekly rebalancing (Fridays)
    and monthly contributions on the first trading day of each month.
    """
    print("\n⚙️  Simulating Top-1 strategy (weekly rebalancing + monthly contributions)...")

    dates = prices.index

    # Last trading day of each week → rebalancing day
    weeks = pd.Series(dates).dt.to_period("W")
    last_day_of_week = pd.Series(dates).groupby(weeks.values).last().values
    rebalancing_days = set(pd.DatetimeIndex(last_day_of_week))

    # First trading day of each month → contribution day
    months = pd.Series(dates).dt.to_period("M")
    first_day_of_month = pd.Series(dates).groupby(months.values).first().values
    contribution_days = set(pd.DatetimeIndex(first_day_of_month))

    records          = []
    capital          = initial_capital
    current_ticker   = None
    shares           = 0.0
    n_trades         = 0
    total_invested   = initial_capital

    for date, row in prices.iterrows():
        new_ticker = cal_top1.get(date)
        if new_ticker is None or pd.isna(new_ticker):
            continue

        # ── Monthly contribution ──────────────────────────────────────────────
        if date in contribution_days and monthly_contribution > 0:
            if current_ticker and shares > 0:
                # Buy more shares of the current ticker with the contribution
                p_contrib = row.get(current_ticker, np.nan)
                if not pd.isna(p_contrib) and p_contrib > 0:
                    new_shares = (monthly_contribution * (1 - cost)) / p_contrib
                    shares += new_shares
                    total_invested += monthly_contribution
            else:
                # No position yet — accumulate in cash
                capital += monthly_contribution
                total_invested += monthly_contribution

        # Price of current position
        current_price = None
        if current_ticker:
            p = row.get(current_ticker, np.nan)
            if not pd.isna(p) and p > 0:
                current_price = p

        # ── Weekly rebalancing ────────────────────────────────────────────────
        trade = None
        if date in rebalancing_days and new_ticker != current_ticker:
            new_price = row.get(new_ticker, np.nan)
            if not (pd.isna(new_price) or new_price <= 0):
                # Sell
                if current_ticker is not None and shares > 0:
                    sell_price = current_price if current_price else new_price
                    capital = shares * sell_price * (1 - cost)
                    n_trades += 1
                    trade = f"SELL {current_ticker}"

                # Buy
                net_capital    = capital * (1 - cost)
                shares         = net_capital / new_price
                capital        = 0.0
                current_ticker = new_ticker
                n_trades      += 1
                trade = (trade + " → " if trade else "") + f"BUY {current_ticker}"

        # ── Value portfolio ───────────────────────────────────────────────────
        if current_ticker:
            p_today = row.get(current_ticker, np.nan)
            if not pd.isna(p_today) and p_today > 0:
                portfolio_value = shares * p_today
            elif current_price:
                portfolio_value = shares * current_price
            else:
                portfolio_value = capital
        else:
            portfolio_value = capital

        records.append({
            "date":  date,
            "value": portfolio_value,
            "ticker": current_ticker,
            "trade":  trade,
        })

    df = pd.DataFrame(records).set_index("date")
    print(f"   ✅ Simulation complete. Trades: {n_trades} | Total invested: ${total_invested:,.0f}")
    return df, total_invested


def simulate_spy(bench_prices: pd.Series,
                 initial_capital: float,
                 monthly_contribution: float,
                 cost: float) -> tuple:
    """
    Simulates the passive strategy: buy-and-hold SPY,
    adding monthly contributions on the first trading day of each month.
    """
    dates = bench_prices.index
    months = pd.Series(dates).dt.to_period("M")
    first_day_of_month = pd.Series(dates).groupby(months.values).first().values
    contribution_days = set(pd.DatetimeIndex(first_day_of_month))

    shares         = (initial_capital * (1 - cost)) / bench_prices.iloc[0]
    total_invested = initial_capital
    values         = []

    for date, price in bench_prices.items():
        if date in contribution_days and monthly_contribution > 0 and date != dates[0]:
            new_shares = (monthly_contribution * (1 - cost)) / price
            shares += new_shares
            total_invested += monthly_contribution
        values.append(shares * price)

    return pd.Series(values, index=dates), total_invested


# =============================================================================
# METRICS
# =============================================================================

def calculate_metrics(series: pd.Series, total_invested: float, rf_annual: float = 0.02) -> dict:
    returns  = series.pct_change().dropna()
    n_days   = len(series)
    n_years  = n_days / 252

    total_return = (series.iloc[-1] / series.iloc[0]) - 1
    # CAGR adjusted to actual capital invested (approximation)
    cagr         = (series.iloc[-1] / total_invested) ** (1 / n_years) - 1 if n_years > 0 else 0

    annual_vol   = np.std(returns, ddof=1) * np.sqrt(252)
    rf_daily     = (1 + rf_annual) ** (1 / 252) - 1
    excess       = returns - rf_daily
    sharpe       = (np.mean(excess) / np.std(excess, ddof=1)) * np.sqrt(252) if np.std(excess, ddof=1) > 0 else np.nan

    down_returns = returns[returns < rf_daily]
    down_std     = np.std(down_returns, ddof=1) * np.sqrt(252) if len(down_returns) > 1 else np.nan
    sortino      = (cagr - rf_annual) / down_std if down_std and down_std > 0 else np.nan

    cum          = (1 + returns).cumprod()
    running_max  = cum.cummax()
    drawdown     = (cum - running_max) / running_max
    max_dd       = drawdown.min()
    calmar       = cagr / abs(max_dd) if max_dd != 0 else np.nan
    var_95       = np.percentile(returns, 5)

    return {
        "Total Return":       total_return,
        "CAGR (on invested)": cagr,
        "Annual Volatility":  annual_vol,
        "Sharpe Ratio":       sharpe,
        "Sortino Ratio":      sortino,
        "Calmar Ratio":       calmar,
        "Max Drawdown":       max_dd,
        "VaR 95% (daily)":    var_95,
        "Best Day":           returns.max(),
        "Worst Day":          returns.min(),
        "Skewness":           float(stats.skew(returns)),
        "Excess Kurtosis":    float(stats.kurtosis(returns)),
        "Days Simulated":     n_days,
        "Years Simulated":    round(n_years, 2),
    }


# =============================================================================
# CHART
# =============================================================================

def create_chart(result: pd.DataFrame,
                 spy_series: pd.Series,
                 metrics_strat: dict,
                 metrics_bench: dict,
                 cfg: dict,
                 total_invested_strat: float,
                 total_invested_spy: float,
                 top1_historical: list):

    print("\n Generating chart...")

    initial_capital      = cfg["initial_capital"]
    monthly_contribution = cfg["monthly_contribution"]
    start_date           = cfg["start_date"]
    end_date             = cfg["end_date"]

    fig = plt.figure(figsize=(22, 17), facecolor=COLORS["bg"])
    gs  = gridspec.GridSpec(3, 3, figure=fig,
                            height_ratios=[2.2, 1, 1],
                            hspace=0.45, wspace=0.32,
                            left=0.06, right=0.97, top=0.90, bottom=0.06)

    series_strat = result["value"]
    common_idx   = series_strat.index.intersection(spy_series.index)
    strat_v      = series_strat[common_idx]
    spy_v        = spy_series[common_idx]

    # Cumulative invested capital (reference line)
    ap_dates   = common_idx
    ap_months  = pd.Series(ap_dates).dt.to_period("M")
    first_ap   = set(pd.DatetimeIndex(pd.Series(ap_dates).groupby(ap_months.values).first().values))
    invested_cum = []
    total = initial_capital
    for d in ap_dates:
        if d in first_ap and monthly_contribution > 0 and d != ap_dates[0]:
            total += monthly_contribution
        invested_cum.append(total)
    series_invested = pd.Series(invested_cum, index=ap_dates)

    ret_strat = series_strat.pct_change().dropna()
    ret_bench = spy_series.pct_change().dropna()

    def drawdown_series(s):
        r = s.pct_change().dropna()
        c = (1 + r).cumprod()
        m = c.cummax()
        return (c - m) / m * 100

    dd_strat = drawdown_series(series_strat)
    dd_bench = drawdown_series(spy_series)

    # ── AX0: Portfolio value evolution ────────────────────────────────────────
    ax0 = fig.add_subplot(gs[0, :2])
    ax0.set_facecolor(COLORS["panel"])

    # Dominant company bands
    df_hist = pd.DataFrame(top1_historical, columns=["date", "ticker", "name"])
    df_hist["date"] = pd.to_datetime(df_hist["date"])
    df_hist = df_hist.sort_values("date").reset_index(drop=True)
    all_dates = strat_v.index

    for i, row in df_hist.iterrows():
        end_d = df_hist.loc[i+1, "date"] if i+1 < len(df_hist) else all_dates[-1] + timedelta(days=1)
        mask  = (all_dates >= row["date"]) & (all_dates < end_d)
        color = TICKER_COLORS.get(row["ticker"], "#888888")
        if mask.sum() > 0:
            ax0.axvspan(all_dates[mask][0], all_dates[mask][-1], alpha=0.09, color=color, lw=0)

    # Invested capital reference (dotted line)
    ax0.plot(series_invested.index, series_invested.values,
             color=COLORS["muted"], lw=1.0, ls=":", alpha=0.7, label="Capital invested")

    # SPY with contributions
    ax0.plot(spy_v.index, spy_v.values,
             color=COLORS["accent2"], lw=1.6, alpha=0.85, label="S&P 500 (SPY)")
    ax0.fill_between(spy_v.index, series_invested[spy_v.index], spy_v.values,
                     color=COLORS["accent2"], alpha=0.07)

    # Top-1 strategy
    ax0.plot(strat_v.index, strat_v.values,
             color=COLORS["accent1"], lw=2.3, label="Top-1 Strategy")
    ax0.fill_between(strat_v.index, series_invested[strat_v.index], strat_v.values,
                     color=COLORS["accent1"], alpha=0.12)

    # Leader change lines
    trades = result[result["trade"].notna()]
    for date in trades.index:
        if date in strat_v.index:
            ax0.axvline(date, color=COLORS["yellow"], lw=0.55, alpha=0.45, ls="--")

    ax0.set_title("Portfolio Value Evolution  ·  Top-1 vs S&P 500 (with monthly contributions)",
                  color=COLORS["text"], fontsize=13, fontweight="bold", pad=10)
    ax0.set_ylabel("Portfolio Value (USD)", color=COLORS["muted"], fontsize=10)
    ax0.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:,.0f}"))
    ax0.tick_params(colors=COLORS["muted"], labelsize=8)
    for sp in ax0.spines.values():
        sp.set_edgecolor(COLORS["grid"])
    ax0.grid(axis="y", color=COLORS["grid"], lw=0.5)

    tickers_present = list(dict.fromkeys(r[1] for r in top1_historical
                                         if pd.to_datetime(r[0]) >= pd.to_datetime(start_date)))
    patches = [mpatches.Patch(color=TICKER_COLORS.get(t, "#888"), label=t, alpha=0.75)
               for t in tickers_present]
    patches += [
        plt.Line2D([0],[0], color=COLORS["accent1"], lw=2.2, label="Top-1 Strategy"),
        plt.Line2D([0],[0], color=COLORS["accent2"], lw=1.6, label="S&P 500 (SPY)"),
        plt.Line2D([0],[0], color=COLORS["muted"],   lw=1.0, ls=":", label="Capital invested"),
        plt.Line2D([0],[0], color=COLORS["yellow"],  lw=0.8, ls="--", label="Leader change"),
    ]
    ax0.legend(handles=patches, loc="upper left", fontsize=7.5,
               facecolor=COLORS["panel"], edgecolor=COLORS["grid"],
               labelcolor=COLORS["text"], ncol=2)

    # ── AX1: Metrics panel ────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 2])
    ax1.set_facecolor(COLORS["panel"])
    ax1.axis("off")

    def fmt_m(k, v):
        if isinstance(v, float) and np.isnan(v): return "N/A"
        if k in ["Total Return", "CAGR (on invested)", "Annual Volatility", "Max Drawdown",
                 "VaR 95% (daily)", "Best Day", "Worst Day"]:
            return f"{v*100:.2f}%"
        elif k == "Days Simulated":  return f"{int(v):,}"
        elif k == "Years Simulated": return f"{v:.1f}"
        else: return f"{v:.3f}"

    metrics_show = ["CAGR (on invested)", "Annual Volatility", "Sharpe Ratio",
                    "Sortino Ratio", "Calmar Ratio", "Max Drawdown",
                    "VaR 95% (daily)", "Best Day", "Worst Day",
                    "Skewness", "Excess Kurtosis", "Years Simulated"]

    ax1.text(0.5, 1.01, "Key Metrics", transform=ax1.transAxes,
             ha="center", va="top", fontsize=12, fontweight="bold", color=COLORS["text"])

    y = 0.93
    ax1.text(0.02, y, "Metric", color=COLORS["muted"],   fontsize=8.5, transform=ax1.transAxes, fontweight="bold")
    ax1.text(0.58, y, "Top-1", color=COLORS["accent1"], fontsize=8.5, transform=ax1.transAxes, fontweight="bold", ha="center")
    ax1.text(0.88, y, "SPY",   color=COLORS["accent2"], fontsize=8.5, transform=ax1.transAxes, fontweight="bold", ha="center")
    y -= 0.04
    ax1.plot([0.01, 0.99], [y, y], color=COLORS["grid"], lw=0.8, transform=ax1.transAxes)

    for k in metrics_show:
        y -= 0.060
        ve = metrics_strat.get(k, np.nan)
        vb = metrics_bench.get(k, np.nan)
        se = fmt_m(k, ve)
        sb = fmt_m(k, vb)
        ax1.text(0.02, y, k,  color=COLORS["muted"],   fontsize=7.6, transform=ax1.transAxes)
        ax1.text(0.58, y, se, color=COLORS["accent1"], fontsize=7.6, transform=ax1.transAxes, ha="center", fontweight="bold")
        ax1.text(0.88, y, sb, color=COLORS["accent2"], fontsize=7.6, transform=ax1.transAxes, ha="center")

    y -= 0.07
    ax1.plot([0.01, 0.99], [y+0.03, y+0.03], color=COLORS["grid"], lw=0.8, transform=ax1.transAxes)

    # Capital summary
    gain_strat = strat_v.iloc[-1] - total_invested_strat
    gain_spy   = spy_v.iloc[-1]   - total_invested_spy
    ax1.text(0.02, y,      "Total invested",  color=COLORS["muted"],   fontsize=7.6, transform=ax1.transAxes)
    ax1.text(0.58, y,      f"${total_invested_strat:,.0f}", color=COLORS["accent1"], fontsize=7.6, transform=ax1.transAxes, ha="center")
    ax1.text(0.88, y,      f"${total_invested_spy:,.0f}",   color=COLORS["accent2"], fontsize=7.6, transform=ax1.transAxes, ha="center")
    y -= 0.055
    ax1.text(0.02, y,      "Final Value",     color=COLORS["text"],    fontsize=8.0, transform=ax1.transAxes, fontweight="bold")
    ax1.text(0.58, y,      f"${strat_v.iloc[-1]:,.0f}", color=COLORS["accent1"], fontsize=8.0, transform=ax1.transAxes, ha="center", fontweight="bold")
    ax1.text(0.88, y,      f"${spy_v.iloc[-1]:,.0f}",   color=COLORS["accent2"], fontsize=8.0, transform=ax1.transAxes, ha="center", fontweight="bold")
    y -= 0.055
    ax1.text(0.02, y,      "Net Gain",        color=COLORS["text"],    fontsize=7.6, transform=ax1.transAxes)
    c_s = COLORS["accent1"] if gain_strat >= 0 else COLORS["red"]
    c_b = COLORS["accent2"] if gain_spy   >= 0 else COLORS["red"]
    ax1.text(0.58, y, f"${gain_strat:+,.0f}", color=c_s, fontsize=7.6, transform=ax1.transAxes, ha="center", fontweight="bold")
    ax1.text(0.88, y, f"${gain_spy:+,.0f}",   color=c_b, fontsize=7.6, transform=ax1.transAxes, ha="center")

    for sp in ax1.spines.values():
        sp.set_edgecolor(COLORS["grid"])

    # ── AX2: Drawdown ─────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1, :2])
    ax2.set_facecolor(COLORS["panel"])
    ax2.fill_between(dd_strat.index, dd_strat.values, 0, color=COLORS["accent1"], alpha=0.40, label="Top-1")
    ax2.fill_between(dd_bench.index, dd_bench.values, 0, color=COLORS["accent2"], alpha=0.25, label="SPY")
    ax2.plot(dd_strat.index, dd_strat.values, color=COLORS["accent1"], lw=1)
    ax2.plot(dd_bench.index, dd_bench.values, color=COLORS["accent2"], lw=1)
    ax2.set_title("Drawdown (%)", color=COLORS["text"], fontsize=11, fontweight="bold")
    ax2.set_ylabel("%", color=COLORS["muted"], fontsize=9)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.tick_params(colors=COLORS["muted"], labelsize=8)
    ax2.legend(fontsize=8, facecolor=COLORS["panel"], edgecolor=COLORS["grid"], labelcolor=COLORS["text"])
    ax2.grid(axis="y", color=COLORS["grid"], lw=0.5)
    for sp in ax2.spines.values(): sp.set_edgecolor(COLORS["grid"])

    # ── AX3: Return distribution ──────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 2])
    ax3.set_facecolor(COLORS["panel"])
    common_idx2 = ret_strat.index.intersection(ret_bench.index)
    re  = ret_strat[common_idx2] * 100
    rb  = ret_bench[common_idx2] * 100
    bins = np.linspace(min(re.min(), rb.min()), max(re.max(), rb.max()), 60)
    ax3.hist(rb.values, bins=bins, color=COLORS["accent2"], alpha=0.50, label="SPY",   density=True)
    ax3.hist(re.values, bins=bins, color=COLORS["accent1"], alpha=0.65, label="Top-1", density=True)
    ax3.axvline(0, color=COLORS["white"], lw=0.7, ls="--")
    ax3.set_title("Daily Return Distribution", color=COLORS["text"], fontsize=11, fontweight="bold")
    ax3.set_xlabel("Daily return (%)", color=COLORS["muted"], fontsize=9)
    ax3.tick_params(colors=COLORS["muted"], labelsize=8)
    ax3.legend(fontsize=8, facecolor=COLORS["panel"], edgecolor=COLORS["grid"], labelcolor=COLORS["text"])
    ax3.grid(axis="y", color=COLORS["grid"], lw=0.5)
    for sp in ax3.spines.values(): sp.set_edgecolor(COLORS["grid"])

    # ── AX4: Annual returns ───────────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[2, :2])
    ax4.set_facecolor(COLORS["panel"])
    rae  = series_strat.resample("YE").last().pct_change().dropna() * 100
    rab  = spy_series.resample("YE").last().pct_change().dropna() * 100
    years_list = sorted(set(rae.index.year) & set(rab.index.year))
    x = np.arange(len(years_list)); w = 0.38
    ve_ = [rae[rae.index.year == a].iloc[0] if a in rae.index.year else 0 for a in years_list]
    vb_ = [rab[rab.index.year == a].iloc[0] if a in rab.index.year else 0 for a in years_list]
    ax4.bar(x - w/2, ve_, w, color=[COLORS["accent1"] if v >= 0 else COLORS["red"]  for v in ve_], alpha=0.85, label="Top-1")
    ax4.bar(x + w/2, vb_, w, color=[COLORS["accent2"] if v >= 0 else "#9d4e6b"       for v in vb_], alpha=0.65, label="SPY")
    ax4.axhline(0, color=COLORS["muted"], lw=0.8)
    ax4.set_xticks(x); ax4.set_xticklabels(years_list, color=COLORS["muted"], fontsize=8)
    ax4.set_title("Annual Return by Year (%)", color=COLORS["text"], fontsize=11, fontweight="bold")
    ax4.set_ylabel("%", color=COLORS["muted"], fontsize=9)
    ax4.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax4.tick_params(colors=COLORS["muted"], labelsize=8)
    ax4.legend(fontsize=8, facecolor=COLORS["panel"], edgecolor=COLORS["grid"], labelcolor=COLORS["text"])
    ax4.grid(axis="y", color=COLORS["grid"], lw=0.5)
    for sp in ax4.spines.values(): sp.set_edgecolor(COLORS["grid"])
    for xi, ve, vb in zip(x, ve_, vb_):
        ax4.text(xi - w/2, ve + (1 if ve >= 0 else -3), f"{ve:.0f}%",
                 ha="center", va="bottom" if ve >= 0 else "top", fontsize=6.5, color=COLORS["text"])
        ax4.text(xi + w/2, vb + (1 if vb >= 0 else -3), f"{vb:.0f}%",
                 ha="center", va="bottom" if vb >= 0 else "top", fontsize=6.5, color=COLORS["text"])

    # ── AX5: Leader company pie chart ─────────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, 2])
    ax5.set_facecolor(COLORS["panel"])
    ec = result[result["ticker"].notna()].groupby("ticker")["value"].count()
    labels_ = ec.index.tolist()
    sizes_  = ec.values
    colors_ = [TICKER_COLORS.get(t, "#888") for t in labels_]
    wedges, texts, autotexts = ax5.pie(
        sizes_, labels=labels_, colors=colors_,
        autopct=lambda p: f"{p:.1f}%\n({int(p/100*sum(sizes_)):.0f}d)",
        startangle=90,
        textprops={"color": COLORS["text"], "fontsize": 8.5},
        wedgeprops={"edgecolor": COLORS["bg"], "linewidth": 2}
    )
    for at in autotexts:
        at.set_fontsize(7.5); at.set_color(COLORS["bg"]); at.set_fontweight("bold")
    ax5.set_title("Days as S&P 500 Leader", color=COLORS["text"], fontsize=11, fontweight="bold")

    # ── Main title ────────────────────────────────────────────────────────────
    ret_strat_pct = (strat_v.iloc[-1] / total_invested_strat - 1) * 100
    ret_spy_pct   = (spy_v.iloc[-1]   / total_invested_spy   - 1) * 100
    diff          = strat_v.iloc[-1] - spy_v.iloc[-1]
    contrib_str   = f" + ${monthly_contribution:,.0f}/mo" if monthly_contribution > 0 else ""
    title = (f"S&P 500 Top-1  |  Initial: ${initial_capital:,.0f}{contrib_str}  |  "
             f"Top-1: ${strat_v.iloc[-1]:,.0f} ({ret_strat_pct:+.1f}%)  |  "
             f"SPY: ${spy_v.iloc[-1]:,.0f} ({ret_spy_pct:+.1f}%)  |  "
             f"Difference: ${diff:+,.0f}  |  {start_date} - {end_date}")
    fig.suptitle(title, fontsize=10, color=COLORS["text"], fontweight="bold", y=0.97)

    fig.text(0.5, 0.005,
             "Historical simulation for educational purposes only. Not financial advice. "
             "Data: Yahoo Finance. Transaction costs included (0.1% per trade).",
             ha="center", fontsize=7.5, color=COLORS["muted"])

    path = "sp500_top1_simulation.png"
    plt.savefig(path, dpi=155, bbox_inches="tight", facecolor=COLORS["bg"])
    print(f"\n✅ Chart saved to: {path}")
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        plt.close("all")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  SIMULATOR: INVESTING IN THE S&P 500 TOP-1")
    print("  With monthly contributions and weekly rebalancing")
    print("=" * 60)

    # 1. Interactive configuration
    cfg = ask_configuration()

    initial_capital      = cfg["initial_capital"]
    monthly_contribution = cfg["monthly_contribution"]
    start_date           = cfg["start_date"]
    end_date             = cfg["end_date"]

    # 2. Tickers required for the period
    tickers_needed = list(dict.fromkeys(
        r[1] for r in TOP1_HISTORICAL
        if pd.to_datetime(r[0]) <= pd.to_datetime(end_date)
    )) + [BENCHMARK_TICKER]

    # 3. Download prices
    prices_all = download_prices(tickers_needed, start_date, end_date)

    bench        = prices_all[BENCHMARK_TICKER].dropna()
    prices_strat = prices_all.drop(columns=[BENCHMARK_TICKER], errors="ignore")

    # 4. Build Top-1 calendar
    cal_top1 = build_top1_calendar(TOP1_HISTORICAL, prices_strat.index)

    # 5. Simulate Top-1 strategy
    result, total_invested_strat = simulate_strategy(
        prices_strat, cal_top1, initial_capital, monthly_contribution, TRANSACTION_COST
    )

    # 6. Simulate SPY with same contributions (aligned start date with Top-1)
    start_date_strat = result.index[0]
    bench_trimmed    = bench[bench.index >= start_date_strat]

    print("\n⚙️  Simulating passive S&P 500 (SPY + monthly contributions)...")
    spy_series, total_invested_spy = simulate_spy(
        bench_trimmed, initial_capital, monthly_contribution, TRANSACTION_COST
    )
    print(f"   ✅ Total invested SPY: ${total_invested_spy:,.0f}")

    # 7. Metrics
    print("\n📐 Calculating metrics...")
    metrics_strat = calculate_metrics(result["value"], total_invested_strat)
    metrics_bench = calculate_metrics(spy_series, total_invested_spy)

    # 8. Console summary
    print("\n" + "─" * 58)
    print(f"  {'METRIC':<28} {'TOP-1':>12} {'SPY':>12}")
    print("─" * 58)
    for k, v in metrics_strat.items():
        vb = metrics_bench.get(k, np.nan)
        def f(x):
            if isinstance(x, float) and np.isnan(x): return "N/A"
            if k in ["Total Return", "CAGR (on invested)", "Annual Volatility", "Max Drawdown",
                     "VaR 95% (daily)", "Best Day", "Worst Day"]:
                return f"{x*100:+.2f}%"
            elif k == "Days Simulated":  return f"{int(x):>7,}"
            elif k == "Years Simulated": return f"{x:>7.1f}"
            else: return f"{x:>9.3f}"
        print(f"  {k:<28} {f(v):>12} {f(vb):>12}")
    print("─" * 58)
    print(f"  {'Final Value':<28} ${result['value'].iloc[-1]:>10,.0f} ${spy_series.iloc[-1]:>10,.0f}")
    print(f"  {'Total invested':<28} ${total_invested_strat:>10,.0f} ${total_invested_spy:>10,.0f}")
    gain_s = result["value"].iloc[-1] - total_invested_strat
    gain_b = spy_series.iloc[-1]      - total_invested_spy
    print(f"  {'Net Gain':<28} ${gain_s:>+10,.0f} ${gain_b:>+10,.0f}")
    print("─" * 58)

    # 9. Chart
    create_chart(result, spy_series, metrics_strat, metrics_bench,
                 cfg, total_invested_strat, total_invested_spy, TOP1_HISTORICAL)

    print("\n Simulation complete!")


if __name__ == "__main__":
    main()
