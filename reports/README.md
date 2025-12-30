# Risk Analysis Reports

This directory contains generated markdown reports for Morpho Blue pool risk analysis.

## Directory Structure

Reports are organized by pool with separate directories for timestamped and latest images:

```
reports/
├── WBTC-USDC/
│   ├── images/
│   │   ├── 2024-12-29_14-30/
│   │   │   ├── health_factor_distribution.png
│   │   │   ├── stress_test_cascade.png
│   │   │   └── borrower_concentration.png
│   │   ├── 2024-12-29_16-45/
│   │   │   ├── health_factor_distribution.png
│   │   │   ├── stress_test_cascade.png
│   │   │   └── borrower_concentration.png
│   │   └── latest/
│   │       ├── health_factor_distribution.png
│   │       ├── stress_test_cascade.png
│   │       └── borrower_concentration.png
│   ├── 2024-12-29_14-30.md
│   ├── 2024-12-29_16-45.md
│   └── latest.md
├── wstETH-WETH/
│   ├── images/
│   │   └── latest/
│   ├── 2024-12-29_14-30.md
│   └── latest.md
└── README.md
```

## Report Types

- **Timestamped Reports**: `YYYY-MM-DD_HH-MM.md` - Historical reports with timestamp, reference charts in `images/YYYY-MM-DD_HH-MM/`
- **Latest Report**: `latest.md` - Always contains the most recent analysis for that pool, references charts in `images/latest/` (overwritten on each run)

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
- Visual Charts:
  - Health Factor Distribution (bar chart)
  - Stress Test Cascade (line chart)
  - Borrower Concentration (pie chart)

## Notes

- Each pool has its own directory for organization
- Timestamped reports and images are kept for historical tracking
- Latest reports and images are overwritten on each run
- The `latest/` directory contains stable image paths that always reference the most recent charts
