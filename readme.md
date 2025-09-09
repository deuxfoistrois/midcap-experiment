# 🎯 Mid-Cap Trading Experiment

**30-Day Automated Trading Experiment with Trailing Stop-Loss | Target: 20-35% Returns**

This repository tracks a concentrated mid-cap investment strategy focused on catalyst-driven positions with advanced trailing stop-loss management.

## 📊 Live Dashboard
🔗 **[View Live Dashboard](https://deuxfoistrois.github.io/midcap-experiment)**

## 🎯 Experiment Overview

- **Capital:** $1,000 starting value
- **Duration:** 30 days (September 8 - October 8, 2025)
- **Strategy:** Catalyst-driven mid-cap stocks ($2B-$10B market cap)
- **Positions:** 3-4 concentrated positions with professional risk management
- **Key Innovation:** Advanced trailing stop-loss system vs. static stops used in micro-cap experiment

## 🛡️ Risk Management System

### Trailing Stop-Loss Configuration
- **Initial Stop:** 13% below entry price
- **Trailing Stop:** 12% below highest price since entry
- **Activation:** Trailing begins after 5% gain from entry
- **Grace Period:** 1 trading day for volatility buffer

### Position Management
- Maximum 4 positions (equal weight ~$250 each)
- Maximum 30% single position exposure
- Maximum 50% sector concentration
- Daily monitoring with automated alerts

## 🏗️ Repository Structure

```
midcap-experiment/
├── config.json                 # Portfolio configuration
├── main.py                     # Core portfolio tracking
├── trailing_stops.py           # Advanced stop-loss management
├── requirements.txt             # Python dependencies
├── .github/workflows/          
│   └── midcap_schedule.yml     # Automated daily updates
├── docs/
│   ├── index.html              # Live dashboard
│   └── latest.json             # Current portfolio data
├── data/
│   ├── portfolio_history.csv   # Historical performance
│   ├── stop_loss_history.csv   # Stop execution log
│   └── benchmark_data.csv      # Market comparison data
├── reports/                    # Daily markdown reports
└── state/
    └── portfolio_state.json    # Current positions
```

## 🚀 Getting Started

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/midcap-experiment.git
cd midcap-experiment
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configuration
Add your Alpha Vantage API key as GitHub secret:
- Go to Settings → Secrets → Actions
- Add `ALPHAVANTAGE_API_KEY` with your API key

### 4. Run Portfolio Update
```bash
python main.py
```

## 🔄 Automated Operations

The system runs automatically via GitHub Actions:
- **20:20 UTC** - Portfolio price updates and stop-loss monitoring
- **20:25 UTC** - Benchmark data collection
- **20:30 UTC** - Daily report generation and dashboard update

## 📈 Performance Tracking

### Key Metrics Monitored
- **Portfolio Value:** Real-time market value
- **Total Return:** Absolute and percentage gains/losses
- **Risk Metrics:** Stop distance, amount at risk, Sharpe ratio
- **Benchmark Comparison:** vs MDY (Mid-Cap ETF), SPY, Russell 2000
- **Stop Performance:** Success rate, average holding periods

### Benchmark Comparison
- **Primary:** SPDR S&P MidCap 400 ETF (MDY)
- **Secondary:** SPY, IWM, QQQ
- **Sector ETFs:** XLF, XLK, XLV, XLI

## 🎯 Strategy Details

### Selection Criteria
- **Market Cap:** $2-10 billion range
- **Catalysts:** Earnings beats, FDA approvals, acquisitions, contract wins
- **Technical:** Breakout patterns, volume confirmation
- **Fundamental:** Strong
