"""
Demo script to test the complete data pipeline

This script demonstrates:
1. Loading configuration
2. Fetching data from Dune Analytics
3. Reconstructing pool state
4. Analyzing positions
5. Saving snapshots

Requirements:
- DUNE_API_KEY in .env file
- Internet connection for Dune API
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.dune_client import MorphoDataFetcher
from src.metrics import RiskMetrics
from src.reporting import MarkdownReportGenerator
from src.scoring import RiskScorer
from src.state.reconstructor import StateReconstructor
from src.stress import StressTestEngine


# ANSI color codes for pretty output
class Colors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"


def readable_number(num):
    """Convert number to K/M/B notation"""
    if abs(num) < 1000:
        return f"{num:.2f}"

    for unit in ["K", "M", "B", "T"]:
        num /= 1000
        if abs(num) < 1000:
            return f"{num:.2f}{unit}"
    return f"{num:.2f}P"


def _format_dollars(text):
    """Auto-format dollar amounts in text with K/M/B notation"""
    import re

    def replace_amount(match):
        # Extract number from matched pattern, remove commas
        amount_str = match.group(1).replace(",", "")
        try:
            amount = float(amount_str)
            return f"${readable_number(amount)}"
        except ValueError:
            return match.group(0)  # Return original if can't parse

    # Match patterns like: $1,234.56 or $1,234 or $1234567.89
    # Captures the number part after the $
    pattern = r"\$([0-9,]+\.?[0-9]*)"
    return re.sub(pattern, replace_amount, text)


def print_header(text):
    """Print a colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    text = _format_dollars(text)
    print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    text = _format_dollars(text)
    print(f"{Colors.OKCYAN}  {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    text = _format_dollars(text)
    print(f"{Colors.WARNING}[WARNING] {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    text = _format_dollars(text)
    print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")


def load_configuration():
    """Load pool configuration"""
    print_header("Loading Configuration")

    config_path = Path(__file__).parent / "config" / "pools.yaml"

    if not config_path.exists():
        print_error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    pools = config["pools"]
    print_success(f"Loaded configuration for {len(pools)} pools")

    for pool in pools:
        print_info(f"  - {pool['name']} (LLTV: {pool['lltv']*100}%)")

    return pools


def initialize_clients():
    """Initialize Dune client"""
    print_header("Initializing Clients")

    # Load environment
    load_dotenv()
    api_key = os.getenv("DUNE_API_KEY")

    if not api_key:
        print_error("DUNE_API_KEY not found in environment")
        print_info("Please create a .env file with your Dune API key")
        print_info("Get your API key at: https://dune.com/settings/api")
        sys.exit(1)

    print_success("Found DUNE_API_KEY")

    # Initialize Dune client
    fetcher = MorphoDataFetcher(api_key)
    print_success("Initialized Dune Analytics client")

    return fetcher


def fetch_pool_data(fetcher, pool_config):
    """Fetch data for a specific pool"""
    pool_name = pool_config["name"]
    print_header(f"Fetching Data: {pool_name}")

    market_ids = [pool_config["market_id"]]
    token_addresses = [pool_config["collateral_address"], pool_config["loan_address"]]

    # Fetch from Dune
    print_info("Fetching from Dune Analytics...")

    try:
        # Fetch positions
        print_info("  Fetching positions...")
        positions_df = fetcher.fetch_positions(market_ids)
        print_success(f"  Retrieved {len(positions_df)} positions")

        # Fetch collateral
        print_info("  Fetching collateral...")
        collateral_df = fetcher.fetch_collateral(market_ids)
        print_success(f"  Retrieved {len(collateral_df)} collateral records")

        # Fetch pool state
        print_info("  Fetching pool state...")
        pool_state_df = fetcher.fetch_pool_state(market_ids)
        print_success(f"  Retrieved {len(pool_state_df)} pool state records")

        # Fetch prices
        print_info("  Fetching token prices...")
        prices = fetcher.fetch_prices(token_addresses)
        print_success(f"  Retrieved prices for {len(prices)} tokens")

        for addr, price in prices.items():
            token = (
                pool_config["collateral"]
                if addr.lower() == pool_config["collateral_address"].lower()
                else pool_config["loan"]
            )
            print_info(f"    {token}: ${price:,.2f}")

        return positions_df, collateral_df, pool_state_df, prices

    except Exception as e:
        print_error(f"Failed to fetch data: {e}")
        raise


def reconstruct_state(pool_config, positions_df, collateral_df, pool_state_df, prices):
    """Reconstruct pool state from raw data"""
    pool_name = pool_config["name"]
    print_header(f"Reconstructing State: {pool_name}")

    try:
        # Initialize reconstructor
        reconstructor = StateReconstructor(pool_config, prices)
        print_success("Initialized state reconstructor")

        # Create snapshot
        print_info("Creating pool snapshot...")
        snapshot = reconstructor.create_snapshot(
            positions_df, collateral_df, pool_state_df, timestamp=datetime.now()
        )

        print_success("Snapshot created successfully")

        return snapshot, reconstructor

    except Exception as e:
        print_error(f"Failed to reconstruct state: {e}")
        raise


def analyze_snapshot(snapshot):
    """Analyze and display snapshot metrics"""
    print_header(f"Pool Analysis: {snapshot.pool_name}")

    # Basic metrics
    print(f"{Colors.BOLD}Pool Metrics:{Colors.ENDC}")
    print_info(f"Market ID: {snapshot.market_id[:10]}...")
    print_info(f"Timestamp: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"LLTV: {snapshot.lltv * 100:.1f}%")
    print()

    print(f"{Colors.BOLD}Liquidity:{Colors.ENDC}")
    print_info(f"Total Supply: ${snapshot.total_supply:,.2f}")
    print_info(f"Total Borrow: ${snapshot.total_borrow:,.2f}")
    print_info(f"Utilization: {snapshot.utilization * 100:.2f}%")
    print()

    print(f"{Colors.BOLD}Positions:{Colors.ENDC}")
    print_info(f"Total Positions: {snapshot.num_positions}")
    print_info(
        f"Healthy Positions: {snapshot.num_healthy_positions} ({snapshot.num_healthy_positions/snapshot.num_positions*100:.1f}%)"
    )
    print_info(
        f"Unhealthy Positions: {snapshot.num_unhealthy_positions} ({snapshot.num_unhealthy_positions/snapshot.num_positions*100:.1f}%)"
    )
    print()

    print(f"{Colors.BOLD}Collateral & Debt:{Colors.ENDC}")
    print_info(f"Total Collateral: ${snapshot.total_collateral_usd:,.2f}")
    print_info(f"Total Debt: ${snapshot.total_debt_usd:,.2f}")
    print()

    print(f"{Colors.BOLD}Health Factors:{Colors.ENDC}")
    print_info(f"Average HF: {snapshot.avg_health_factor:.3f}")
    print_info(f"Weighted Avg HF: {snapshot.weighted_avg_health_factor:.3f}")
    print()

    # Analyze positions by health factor buckets
    print(f"{Colors.BOLD}Health Factor Distribution:{Colors.ENDC}")

    buckets = [
        ("Critical (HF < 1.05)", 0.0, 1.05),
        ("At Risk (1.05 - 1.10)", 1.05, 1.10),
        ("Warning (1.10 - 1.20)", 1.10, 1.20),
        ("Healthy (HF > 1.20)", 1.20, float("inf")),
    ]

    for label, min_hf, max_hf in buckets:
        positions = snapshot.get_positions_by_health_factor(
            min_hf=min_hf, max_hf=max_hf
        )
        count = len(positions)
        pct = (
            (count / snapshot.num_positions * 100) if snapshot.num_positions > 0 else 0
        )
        debt = sum(p.debt_value_usd for p in positions)
        debt_pct = (
            (debt / snapshot.total_debt_usd * 100) if snapshot.total_debt_usd > 0 else 0
        )

        print_info(
            f"{label}: {count} positions ({pct:.1f}%), ${debt:,.0f} debt ({debt_pct:.1f}%)"
        )

    print()

    # Top borrowers
    print(f"{Colors.BOLD}Top 5 Borrowers:{Colors.ENDC}")
    top_borrowers = snapshot.get_top_borrowers(n=5)

    for i, position in enumerate(top_borrowers, 1):
        borrower_short = f"{position.borrower[:6]}...{position.borrower[-4:]}"
        print_info(
            f"{i}. {borrower_short}: ${position.debt_value_usd:,.2f} debt, HF={position.health_factor:.3f}"
        )

    print()

    # Risk analysis
    risky_positions = snapshot.get_positions_by_health_factor(max_hf=1.1)
    if risky_positions:
        print(f"{Colors.WARNING}{Colors.BOLD}[RISK ALERT]:{Colors.ENDC}")
        print_warning(f"{len(risky_positions)} positions are within 10% of liquidation")

        total_risky_debt = sum(p.debt_value_usd for p in risky_positions)
        risky_debt_pct = total_risky_debt / snapshot.total_debt_usd * 100
        print_warning(
            f"${total_risky_debt:,.2f} in debt at risk ({risky_debt_pct:.1f}% of pool)"
        )

        # Show price drop needed
        min_drop = min(
            p.liquidation_price_drop_pct()
            for p in risky_positions
            if p.health_factor > 1.0
        )
        print_warning(
            f"Minimum price drop to trigger liquidations: {min_drop * 100:.2f}%"
        )


def calculate_risk_metrics(snapshot):
    """Calculate and display risk metrics"""
    print_header("Risk Metrics Analysis")

    risk_metrics = None
    try:
        # Initialize risk metrics calculator
        risk_metrics = RiskMetrics(snapshot)
        print_success("Initialized risk metrics calculator")
        print()

        # Concentration Metrics
        print(f"{Colors.BOLD}Concentration Risk:{Colors.ENDC}")
        concentration = risk_metrics.concentration_metrics()
        print_info(
            f"Top 5 Borrowers: {concentration['top_5_pct']:.1f}% of debt (${concentration['top_5_debt_usd']:,.2f})"
        )
        print_info(
            f"Top 10 Borrowers: {concentration['top_10_pct']:.1f}% of debt (${concentration['top_10_debt_usd']:,.2f})"
        )
        print_info(f"Gini Coefficient: {risk_metrics.gini_coefficient():.3f}")
        print_info(f"Herfindahl Index: {risk_metrics.herfindahl_index():.0f}")
        print()

        # Health Factor Distribution
        print(f"{Colors.BOLD}Health Factor Distribution:{Colors.ENDC}")
        hf_dist = risk_metrics.health_factor_distribution()
        print_info(f"HF < 1.05 (Critical): {hf_dist['hf_below_1.05']:.1f}% of debt")
        print_info(f"HF 1.05-1.1 (At Risk): {hf_dist['hf_1.05_to_1.1']:.1f}% of debt")
        print_info(f"HF 1.1-1.2 (Warning): {hf_dist['hf_1.1_to_1.2']:.1f}% of debt")
        print_info(f"HF 1.2-1.5 (Moderate): {hf_dist['hf_1.2_to_1.5']:.1f}% of debt")
        print_info(f"HF > 1.5 (Healthy): {hf_dist['hf_above_1.5']:.1f}% of debt")
        print()

        # Weighted Average Health Factor
        weighted_hf = risk_metrics.weighted_avg_health_factor()
        print(f"{Colors.BOLD}Health Factor Analysis:{Colors.ENDC}")
        print_info(f"Weighted Average HF: {weighted_hf:.3f}")

        liquidation_buffer = risk_metrics.liquidation_buffer_percentage(1.1)
        print_info(f"Liquidation Buffer (HF < 1.1): {liquidation_buffer:.1f}% of debt")

        at_risk = risk_metrics.positions_at_risk(1.1)
        print_info(f"Positions at Risk: {len(at_risk)}")
        print()

        # Position Size Distribution
        print(f"{Colors.BOLD}Position Size Distribution:{Colors.ENDC}")
        size_dist = risk_metrics.position_size_distribution()
        print_info(f"Micro (<$10k): {size_dist['micro_below_10k']} positions")
        print_info(f"Small ($10k-$100k): {size_dist['small_10k_to_100k']} positions")
        print_info(f"Medium ($100k-$1M): {size_dist['medium_100k_to_1m']} positions")
        print_info(f"Large ($1M-$10M): {size_dist['large_1m_to_10m']} positions")
        print_info(f"Whale (>$10M): {size_dist['whale_above_10m']} positions")
        print()

        # Risk assessment
        if concentration["top_5_pct"] > 50:
            print_warning(
                f"High concentration risk: Top 5 borrowers control {concentration['top_5_pct']:.1f}% of debt"
            )

        if liquidation_buffer > 10:
            print_warning(
                f"Significant liquidation risk: {liquidation_buffer:.1f}% of debt has HF < 1.1"
            )

        if weighted_hf < 1.5:
            print_warning(f"Low overall health: Weighted HF is {weighted_hf:.3f}")

    except Exception as e:
        print_error(f"Failed to calculate risk metrics: {e}")
        import traceback

        print(traceback.format_exc())

    return risk_metrics


def run_stress_tests(snapshot):
    """Run stress tests and display results"""
    print_header("Stress Testing")

    stress_engine = None
    try:
        # Initialize stress test engine
        stress_engine = StressTestEngine(snapshot)
        print_success("Initialized stress test engine")
        print_info(f"Testing {len(stress_engine.scenarios)} price shock scenarios")
        print()

        # Run all scenarios
        print(f"{Colors.BOLD}Running Scenarios:{Colors.ENDC}")
        results_df = stress_engine.run_all_scenarios()

        # Display results table header
        print(
            f"  {'Shock':<8} {'Positions':<11} {'Debt at Risk':<15} {'Pool %':<8} {'Bad Debt':<12}"
        )
        print(f"  {'-'*8} {'-'*11} {'-'*15} {'-'*8} {'-'*12}")

        # Display results table
        for _, row in results_df.iterrows():
            shock = row["price_shock_pct"]
            positions = row["liquidatable_positions"]
            debt_risk = row["debt_at_risk_usd"]
            pct_affected = row["pct_pool_affected"]
            bad_debt = row["bad_debt_potential_usd"]

            # Color code based on severity
            if pct_affected > 50:
                color = Colors.FAIL
            elif pct_affected > 20:
                color = Colors.WARNING
            else:
                color = Colors.OKCYAN

            # Format dollar amounts
            debt_risk_str = readable_number(debt_risk)
            bad_debt_str = readable_number(bad_debt)

            line = (
                f"  {shock:+6.0f}%  {int(positions):<11} "
                f"${debt_risk_str:<14} {pct_affected:>6.1f}%  "
                f"${bad_debt_str:<12}"
            )
            print(f"{color}{line}{Colors.ENDC}")

        print()

        # Analyze cliff points
        print(f"{Colors.BOLD}Cliff Point Analysis:{Colors.ENDC}")
        cliffs = stress_engine.find_cliff_points(results_df)

        if cliffs:
            print_warning(f"Found {len(cliffs)} cliff points (sharp risk increases)")
            print()
            for cliff in cliffs:
                print_warning(
                    f"  Between {cliff['from_shock_pct']:+.0f}% and {cliff['to_shock_pct']:+.0f}%: "
                    f"{cliff['risk_jump_pct']:.0f}% risk increase "
                    f"({cliff['new_liquidations']} new liquidations)"
                )
        else:
            print_success("No cliff points detected - risk increases smoothly")

        print()

        # # Cascading risk analysis
        # print(f"{Colors.BOLD}Cascading Risk Analysis:{Colors.ENDC}")
        # cascading = stress_engine.analyze_cascading_risk()

        # if cascading["has_severe_cliffs"]:
        #     print_warning(f"Severe cascading risk detected!")
        #     worst_cliff = cascading["worst_cliff"]
        #     if worst_cliff:
        #         print_warning(
        #             f"Worst cliff: {worst_cliff['risk_jump_pct']:.0f}% increase "
        #             f"between {worst_cliff['from_shock_pct']:.0f}% and {worst_cliff['to_shock_pct']:.0f}%"
        #         )
        # else:
        #     print_success("No severe cascading risk detected")

        # print_info(
        #     f"Average risk increase per scenario: {cascading['avg_risk_increase_per_scenario']:.2f}%"
        # )
        # print_info(
        #     f"Maximum risk increase per scenario: {cascading['max_risk_increase_per_scenario']:.2f}%"
        # )
        # print()

        # Find liquidation thresholds
        print(f"{Colors.BOLD}Liquidation Thresholds:{Colors.ENDC}")
        threshold_10 = stress_engine.get_liquidation_threshold(10.0)
        threshold_50 = stress_engine.get_liquidation_threshold(50.0)

        if threshold_10:
            print_info(f"10% of pool at risk at: {threshold_10:+.0f}% price shock")
        else:
            print_success("10% threshold not reached in tested scenarios")

        if threshold_50:
            print_warning(f"50% of pool at risk at: {threshold_50:+.0f}% price shock")
        else:
            print_success("50% threshold not reached in tested scenarios")

        print()

        # Risk warnings
        if threshold_10 and abs(threshold_10) < 15:
            print_warning(
                f"High risk: 10% of pool liquidatable with only {abs(threshold_10):.0f}% price drop"
            )

        # if cascading["cliff_points_count"] > 2:
        #     print_warning(
        #         f"Multiple cliff points detected - positions clustered at similar health factors"
        #     )

    except Exception as e:
        print_error(f"Failed to run stress tests: {e}")
        import traceback

        print(traceback.format_exc())

    return stress_engine


def calculate_risk_score(snapshot, risk_metrics, stress_engine):
    """Calculate and display composite risk score"""
    print_header("Risk Score Calculation")

    try:
        # Initialize risk scorer
        scorer = RiskScorer(risk_metrics, stress_engine)
        print_success("Initialized risk scorer")
        print()

        # Calculate composite score
        composite_score = scorer.calculate_composite_score()
        risk_level = scorer.get_risk_level(composite_score)

        # Get component scores
        component_scores = scorer.get_component_scores()

        # Display composite score with color coding
        if risk_level == "CRITICAL":
            color = Colors.FAIL
        elif risk_level == "HIGH":
            color = Colors.WARNING
        elif risk_level == "MODERATE":
            color = Colors.OKCYAN
        else:
            color = Colors.OKGREEN

        print(f"{Colors.BOLD}Composite Risk Score:{Colors.ENDC}")
        print(f"{color}  {composite_score:.1f} / 100  ({risk_level}){Colors.ENDC}")
        print()

        # Display component scores
        print(f"{Colors.BOLD}Component Scores:{Colors.ENDC}")
        for component, score in component_scores.items():
            weight = scorer.weights[component] * 100
            contribution = score * scorer.weights[component]

            # Color code each component
            if score >= 70:
                comp_color = Colors.FAIL
            elif score >= 50:
                comp_color = Colors.WARNING
            else:
                comp_color = Colors.OKCYAN

            print(
                f"{comp_color}  {component.replace('_', ' ').title()}: {score:.1f} / 100{Colors.ENDC} "
                f"(weight: {weight:.0f}%, contributes {contribution:.1f})"
            )

        print()

        # Risk level interpretation
        print(f"{Colors.BOLD}Risk Assessment:{Colors.ENDC}")
        if composite_score >= 80:
            print_error(
                "CRITICAL: This pool has severe risk factors requiring immediate attention"
            )
        elif composite_score >= 65:
            print_warning(
                "HIGH RISK: Significant risk factors detected, close monitoring recommended"
            )
        elif composite_score >= 45:
            print_info(
                "MODERATE RISK: Some risk factors present, regular monitoring advised"
            )
        elif composite_score >= 25:
            print_success(
                "LOW RISK: Pool appears relatively healthy with minor risk factors"
            )
        else:
            print_success("MINIMAL RISK: Pool appears very healthy")

        print()

        # Highlight top risk factor
        sorted_components = sorted(
            component_scores.items(), key=lambda x: x[1], reverse=True
        )
        if sorted_components[0][1] > 60:
            print_warning(
                f"Primary concern: {sorted_components[0][0].replace('_', ' ').title()} "
                f"(score: {sorted_components[0][1]:.1f})"
            )
            print()

    except Exception as e:
        print_error(f"Failed to calculate risk score: {e}")
        import traceback

        print(traceback.format_exc())


def save_snapshot_to_file(snapshot, reconstructor):
    """Save snapshot to file"""
    print_header("Saving Snapshot")

    # Create output directory
    output_dir = Path(__file__).parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = snapshot.timestamp.strftime("%Y%m%d_%H%M%S")
    pool_name_safe = snapshot.pool_name.replace("/", "-")
    filename = f"{pool_name_safe}_{timestamp}.json"
    output_path = output_dir / filename

    try:
        reconstructor.save_snapshot(snapshot, str(output_path))
        print_success(f"Snapshot saved to: {output_path}")

        # Show file size
        file_size = output_path.stat().st_size / 1024  # KB
        print_info(f"File size: {file_size:.2f} KB")

    except Exception as e:
        print_error(f"Failed to save snapshot: {e}")


def main():
    """Main demo function"""
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Morpho Blue Risk Monitor")
    parser.add_argument(
        "--save-report",
        action="store_true",
        help="Save markdown reports for analyzed pools",
    )
    args = parser.parse_args()

    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                     DeFi Risk Monitor                      ║")
    print("║                Morpho Blue Pool Analysis                   ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    # Initialize report generator if needed
    report_gen = None
    if args.save_report:
        report_gen = MarkdownReportGenerator()
        print_info(f"Reports will be saved to: {report_gen.output_dir}")
        print()

    try:
        # Step 1: Load configuration
        pools = load_configuration()

        # Step 2: Initialize clients
        fetcher = initialize_clients()

        # Step 3: Analyze all pools or specific pool based on user selection
        # Allow user to select which pools to analyze via environment variable or analyze all
        pool_indices_str = os.getenv("ANALYZE_POOLS", "all")

        if pool_indices_str.lower() == "all":
            pools_to_analyze = pools
        else:
            # Parse comma-separated indices (e.g., "0,2,3")
            indices = [int(i.strip()) for i in pool_indices_str.split(",")]
            pools_to_analyze = [pools[i] for i in indices if i < len(pools)]

        print_info(f"\nAnalyzing {len(pools_to_analyze)} pool(s)")
        print()

        # Store results for summary
        results = []

        # Step 4: Loop through each pool
        for idx, pool_config in enumerate(pools_to_analyze):
            print(f"\n{Colors.BOLD}{'=' * 60}")
            print(f"Pool {idx + 1} of {len(pools_to_analyze)}: {pool_config['name']}")
            print(f"{'=' * 60}{Colors.ENDC}\n")

            try:
                # Fetch data
                positions_df, collateral_df, pool_state_df, prices = fetch_pool_data(
                    fetcher, pool_config
                )

                # Check if we have data
                if positions_df.empty:
                    print_warning("No positions found for this pool")
                    print_info("This could mean:")
                    print_info("  1. The market ID is incorrect")
                    print_info("  2. The pool has no active positions")
                    print_info("  3. The Dune query needs adjustment")
                    results.append(
                        {
                            "pool_name": pool_config["name"],
                            "status": "NO_DATA",
                            "snapshot": None,
                            "risk_score": None,
                            "risk_level": None,
                        }
                    )
                    continue

                # Reconstruct state
                snapshot, reconstructor = reconstruct_state(
                    pool_config, positions_df, collateral_df, pool_state_df, prices
                )

                # Analyze snapshot
                analyze_snapshot(snapshot)

                # Calculate risk metrics
                risk_metrics = calculate_risk_metrics(snapshot)

                # Run stress tests
                stress_engine = run_stress_tests(snapshot)

                # Calculate risk score
                risk_score = None
                risk_level = None
                if risk_metrics and stress_engine:
                    scorer = RiskScorer(risk_metrics, stress_engine)
                    risk_score = scorer.calculate_composite_score()
                    risk_level = scorer.get_risk_level(risk_score)
                    calculate_risk_score(snapshot, risk_metrics, stress_engine)

                # Save snapshot
                save_snapshot_to_file(snapshot, reconstructor)

                # Generate markdown report if requested
                if report_gen and risk_metrics and stress_engine and scorer:
                    print_header("Generating Report")
                    timestamped_path, latest_path = report_gen.generate_report(
                        snapshot, risk_metrics, stress_engine, scorer
                    )
                    if timestamped_path:
                        print_success(
                            f"Saved timestamped report: {timestamped_path.name}"
                        )
                    if latest_path:
                        print_success(f"Saved latest report: {latest_path.name}")

                # Store results
                results.append(
                    {
                        "pool_name": pool_config["name"],
                        "status": "SUCCESS",
                        "snapshot": snapshot,
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                    }
                )

            except Exception as e:
                print_error(f"Failed to analyze pool {pool_config['name']}: {e}")
                results.append(
                    {
                        "pool_name": pool_config["name"],
                        "status": "ERROR",
                        "snapshot": None,
                        "risk_score": None,
                        "risk_level": None,
                        "error": str(e),
                    }
                )
                continue

        # Summary of all pools
        if len(pools_to_analyze) > 1:
            print_header("Multi-Pool Summary")

            print(f"{Colors.BOLD}Analysis Results:{Colors.ENDC}")
            for result in results:
                status_icon = "[OK]" if result["status"] == "SUCCESS" else "[FAIL]"

                if result["status"] == "SUCCESS":
                    risk_score = result["risk_score"]
                    risk_level = result["risk_level"]
                    snapshot = result["snapshot"]

                    # Color code by risk level
                    if risk_level == "CRITICAL":
                        color = Colors.FAIL
                    elif risk_level == "HIGH":
                        color = Colors.WARNING
                    elif risk_level == "MODERATE":
                        color = Colors.OKCYAN
                    else:
                        color = Colors.OKGREEN

                    tvl_str = readable_number(snapshot.total_supply)
                    print(
                        f"{color}{status_icon} {result['pool_name']:<30} | "
                        f"Score: {risk_score:>5.1f} ({risk_level:<8}) | "
                        f"TVL: ${tvl_str:>8} | "
                        f"Util: {snapshot.utilization*100:>5.1f}%{Colors.ENDC}"
                    )
                elif result["status"] == "NO_DATA":
                    print(
                        f"{Colors.WARNING}{status_icon} {result['pool_name']:<30} | No positions found{Colors.ENDC}"
                    )
                else:
                    print(
                        f"{Colors.FAIL}{status_icon} {result['pool_name']:<30} | Error: {result.get('error', 'Unknown')}{Colors.ENDC}"
                    )

            print()

            # Aggregate statistics
            successful_results = [r for r in results if r["status"] == "SUCCESS"]
            if successful_results:
                total_tvl = sum(r["snapshot"].total_supply for r in successful_results)
                avg_risk_score = sum(r["risk_score"] for r in successful_results) / len(
                    successful_results
                )

                print(f"{Colors.BOLD}Aggregate Statistics:{Colors.ENDC}")
                print_info(f"Total TVL: ${total_tvl:,.2f}")
                print_info(f"Average Risk Score: {avg_risk_score:.1f}")
                print_info(
                    f"Successful Analyses: {len(successful_results)}/{len(results)}"
                )
                print()

    except KeyboardInterrupt:
        print_warning("\n\nDemo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print_error(f"\nDemo failed with error: {e}")
        import traceback

        print("\n" + traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
