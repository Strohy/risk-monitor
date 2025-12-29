# Risk Analysis Reports

This directory contains generated markdown reports for Morpho Blue pool risk analysis.

## Report Types

- **Timestamped Reports**: `PoolName_YYYY-MM-DD_HH-MM.md` - Historical reports with timestamp
- **Latest Reports**: `PoolName_latest.md` - Always contains the most recent analysis

## Generating Reports

Run the demo with the `--save-report` flag:

```bash
python demo.py --save-report
```

This will generate one report per analyzed pool.

## Report Contents

Each report includes:
- Executive Summary with overall risk score
- Pool Overview (TVL, utilization, positions)
- Risk Metrics (concentration, health factor distribution)
- Stress Test Results (price shock scenarios)
- Top 10 Borrowers with risk status

## Notes

- Timestamped reports are kept for historical tracking
- Latest reports are overwritten on each run
