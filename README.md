# DeFi Lending Pool Risk Monitor

A comprehensive risk analysis system for Morpho Blue lending pools, featuring stress testing, concentration analysis, and automated reporting.

## Features

- Real-time risk metrics calculation
- Multi-scenario stress testing
- Interactive HTML reports with Plotly charts
- Automated daily analysis via GitHub Actions
- Composite risk scoring (0-100)

## Quick Start

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)
- Dune Analytics API key ([Get one here](https://dune.com/settings/api))

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/risk-monitor.git
cd risk-monitor

# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Set up environment
cp .env.example .env
# Edit .env and add your DUNE_API_KEY
```

### Usage

```bash
# Analyze all configured pools
poetry run python -m src.main --pools all

# Analyze specific pool
poetry run python -m src.main --pools "wstETH/USDC"

# Force fresh data (bypass cache)
poetry run python -m src.main --pools all --force-refresh
```

### View Reports

Reports are generated in the `reports/` directory. Open `reports/index.html` in your browser.

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
├── reports/           # Generated HTML reports
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
- **Utilization (20%):** Pool capital efficiency vs. liquidity risk
- **Liquidation Clustering (30%):** Concentration of positions near liquidation
- **Concentration (25%):** Borrower concentration risk
- **Oracle Sensitivity (25%):** Vulnerability to price movements

## Configuration

### Adding Pools

Edit `config/pools.yaml` to add/modify pools:

```yaml
pools:
  - name: "wstETH/USDC"
    market_id: "0x..."
    collateral: "wstETH"
    collateral_address: "0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0"
    loan: "USDC"
    loan_address: "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    lltv: 0.86
    priority: 1
```

### Customizing Stress Scenarios

Edit `config/stress_scenarios.yaml` to modify:
- Price shock scenarios
- Risk scoring weights
- Alert thresholds

## Automated Analysis

GitHub Actions runs analysis daily at midnight UTC. To enable:

1. Add `DUNE_API_KEY` to GitHub Secrets
2. Enable GitHub Pages (source: gh-pages branch)
3. Push to main branch

Results are automatically committed and deployed.

## Analysis Document

See [ANALYSIS.md](ANALYSIS.md) for detailed risk analysis and parameter recommendations (generated after running analysis).

## Development

```bash
# Run tests
poetry run pytest

# Format code
poetry run black src/

# Lint code
poetry run ruff check src/

# Start Jupyter for exploration
poetry run jupyter lab
```

## Implementation Status

- [x] Phase 1: Foundation (Project setup)
- [ ] Phase 2: Data Layer (Dune integration)
- [ ] Phase 3: State Reconstruction
- [ ] Phase 4: Risk Metrics Engine
- [ ] Phase 5: Stress Testing
- [ ] Phase 6: Risk Scoring
- [ ] Phase 7: Report Generation
- [ ] Phase 8: CLI & Automation
- [ ] Phase 9: Written Analysis
- [ ] Phase 10: Polish & Deploy

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for full roadmap.

## Resources

- [Morpho Blue Documentation](https://docs.morpho.org/)
- [Dune Analytics](https://dune.com/)
- [Implementation Plan](IMPLEMENTATION_PLAN.md)

## Contributing

Issues and pull requests welcome!

## License

MIT License

---

**Built for DeFi risk analysis and portfolio demonstration**
