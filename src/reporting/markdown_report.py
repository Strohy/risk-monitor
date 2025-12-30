"""Markdown report generator for risk analysis"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from ..state.models import PoolSnapshot
from ..metrics.core import RiskMetrics
from ..stress.engine import StressTestEngine
from ..scoring.scorer import RiskScorer
from .charts import ChartGenerator
import pandas as pd


class MarkdownReportGenerator:
    """Generates markdown reports for pool risk analysis"""

    def __init__(self, output_dir: Path = None):
        """
        Initialize report generator

        Args:
            output_dir: Directory to save reports (default: reports/)
        """
        if output_dir is None:
            output_dir = Path(__file__).parent.parent.parent / "reports"

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_report(
        self,
        snapshot: PoolSnapshot,
        risk_metrics: RiskMetrics,
        stress_engine: StressTestEngine,
        risk_scorer: RiskScorer,
        save_timestamped: bool = True,
        save_latest: bool = True,
    ) -> tuple[Optional[Path], Optional[Path]]:
        """
        Generate markdown report for a pool

        Args:
            snapshot: Pool snapshot
            risk_metrics: Calculated risk metrics
            stress_engine: Stress test engine with results
            risk_scorer: Risk scorer with composite score
            save_timestamped: Whether to save timestamped report
            save_latest: Whether to save/overwrite latest report

        Returns:
            Tuple of (timestamped_path, latest_path)
        """
        # Generate report content
        content = self._generate_content(
            snapshot, risk_metrics, stress_engine, risk_scorer
        )

        # Create pool-specific directory
        pool_name_safe = snapshot.pool_name.replace("/", "-")
        pool_dir = self.output_dir / pool_name_safe
        pool_dir.mkdir(parents=True, exist_ok=True)

        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

        # Create images directory for this timestamp
        images_dir = pool_dir / "images" / timestamp
        images_dir.mkdir(parents=True, exist_ok=True)

        # Generate charts
        chart_gen = ChartGenerator(images_dir)
        concentration = risk_metrics.concentration_metrics()
        charts = chart_gen.generate_all_charts(snapshot, stress_engine, concentration)

        # Update content with chart references (relative to markdown file location)
        content = self._add_chart_references(content, timestamp, charts)

        timestamped_path = None
        latest_path = None

        # Save timestamped version
        if save_timestamped:
            filename = f"{timestamp}.md"
            timestamped_path = pool_dir / filename

            with open(timestamped_path, "w", encoding="utf-8") as f:
                f.write(content)

        # Save latest version (with same chart references pointing to timestamped images)
        if save_latest:
            filename = "latest.md"
            latest_path = pool_dir / filename

            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(content)

        return timestamped_path, latest_path

    def _generate_content(
        self,
        snapshot: PoolSnapshot,
        risk_metrics: RiskMetrics,
        stress_engine: StressTestEngine,
        risk_scorer: RiskScorer,
    ) -> str:
        """Generate markdown content"""

        sections = []

        # Header
        sections.append(self._generate_header(snapshot, risk_scorer))

        # Executive Summary
        sections.append(self._generate_executive_summary(snapshot, risk_scorer))

        # Pool Overview
        sections.append(self._generate_pool_overview(snapshot))

        # Risk Metrics
        sections.append(self._generate_risk_metrics(risk_metrics))

        # Stress Test Results
        sections.append(self._generate_stress_tests(stress_engine))

        # Top Borrowers
        sections.append(self._generate_top_borrowers(snapshot))

        # Footer
        sections.append(self._generate_footer())

        return "\n\n".join(sections)

    def _generate_header(self, snapshot: PoolSnapshot, risk_scorer: RiskScorer) -> str:
        """Generate report header"""
        composite_score = risk_scorer.calculate_composite_score()
        risk_level = risk_scorer.get_risk_level(composite_score)

        return f"""# Risk Analysis Report: {snapshot.pool_name} Morpho Blue pool

**Generated:** {snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}

**Overall Risk Score:** {composite_score:.1f}/100 ({risk_level})"""

    def _generate_executive_summary(
        self, snapshot: PoolSnapshot, risk_scorer: RiskScorer
    ) -> str:
        """Generate executive summary section"""
        composite_score = risk_scorer.calculate_composite_score()
        risk_level = risk_scorer.get_risk_level(composite_score)
        component_scores = risk_scorer.get_component_scores()

        # Determine primary concern
        sorted_components = sorted(
            component_scores.items(), key=lambda x: x[1], reverse=True
        )
        primary_concern = sorted_components[0][0].replace("_", " ").title()
        primary_score = sorted_components[0][1]

        # Risk interpretation
        if composite_score >= 80:
            interpretation = "**CRITICAL RISK**: This pool has severe risk factors requiring immediate attention."
        elif composite_score >= 65:
            interpretation = "**HIGH RISK**: Significant risk factors detected. Close monitoring recommended."
        elif composite_score >= 45:
            interpretation = "**MODERATE RISK**: Some risk factors present. Regular monitoring advised."
        elif composite_score >= 25:
            interpretation = (
                "**LOW RISK**: Pool appears relatively healthy with minor risk factors."
            )
        else:
            interpretation = "**MINIMAL RISK**: Pool appears very healthy."

        return f"""## Executive Summary

{interpretation}

**Key Findings:**
- Total Value Locked: ${self._format_number(snapshot.total_supply)}
- Utilization Rate: {snapshot.utilization * 100:.1f}%
- Active Positions: {snapshot.num_positions}
- Unhealthy Positions: {snapshot.num_unhealthy_positions} ({snapshot.num_unhealthy_positions/snapshot.num_positions*100:.1f}% of total)
- Primary Risk Factor: {primary_concern} (Score: {primary_score:.1f}/100)"""

    def _generate_pool_overview(self, snapshot: PoolSnapshot) -> str:
        """Generate pool overview section"""
        return f"""## Pool Overview

| Metric | Value |
|--------|-------|
| **Market ID** | `{snapshot.market_id[:16]}...` |
| **Liquidation Threshold (LLTV)** | {snapshot.lltv * 100:.1f}% |
| **Total Supply** | ${self._format_number(snapshot.total_supply)} |
| **Total Borrow** | ${self._format_number(snapshot.total_borrow)} |
| **Utilization Rate** | {snapshot.utilization * 100:.2f}% |
| **Total Collateral** | ${self._format_number(snapshot.total_collateral_usd)} |
| **Total Debt** | ${self._format_number(snapshot.total_debt_usd)} |
| **Average Health Factor** | {snapshot.avg_health_factor:.3f} |
| **Weighted Avg Health Factor** | {snapshot.weighted_avg_health_factor:.3f} |"""

    def _generate_risk_metrics(self, risk_metrics: RiskMetrics) -> str:
        """Generate risk metrics section"""
        concentration = risk_metrics.concentration_metrics()
        gini = risk_metrics.gini_coefficient()
        hhi = risk_metrics.herfindahl_index()
        hf_dist = risk_metrics.health_factor_distribution()

        content = f"""## Risk Metrics Analysis

### Concentration Risk

| Metric | Value |
|--------|-------|
| **Top 5 Borrowers** | {concentration['top_5_pct']:.1f}% of debt (${self._format_number(concentration['top_5_debt_usd'])}) |
| **Top 10 Borrowers** | {concentration['top_10_pct']:.1f}% of debt (${self._format_number(concentration['top_10_debt_usd'])}) |
| **Gini Coefficient** | {gini:.3f} |
| **Herfindahl Index** | {hhi:.0f} |

### Health Factor Distribution

Distribution of debt by health factor ranges:

| Health Factor Range | % of Total Debt |
|---------------------|-----------------|
| **< 1.05 (Critical)** | {hf_dist['hf_below_1.05']:.1f}% |
| **1.05 - 1.1 (At Risk)** | {hf_dist['hf_1.05_to_1.1']:.1f}% |
| **1.1 - 1.2 (Warning)** | {hf_dist['hf_1.1_to_1.2']:.1f}% |
| **1.2 - 1.5 (Moderate)** | {hf_dist['hf_1.2_to_1.5']:.1f}% |
| **> 1.5 (Healthy)** | {hf_dist['hf_above_1.5']:.1f}% |"""

        # Add warnings if needed
        warnings = []
        if concentration["top_5_pct"] > 50:
            warnings.append(
                f"High concentration: Top 5 borrowers control {concentration['top_5_pct']:.1f}% of debt"
            )
        if hf_dist["hf_below_1.05"] > 10:
            warnings.append(
                f"Critical positions: {hf_dist['hf_below_1.05']:.1f}% of debt has health factor below 1.05"
            )

        if warnings:
            content += "\n\n**Warnings:**\n" + "\n".join(f"- {w}" for w in warnings)

        return content

    def _generate_stress_tests(self, stress_engine: StressTestEngine) -> str:
        """Generate stress test results section"""
        results_df = stress_engine.run_all_scenarios()
        cliffs = stress_engine.find_cliff_points(results_df)

        content = """## Stress Test Results

Testing pool resilience under collateral price shocks:

| Price Shock | Liquidatable Positions | Debt at Risk | % of Pool | Bad Debt Potential |
|-------------|------------------------|--------------|-----------|-------------------|
"""

        for _, row in results_df.iterrows():
            shock = row["price_shock_pct"]
            positions = int(row["liquidatable_positions"])
            debt_risk = row["debt_at_risk_usd"]
            pct = row["pct_pool_affected"]
            bad_debt = row["bad_debt_potential_usd"]

            content += f"| {shock:+.0f}% | {positions} | ${self._format_number(debt_risk)} | {pct:.1f}% | ${self._format_number(bad_debt)} |\n"

        # Add cliff points analysis
        if cliffs:
            content += f"\n### Cliff Points Detected\n\n"
            content += f"Found {len(cliffs)} sharp risk increases (positions clustered at similar health factors):\n\n"
            for cliff in cliffs:
                content += f"- **{cliff['from_shock_pct']:+.0f}% to {cliff['to_shock_pct']:+.0f}%**: "
                content += f"{cliff['risk_jump_pct']:.0f}% risk increase ({cliff['new_liquidations']} new liquidations)\n"
        else:
            content += "\nNo cliff points detected - risk increases smoothly\n"

        # Liquidation thresholds
        threshold_10 = stress_engine.get_liquidation_threshold(10.0)
        threshold_50 = stress_engine.get_liquidation_threshold(50.0)

        content += "\n### Liquidation Thresholds\n\n"
        if threshold_10:
            content += (
                f"- **10% of pool at risk** at: {threshold_10:+.0f}% price shock\n"
            )
        else:
            content += "- **10% threshold**: Not reached in tested scenarios\n"

        if threshold_50:
            content += (
                f"- **50% of pool at risk** at: {threshold_50:+.0f}% price shock\n"
            )
        else:
            content += "- **50% threshold**: Not reached in tested scenarios\n"

        return content

    def _generate_top_borrowers(self, snapshot: PoolSnapshot) -> str:
        """Generate top borrowers section"""
        top_borrowers = snapshot.get_top_borrowers(n=10)

        content = """## Top 10 Borrowers

| Rank | Address | Debt | Health Factor | Status |
|------|---------|------|---------------|--------|
"""

        for i, position in enumerate(top_borrowers, 1):
            addr_short = f"{position.borrower[:6]}...{position.borrower[-4:]}"
            debt = self._format_number(position.debt_value_usd)
            hf = position.health_factor

            # Status indicator
            if hf < 1.05:
                status = "Critical"
            elif hf < 1.1:
                status = "At Risk"
            elif hf < 1.2:
                status = "Warning"
            else:
                status = "Healthy"

            content += f"| {i} | `{addr_short}` | ${debt} | {hf:.3f} | {status} |\n"

        return content

    def _generate_footer(self) -> str:
        """Generate report footer"""
        return f"""---

**Report generated by Risk Monitor** | [View Source](https://github.com/strohy/risk-monitor)

*This report is for informational purposes only. Always verify data independently before making decisions.*"""

    def _add_chart_references(self, content: str, timestamp: str, charts: dict) -> str:
        """Add chart image references to markdown content"""

        # Insert health factor chart after Health Factor Distribution section
        hf_chart = f"\n\n![Health Factor Distribution](images/{timestamp}/health_factor_distribution.png)\n"
        content = content.replace(
            "### Health Factor Distribution",
            f"### Health Factor Distribution\n{hf_chart}",
        )

        # Insert stress test chart after Stress Test Results header
        stress_chart = (
            f"\n![Stress Test Cascade](images/{timestamp}/stress_test_cascade.png)\n"
        )
        content = content.replace(
            "## Stress Test Results\n\nTesting pool resilience under collateral price shocks:",
            f"## Stress Test Results\n\nTesting pool resilience under collateral price shocks:\n{stress_chart}",
        )

        # Insert concentration chart after Concentration Risk header
        conc_chart = f"\n![Borrower Concentration](images/{timestamp}/borrower_concentration.png)\n"
        content = content.replace(
            "### Concentration Risk", f"### Concentration Risk\n{conc_chart}"
        )

        return content

    def _format_number(self, num: float) -> str:
        """Format number with K/M/B suffix"""
        if abs(num) < 1000:
            return f"{num:.2f}"

        for unit in ["K", "M", "B", "T"]:
            num /= 1000
            if abs(num) < 1000:
                return f"{num:.2f}{unit}"

        return f"{num:.2f}P"
