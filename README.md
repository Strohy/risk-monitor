# DeFi Lending Pool Risk Monitor

A comprehensive risk analysis system for Morpho Blue lending pools, featuring stress testing, concentration analysis, and automated reporting.

## Features

- Real-time risk metrics calculation
- Multi-scenario stress testing
- Composite risk scoring (0-100)

## Quick Start

### Prerequisites

- Python 3.10+
- pip (Python package installer)
- Dune Analytics API key ([Get one here](https://dune.com/settings/api))

### Installation

```bash
# Clone repository
git clone https://github.com/strohy/risk-monitor.git
cd risk-monitor

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env and add your DUNE_API_KEY
```

### Configuration

Before running, configure your pools in `config/pools.yaml` and add:
- Market IDs from Morpho Blue
- Token addresses and decimals
<!-- - Dune query IDs in `config/dune_queries.yaml` -->

### Usage

```bash
# Analyze all pools
python demo.py

# Analyze specific pools (by index)
ANALYZE_POOLS="0,2" python demo.py

# Generate markdown reports
python demo.py --save-report
```

### View Reports

Markdown reports are generated in the `reports/` directory when using `--save-report` flag.

## Project Structure

```
risk-monitor/
├── src/
│   ├── data/           # Dune queries & fetching
│   ├── state/          # State reconstruction
│   ├── metrics/        # Risk metrics
│   ├── stress/         # Stress testing
│   ├── scoring/        # Risk scoring
│   └── reporting/      # Report generation
├── queries/            # SQL queries for Dune
├── data/
│   ├── raw/           # Raw Dune exports
│   └── processed/     # Cleaned snapshots
├── reports/           # Generated markdown reports
├── config/            # Pool and scenario configs
└── tests/             # Unit tests
```

## Methodology

### Risk Metrics

1. **Utilization Rate:** Total borrow / total supply
2. **Health Factor Distribution:** Position-level liquidation proximity
3. **Concentration Metrics:** Top borrower market share, Gini coefficient, Herfindahl index
4. **Oracle Sensitivity:** Positions vulnerable to small price moves

### Stress Testing

We simulate collateral price shocks from -5% to -50% and measure:
- Number of liquidatable positions
- Total collateral at risk
- Potential bad debt
- Percentage of pool affected

### Risk Scoring

Composite score (0-100, higher = riskier) weighted across four components:
- **Utilization (15%):** Pool capital efficiency vs. liquidity risk
- **Health Factor (30%):** Concentration of positions near liquidation
- **Concentration (25%):** Borrower concentration risk
- **Stress Sensitivity (30%):** Vulnerability to price movements

## Configuration

### Adding Pools

Edit `config/pools.yaml` to add/modify pools:

```yaml
pools:
  - name: "wstETH/USDC"
    market_id: "0x..."
    collateral: "wstETH"
    collateral_address: "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
    collateral_decimals: 18
    loan: "USDC"
    loan_address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    decimals: 6  # loan token decimals
    lltv: 0.86
```

## Output

### Terminal Output

The demo script provides color-coded terminal output with:
- Pool metrics (TVL, utilization, positions)
- Risk metrics (concentration, health factor distribution)
- Stress test results (formatted table)
- Composite risk score and level
- Top borrowers with risk status

### Markdown Reports

When using `--save-report`, generates markdown files with:
- Executive summary with risk interpretation
- Detailed metrics tables
- Stress test analysis
- Top 10 borrowers
- Timestamped and latest versions saved


## Resources

- [Morpho Blue Documentation](https://docs.morpho.org/)
- [Dune Analytics](https://dune.com/)

## Contributing

Issues and pull requests welcome!

## License

MIT License

---

**Built for DeFi risk analysis and portfolio demonstration**
