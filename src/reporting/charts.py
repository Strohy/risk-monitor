"""Chart generation for markdown reports using matplotlib"""

import matplotlib

matplotlib.use("Agg")  # Use non-interactive backend
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..state.models import PoolSnapshot
from ..stress.engine import StressTestEngine


class ChartGenerator:
    """Generates matplotlib charts for markdown reports"""

    def __init__(self, output_dir: Path):
        """
        Initialize chart generator

        Args:
            output_dir: Directory to save chart images
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set style for GitHub-friendly appearance (light theme, clean)
        plt.style.use("seaborn-v0_8-darkgrid")

        # Configure default settings
        self.fig_width = 10
        self.fig_height = 6
        self.dpi = 100

    def generate_health_factor_distribution(
        self, snapshot: PoolSnapshot, filename: str = "health_factor_distribution.png"
    ) -> Path:
        """
        Generate health factor distribution bar chart

        Args:
            snapshot: Pool snapshot with positions
            filename: Output filename

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(self.fig_width, self.fig_height), dpi=self.dpi)

        # Define health factor buckets
        buckets = [
            ("< 1.05\n(Critical)", 0.0, 1.05, "#d32f2f"),  # Red
            ("1.05 - 1.1\n(At Risk)", 1.05, 1.10, "#f57c00"),  # Orange
            ("1.1 - 1.2\n(Warning)", 1.10, 1.20, "#fbc02d"),  # Yellow
            ("1.2 - 1.5\n(Moderate)", 1.20, 1.50, "#388e3c"),  # Green
            ("> 1.5\n(Healthy)", 1.50, float("inf"), "#1976d2"),  # Blue
        ]

        labels = []
        values = []
        colors = []
        debt_amounts = []

        total_debt = snapshot.total_debt_usd if snapshot.total_debt_usd > 0 else 1

        for label, min_hf, max_hf, color in buckets:
            positions = snapshot.get_positions_by_health_factor(
                min_hf=min_hf, max_hf=max_hf
            )
            debt = sum(p.debt_value_usd for p in positions)
            pct = debt / total_debt * 100

            labels.append(label)
            values.append(pct)
            colors.append(color)
            debt_amounts.append(debt)

        # Create bar chart
        bars = ax.bar(
            labels, values, color=colors, alpha=0.8, edgecolor="black", linewidth=1
        )

        # Add value labels on bars
        for i, (bar, value, debt) in enumerate(zip(bars, values, debt_amounts)):
            height = bar.get_height()
            if height > 0:
                # Format debt amount
                if debt >= 1_000_000:
                    debt_str = f"${debt/1_000_000:.1f}M"
                elif debt >= 1_000:
                    debt_str = f"${debt/1_000:.0f}K"
                else:
                    debt_str = f"${debt:.0f}"

                ax.text(
                    bar.get_x() + bar.get_width() / 2.0,
                    height,
                    f"{value:.1f}%\n{debt_str}",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                    fontweight="bold",
                )

        # Customize chart
        ax.set_ylabel("% of Total Debt", fontsize=12, fontweight="bold")
        ax.set_xlabel("Health Factor Range", fontsize=12, fontweight="bold")
        ax.set_title(
            "Health Factor Distribution", fontsize=14, fontweight="bold", pad=20
        )
        ax.set_ylim(0, max(values) * 1.2 if max(values) > 0 else 100)
        ax.grid(axis="y", alpha=0.3)

        # Tight layout
        plt.tight_layout()

        # Save
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        return output_path

    def generate_stress_test_cascade(
        self, stress_engine: StressTestEngine, filename: str = "stress_test_cascade.png"
    ) -> Path:
        """
        Generate stress test cascade curve

        Args:
            stress_engine: Stress test engine with results
            filename: Output filename

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(self.fig_width, self.fig_height), dpi=self.dpi)

        # Get stress test results
        results_df = stress_engine.run_all_scenarios()

        shocks = results_df["price_shock_pct"].values
        debt_at_risk = (
            results_df["debt_at_risk_usd"].values / 1_000_000
        )  # Convert to millions

        # Plot line with area fill
        ax.plot(
            shocks,
            debt_at_risk,
            "o-",
            linewidth=3,
            markersize=8,
            color="#d32f2f",
            label="Debt at Risk",
            zorder=3,
        )
        ax.fill_between(shocks, debt_at_risk, alpha=0.3, color="#d32f2f")

        # Add threshold lines if significant liquidations occur
        threshold_10 = stress_engine.get_liquidation_threshold(10.0)
        threshold_50 = stress_engine.get_liquidation_threshold(50.0)

        if threshold_10:
            ax.axvline(
                x=threshold_10,
                color="orange",
                linestyle="--",
                linewidth=2,
                alpha=0.7,
                label=f"10% Pool at Risk ({threshold_10:+.0f}%)",
            )

        if threshold_50:
            ax.axvline(
                x=threshold_50,
                color="red",
                linestyle="--",
                linewidth=2,
                alpha=0.7,
                label=f"50% Pool at Risk ({threshold_50:+.0f}%)",
            )

        # Mark cliff points
        cliffs = stress_engine.find_cliff_points(results_df)
        if cliffs:
            for cliff in cliffs:
                shock_idx = None
                for i, shock in enumerate(shocks):
                    if shock == cliff["to_shock_pct"]:
                        shock_idx = i
                        break

                if shock_idx is not None:
                    ax.plot(
                        shocks[shock_idx],
                        debt_at_risk[shock_idx],
                        "r*",
                        markersize=15,
                        label="Cliff Point" if cliffs[0] == cliff else "",
                        zorder=4,
                    )

        # Customize chart
        ax.set_xlabel("Collateral Price Shock (%)", fontsize=12, fontweight="bold")
        ax.set_ylabel("Debt at Risk ($M)", fontsize=12, fontweight="bold")
        ax.set_title(
            "Stress Test: Liquidation Cascade", fontsize=14, fontweight="bold", pad=20
        )
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper left", framealpha=0.9)

        # Format x-axis to show negative percentages
        ax.set_xlim(min(shocks) - 2, 0)

        # Tight layout
        plt.tight_layout()

        # Save
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        return output_path

    def generate_borrower_concentration(
        self,
        concentration_metrics: Dict[str, float],
        filename: str = "borrower_concentration.png",
    ) -> Path:
        """
        Generate borrower concentration pie chart

        Args:
            concentration_metrics: Dictionary with concentration metrics
            filename: Output filename

        Returns:
            Path to saved chart
        """
        fig, ax = plt.subplots(figsize=(8, 8), dpi=self.dpi)

        # Prepare data
        top_5_pct = concentration_metrics["top_5_pct"]
        top_10_pct = concentration_metrics["top_10_pct"]

        top_5_to_10_pct = top_10_pct - top_5_pct
        rest_pct = 100 - top_10_pct

        sizes = [top_5_pct, top_5_to_10_pct, rest_pct]
        labels = [
            f"Top 5 Borrowers\n{top_5_pct:.1f}%",
            f"Next 5 Borrowers\n{top_5_to_10_pct:.1f}%",
            f"All Others\n{rest_pct:.1f}%",
        ]
        colors = ["#d32f2f", "#f57c00", "#388e3c"]  # Red, Orange, Green
        explode = (0.05, 0.02, 0)  # Explode top 5 slightly

        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="",  # We'll add custom labels
            startangle=90,
            explode=explode,
            shadow=False,
            textprops={"fontsize": 11, "fontweight": "bold"},
        )

        # Equal aspect ratio ensures circular pie
        ax.axis("equal")

        # Add title
        ax.set_title(
            "Borrower Concentration by Debt", fontsize=14, fontweight="bold", pad=20
        )

        # Add concentration warning if needed
        if top_5_pct > 50:
            fig.text(
                0.5,
                0.02,
                "Warning: High concentration risk - Top 5 control majority of debt",
                ha="center",
                fontsize=10,
                color="red",
                fontweight="bold",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
            )

        # Tight layout
        plt.tight_layout()

        # Save
        output_path = self.output_dir / filename
        plt.savefig(output_path, dpi=self.dpi, bbox_inches="tight", facecolor="white")
        plt.close()

        return output_path

    def generate_all_charts(
        self,
        snapshot: PoolSnapshot,
        stress_engine: StressTestEngine,
        concentration_metrics: Dict[str, float],
    ) -> Dict[str, Path]:
        """
        Generate all charts for a report

        Args:
            snapshot: Pool snapshot
            stress_engine: Stress test engine with results
            concentration_metrics: Concentration metrics dictionary

        Returns:
            Dictionary mapping chart names to their file paths
        """
        charts = {}

        charts["health_factor"] = self.generate_health_factor_distribution(snapshot)
        charts["stress_cascade"] = self.generate_stress_test_cascade(stress_engine)
        charts["concentration"] = self.generate_borrower_concentration(
            concentration_metrics
        )

        return charts
