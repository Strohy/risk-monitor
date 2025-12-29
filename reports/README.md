# Risk Analysis Reports

This directory contains generated markdown reports for Morpho Blue pool risk analysis.

## Directory Structure

Reports are organized by pool:

```
reports/
├── WBTC-USDC/
│   ├── 2024-12-29_14-30.md
│   ├── 2024-12-29_16-45.md
│   └── latest.md
├── wstETH-WETH/
│   ├── 2024-12-29_14-30.md
│   └── latest.md
└── README.md
```

## Report Types

- **Timestamped Reports**: `YYYY-MM-DD_HH-MM.md` - Historical reports with timestamp
- **Latest Report**: `latest.md` - Always contains the most recent analysis for that pool

## Generating Reports

Run the demo with the `--save-report` flag:

```bash
python demo.py --save-report
```

This will generate one report per analyzed pool in its own directory.

## Report Contents

Each report includes:
- Executive Summary with overall risk score
- Pool Overview (TVL, utilization, positions)
- Risk Metrics (concentration, health factor distribution)
- Stress Test Results (price shock scenarios)
- Top 10 Borrowers with risk status

## Notes

- Each pool has its own directory for organization
- Timestamped reports are kept for historical tracking
- Latest reports are overwritten on each run
