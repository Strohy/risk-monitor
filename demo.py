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
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import yaml

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.dune_client import MorphoDataFetcher
from src.data.cache import DataCache
from src.state.reconstructor import StateReconstructor

# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print a colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 60}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}  {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.FAIL} {text}{Colors.ENDC}")


def load_configuration():
    """Load pool configuration"""
    print_header("Loading Configuration")

    config_path = Path(__file__).parent / "config" / "pools.yaml"

    if not config_path.exists():
        print_error(f"Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    pools = config['pools']
    print_success(f"Loaded configuration for {len(pools)} pools")

    for pool in pools:
        print_info(f"  - {pool['name']} (LLTV: {pool['lltv']*100}%)")

    return pools


def initialize_clients(use_cache=True):
    """Initialize Dune client and cache"""
    print_header("Initializing Clients")

    # Load environment
    load_dotenv()
    api_key = os.getenv('DUNE_API_KEY')

    if not api_key:
        print_error("DUNE_API_KEY not found in environment")
        print_info("Please create a .env file with your Dune API key")
        print_info("Get your API key at: https://dune.com/settings/api")
        sys.exit(1)

    print_success("Found DUNE_API_KEY")

    # Initialize Dune client
    fetcher = MorphoDataFetcher(api_key)
    print_success("Initialized Dune Analytics client")

    # Initialize cache
    if use_cache:
        cache = DataCache(ttl_minutes=60)
        print_success(f"Initialized data cache (TTL: 60 minutes)")

        # Show cache info
        cache_info = cache.get_cache_info()
        if cache_info['num_files'] > 0:
            print_info(f"  Found {cache_info['num_files']} cached files")
    else:
        cache = None
        print_warning("Cache disabled")

    return fetcher, cache


def fetch_pool_data(fetcher, cache, pool_config):
    """Fetch data for a specific pool"""
    pool_name = pool_config['name']
    print_header(f"Fetching Data: {pool_name}")

    market_ids = [pool_config['market_id']]
    token_addresses = [
        pool_config['collateral_address'],
        pool_config['loan_address']
    ]

    # Try cache first
    if cache:
        print_info("Checking cache...")

        positions_df = cache.get(f"positions_{pool_config['market_id']}")
        collateral_df = cache.get(f"collateral_{pool_config['market_id']}")
        pool_state_df = cache.get(f"pool_state_{pool_config['market_id']}")
        prices = cache.get(f"prices_{pool_config['market_id']}")

        if positions_df is not None and collateral_df is not None:
            print_success("Retrieved data from cache")

            # Convert prices back to dict if cached as DataFrame
            if prices is not None and not isinstance(prices, dict):
                prices = prices.to_dict('records')[0] if len(prices) > 0 else {}

            return positions_df, collateral_df, pool_state_df, prices

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
            token = pool_config['collateral'] if addr.lower() == pool_config['collateral_address'].lower() else pool_config['loan']
            print_info(f"    {token}: ${price:,.2f}")

        # Cache the results
        if cache:
            print_info("Caching results...")
            cache.set(f"positions_{pool_config['market_id']}", positions_df)
            cache.set(f"collateral_{pool_config['market_id']}", collateral_df)
            cache.set(f"pool_state_{pool_config['market_id']}", pool_state_df)

            # Cache prices as DataFrame for consistency
            import pandas as pd
            cache.set(f"prices_{pool_config['market_id']}", pd.DataFrame([prices]))
            print_success("Data cached successfully")

        return positions_df, collateral_df, pool_state_df, prices

    except Exception as e:
        print_error(f"Failed to fetch data: {e}")
        raise


def reconstruct_state(pool_config, positions_df, collateral_df, pool_state_df, prices):
    """Reconstruct pool state from raw data"""
    pool_name = pool_config['name']
    print_header(f"Reconstructing State: {pool_name}")

    try:
        # Initialize reconstructor
        reconstructor = StateReconstructor(pool_config, prices)
        print_success("Initialized state reconstructor")

        # Create snapshot
        print_info("Creating pool snapshot...")
        snapshot = reconstructor.create_snapshot(
            positions_df,
            collateral_df,
            pool_state_df,
            timestamp=datetime.now()
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
    print_info(f"Healthy Positions: {snapshot.num_healthy_positions} ({snapshot.num_healthy_positions/snapshot.num_positions*100:.1f}%)")
    print_info(f"Unhealthy Positions: {snapshot.num_unhealthy_positions} ({snapshot.num_unhealthy_positions/snapshot.num_positions*100:.1f}%)")
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
        ("Healthy (HF > 1.20)", 1.20, float('inf'))
    ]

    for label, min_hf, max_hf in buckets:
        positions = snapshot.get_positions_by_health_factor(min_hf=min_hf, max_hf=max_hf)
        count = len(positions)
        pct = (count / snapshot.num_positions * 100) if snapshot.num_positions > 0 else 0
        debt = sum(p.debt_value_usd for p in positions)
        debt_pct = (debt / snapshot.total_debt_usd * 100) if snapshot.total_debt_usd > 0 else 0

        print_info(f"{label}: {count} positions ({pct:.1f}%), ${debt:,.0f} debt ({debt_pct:.1f}%)")

    print()

    # Top borrowers
    print(f"{Colors.BOLD}Top 5 Borrowers:{Colors.ENDC}")
    top_borrowers = snapshot.get_top_borrowers(n=5)

    for i, position in enumerate(top_borrowers, 1):
        borrower_short = f"{position.borrower[:6]}...{position.borrower[-4:]}"
        print_info(f"{i}. {borrower_short}: ${position.debt_value_usd:,.2f} debt, HF={position.health_factor:.3f}")

    print()

    # Risk analysis
    risky_positions = snapshot.get_positions_by_health_factor(max_hf=1.1)
    if risky_positions:
        print(f"{Colors.WARNING}{Colors.BOLD}⚠ RISK ALERT:{Colors.ENDC}")
        print_warning(f"{len(risky_positions)} positions are within 10% of liquidation")

        total_risky_debt = sum(p.debt_value_usd for p in risky_positions)
        risky_debt_pct = (total_risky_debt / snapshot.total_debt_usd * 100)
        print_warning(f"${total_risky_debt:,.2f} in debt at risk ({risky_debt_pct:.1f}% of pool)")

        # Show price drop needed
        min_drop = min(p.liquidation_price_drop_pct() for p in risky_positions if p.health_factor > 1.0)
        print_warning(f"Minimum price drop to trigger liquidations: {min_drop * 100:.2f}%")


def save_snapshot_to_file(snapshot, reconstructor):
    """Save snapshot to file"""
    print_header("Saving Snapshot")

    # Create output directory
    output_dir = Path(__file__).parent / "data" / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename
    timestamp = snapshot.timestamp.strftime('%Y%m%d_%H%M%S')
    pool_name_safe = snapshot.pool_name.replace('/', '-')
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
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║             DeFi Risk Monitor - Pipeline Demo              ║")
    print("║                Morpho Blue Pool Analysis                   ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print(f"{Colors.ENDC}\n")

    try:
        # Step 1: Load configuration
        pools = load_configuration()

        # Step 2: Initialize clients
        fetcher, cache = initialize_clients(use_cache=True)

        # Step 3: Select pool to analyze (use first pool)
        pool_config = pools[0]
        print_info(f"\nAnalyzing pool: {pool_config['name']}")

        # Step 4: Fetch data
        positions_df, collateral_df, pool_state_df, prices = fetch_pool_data(
            fetcher, cache, pool_config
        )

        # Check if we have data
        if positions_df.empty:
            print_warning("No positions found for this pool")
            print_info("This could mean:")
            print_info("  1. The market ID is incorrect")
            print_info("  2. The pool has no active positions")
            print_info("  3. The Dune query needs adjustment")
            return

        # Step 5: Reconstruct state
        snapshot, reconstructor = reconstruct_state(
            pool_config,
            positions_df,
            collateral_df,
            pool_state_df,
            prices
        )

        # Step 6: Analyze snapshot
        analyze_snapshot(snapshot)

        # Step 7: Save snapshot
        save_snapshot_to_file(snapshot, reconstructor)

        # Success summary
        print_header("Demo Complete")
        print_success("Successfully executed full data pipeline:")
        print_info("  ✓ Loaded configuration")
        print_info("  ✓ Fetched data from Dune Analytics")
        print_info("  ✓ Reconstructed pool state")
        print_info("  ✓ Analyzed positions")
        print_info("  ✓ Saved snapshot to file")
        print()

        print(f"{Colors.OKGREEN}Ready for next phases:{Colors.ENDC}")
        print_info("  → Phase 4: Risk Metrics Engine")
        print_info("  → Phase 5: Stress Testing")
        print_info("  → Phase 6: Risk Scoring")
        print_info("  → Phase 7: Report Generation")
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
