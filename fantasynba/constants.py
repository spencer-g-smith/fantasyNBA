"""
Configuration constants for Fantasy NBA analysis.

Contains league settings, statistical categories, and matchup schedules.
"""

# ============================================================================
# LEAGUE CONFIGURATION
# ============================================================================

LEAGUE_ID = 682068465
YEAR = 2027  # ESPN uses the ending year: 2026–27


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

def get_matchup_schedule(league):
    """Read daily scoring periods from ESPN; settings.matchup_periods contains weeks."""
    schedule = getattr(league, 'matchup_ids', {})
    if not schedule:
        raise ValueError(
            "ESPN has not published daily matchup scoring periods for this season yet. "
            "Player projections are available; retry matchup projections once the schedule is available."
        )
    return {
        int(matchup_id): sorted(int(period) for period in periods)
        for matchup_id, periods in schedule.items()
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

