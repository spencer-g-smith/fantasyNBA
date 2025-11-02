"""
Configuration constants for Fantasy NBA analysis.

Contains league settings, statistical categories, and matchup schedules.
"""

# ============================================================================
# LEAGUE CONFIGURATION
# ============================================================================

LEAGUE_ID = 682068465
YEAR = 2026


# ============================================================================
# STATISTICAL CATEGORIES
# ============================================================================

# Main statistical categories tracked for z-score calculations
STAT_CATEGORIES = ['PTS', 'BLK', 'STL', 'AST', 'REB', '3PM', 'FT%', 'DD']

# Standard deviation assumptions (as % of mean) for double-double calculation
# These ratios represent typical variance patterns in NBA statistics
STD_DEV_RATIOS = {
    'PTS': 0.35,  # Points typically vary ±35% from average
    'REB': 0.40,  # Rebounds vary ±40% from average
    'AST': 0.45,  # Assists vary ±45% from average
    'BLK': 0.60,  # Blocks vary ±60% from average (high variance)
    'STL': 0.60,  # Steals vary ±60% from average (high variance)
}


# ============================================================================
# LINEUP CONFIGURATION
# ============================================================================

# Lineup position slots (order matters for optimization)
# Specific positions filled first, then flex positions, then utility
LINEUP_SLOTS = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL', 'UTIL', 'UTIL']


# ============================================================================
# MATCHUP SCHEDULE
# ============================================================================

# 2026 season matchup schedule: matchup_id -> [scoring_period_ids]
# Season runs Oct 21, 2025 to Mar 15, 2026
MATCHUP_SCHEDULE_2026 = {
    1: list(range(1, 7)),        # Oct 21 - 26 (6 days)
    2: list(range(7, 14)),       # Oct 27 - Nov 2 (7 days)
    3: list(range(14, 21)),      # Nov 3 - 9 (7 days)
    4: list(range(21, 28)),      # Nov 10 - 16 (7 days)
    5: list(range(28, 35)),      # Nov 17 - 23 (7 days)
    6: list(range(35, 42)),      # Nov 24 - 30 (7 days)
    7: list(range(42, 49)),      # Dec 1 - 7 (7 days)
    8: list(range(49, 56)),      # Dec 8 - 14 (7 days)
    9: list(range(56, 63)),      # Dec 15 - 21 (7 days)
    10: list(range(63, 70)),     # Dec 22 - 28 (7 days)
    11: list(range(70, 77)),     # Dec 29 - Jan 4 (7 days)
    12: list(range(77, 84)),     # Jan 5 - 11 (7 days)
    13: list(range(84, 91)),     # Jan 12 - 18 (7 days)
    14: list(range(91, 98)),     # Jan 19 - 25 (7 days)
    15: list(range(98, 105)),    # Jan 26 - Feb 1 (7 days)
    16: list(range(105, 112)),   # Feb 2 - 8 (7 days)
    17: list(range(112, 126)),   # Feb 9 - 22 (14 days - All-Star break)
    18: list(range(126, 133)),   # Feb 23 - Mar 1 (7 days)
    19: list(range(133, 140)),   # Mar 2 - 8 (7 days)
    20: list(range(140, 147)),   # Mar 9 - 15 (7 days)
}


# ============================================================================
# TIME PERIODS
# ============================================================================

# Time periods for statistical analysis
TIME_PERIODS = {
    'total': f'{YEAR}_total',
    'last_30': f'{YEAR}_last_30',
    'last_15': f'{YEAR}_last_15',
    'last_7': f'{YEAR}_last_7',
    'projected': f'{YEAR}_projected',
}

