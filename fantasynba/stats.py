"""One scoring implementation for rankings, CLI reports, and matchup lineups."""
import numpy as np

from .constants import STAT_CATEGORIES, YEAR
from .players import get_player_per_game_stats, get_comparison_players
from .scoring import (number, nonnegative, ft_line, ft_impact, build_dd_peers,
                      resolve_double_doubles)

SCORING_CATEGORIES = tuple('FT impact' if stat == 'FT%' else stat for stat in STAT_CATEGORIES)


def calculate_expected_double_doubles(stats_dict):
    """Deprecated: a production line alone cannot identify an observed DD rate.

    Use resolve_double_doubles(player, stats_key, peers) for source-aware rates.
    """
    raise ValueError('DD requires observed history or an explicit projection; use resolve_double_doubles')


def extract_player_stats(players, year, stats_key, comparison_players=None):
    """Extract requested-period data without silently substituting projections."""
    pool = get_comparison_players(players) if comparison_players is None else comparison_players
    peers = build_dd_peers(pool, int(stats_key.split('_')[0]))
    player_stats = {}
    raw_stats = {stat: [] for stat in SCORING_CATEGORIES}
    raw_stats['_comparison_ids'] = {getattr(p, 'playerId', p.name) for p in pool}
    for player in players:
        averages = get_player_per_game_stats(player, stats_key) or {}
        stats = {stat: number(averages.get(stat, averages.get('3PTM') if stat == '3PM' else None))
                 for stat in STAT_CATEGORIES if stat not in ('FT%', 'DD')}
        makes, attempts, percentage = ft_line(averages)
        stats.update({'FTM': makes, 'FTA': attempts, 'FT%': percentage, '_stats_key': stats_key})
        stats['dd'] = resolve_double_doubles(player, stats_key, peers)
        stats['DD'] = stats['dd']['value']
        player_stats[player] = stats
    # Baseline uses combined season/period makes and attempts, including the
    # projected GP weighting. Derive totals from per-game lines only with known
    # GP when ESPN omits both counts. Never assume 82 games or zero attempts.
    pool_totals = []
    for player in pool:
        record = getattr(player, 'stats', {}).get(stats_key, {})
        total, avg = record.get('total') or {}, record.get('avg') or {}
        if 'FTM' in total or 'FTA' in total:
            makes, attempts, _ = ft_line(total)
        else:
            makes, attempts, _ = ft_line(avg)
            gp = nonnegative(total.get('GP', avg.get('GP')))
            if gp is None or gp <= 0 or makes is None or attempts is None:
                makes = attempts = None
            else:
                makes, attempts = makes * gp, attempts * gp
        pool_totals.append((makes, attempts))
    baseline = None
    if pool_totals and all(m is not None and a is not None for m, a in pool_totals):
        attempts = sum(a for _, a in pool_totals)
        if attempts > 0:
            baseline = sum(m for m, _ in pool_totals) / attempts
    raw_stats['_ft_baseline'] = baseline
    for player, stats in player_stats.items():
        averages = get_player_per_game_stats(player, stats_key) or {}
        stats['FT impact'] = ft_impact(averages, baseline)
        if getattr(player, 'playerId', player.name) in raw_stats['_comparison_ids']:
            for stat in SCORING_CATEGORIES:
                if stats[stat] is not None:
                    raw_stats[stat].append(stats[stat])
    return player_stats, raw_stats


def add_double_doubles(player_stats, raw_stats):
    """Compatibility hook: DD is resolved during extraction, exactly once."""
    return None


def calculate_zscores(player_stats, raw_stats, year, stats_key):
    """Standardize the fixed pool; missing contributions make power incomplete."""
    distributions = {stat: (float(np.mean(raw_stats[stat])), float(np.std(raw_stats[stat])))
                     for stat in SCORING_CATEGORIES if raw_stats[stat]}
    result = {}
    for player, stats in player_stats.items():
        scores = {}
        for stat in SCORING_CATEGORIES:
            value = stats.get(stat)
            if value is None or stat not in distributions:
                # Preserve the other six categories' legacy neutral contribution,
                # while raw values and completeness still expose the missing input.
                scores[stat] = None if stat in ('FT impact', 'DD') else 0.0
            else:
                mean, std = distributions[stat]
                scores[stat] = (value - mean) / std if std > 0 else 0.0
        missing = [stat for stat in SCORING_CATEGORIES if stats.get(stat) is None or scores[stat] is None]
        power = sum(value for value in scores.values() if value is not None)
        record = getattr(player, 'stats', {}).get(f'{year}_projected', {})
        gp = nonnegative((record.get('total') or {}).get('GP', (record.get('avg') or {}).get('GP')))
        scores.update({'per_game_power': power if not missing else None,
                       'partial_power': power, 'score_complete': not missing,
                       'missing_contributions': missing, 'games_played': gp,
                       'season_power': power * gp / 82.0 if not missing and gp is not None else None,
                       'raw_stats': {k: v for k, v in stats.items() if not k.startswith('_') and k != 'dd'},
                       'dd': stats['dd'], 'ft_baseline': raw_stats['_ft_baseline'],
                       'comparison_pool_size': len(raw_stats['_comparison_ids']),
                       'dd_reference_count': len(raw_stats['DD'])})
        result[player] = scores
    return result


def calculate_player_zscores(players, stats_key=f'{YEAR}_projected', comparison_players=None):
    year = int(stats_key.split('_')[0])
    stats, raw = extract_player_stats(players, year, stats_key, comparison_players)
    return {player.name: scores for player, scores in calculate_zscores(stats, raw, year, stats_key).items()}


def power_sort_key(scores, field='per_game_power'):
    """Incomplete scores sort after complete scores; retain partial for inspection."""
    value = scores.get(field)
    return (value is not None, value if value is not None else scores.get('partial_power', float('-inf')))


def calculate_team_stats(team_player_zscores):
    """Average category contributions, plus raw FT% from combined makes/attempts."""
    result = {}
    for name, players in team_player_zscores.items():
        if name == 'Free Agents' or not players:
            continue
        totals = {}
        for stat in SCORING_CATEGORIES:
            values = [p.get(stat) for p in players.values()]
            totals[stat] = float(np.mean(values)) if all(v is not None for v in values) else None
        lines = [p.get('raw_stats', {}) for p in players.values()]
        valid = all(line.get('FTM') is not None and line.get('FTA') is not None for line in lines)
        totals['FTM'] = sum(line['FTM'] for line in lines) if valid else None
        totals['FTA'] = sum(line['FTA'] for line in lines) if valid else None
        totals['FT%'] = totals['FTM'] / totals['FTA'] if valid and totals['FTA'] > 0 else None
        totals['roster_size'] = len(players)
        totals['score_complete'] = all(p['score_complete'] for p in players.values())
        result[name] = totals
    return result


def build_team_dictionary(league, player_zscores, top_free_agents):
    result = {}
    for team in league.teams:
        result[team.team_name] = {p.name: player_zscores[p] for p in team.roster if p in player_zscores}
    result['Free Agents'] = {p.name: player_zscores[p] for p in top_free_agents if p in player_zscores}
    return result
