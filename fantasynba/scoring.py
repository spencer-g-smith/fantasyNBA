"""Shared FT and DD inputs. Missing values remain None, never observed zeroes."""
import math
from numbers import Real

DD_STATS = ('PTS', 'REB', 'AST', 'STL', 'BLK')
# Distances measure changes large enough to materially affect DD opportunities.
DD_SCALES = (5.0, 2.0, 2.0, 0.75, 0.75)
MIN_HISTORY_GAMES = 20
MIN_PEERS = 5
MAX_PEERS = 8
MAX_DISTANCE = 1.5


def number(value):
    return float(value) if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) else None


def nonnegative(value):
    value = number(value)
    return value if value is not None and value >= 0 else None


def ft_line(averages):
    """FTM/FTA are already per game. FT% is a fraction, not a percent number."""
    attempts = nonnegative(averages.get('FTA'))
    makes = nonnegative(averages.get('FTM'))
    if attempts == 0 and makes in (None, 0):
        return 0.0, 0.0, None
    if attempts is None or makes is None or makes > attempts:
        return None, attempts, number(averages.get('FT%'))
    percentage = number(averages.get('FT%'))
    if percentage is None or not 0 <= percentage <= 1:
        percentage = makes / attempts if attempts > 0 else None
    return makes, attempts, percentage


def ft_impact(averages, baseline):
    makes, attempts, _ = ft_line(averages)
    if attempts == 0 and makes == 0:
        return 0.0
    if baseline is None or makes is None or attempts is None:
        return None
    return makes - baseline * attempts


def dd_from_record(record):
    """Prefer DD totals/GP; use avg DD once, with consistency/range checks."""
    total, avg = record.get('total') or {}, record.get('avg') or {}
    gp = nonnegative(total.get('GP', avg.get('GP')))
    count = nonnegative(total.get('DD'))
    rate = nonnegative(avg.get('DD'))
    if gp is None or gp <= 0:
        return None
    if count is not None:
        if count > gp:
            return None
        converted = count / gp
        if rate is not None and not math.isclose(rate, converted, rel_tol=1e-3, abs_tol=1e-4):
            return None
        return converted
    return rate if rate is not None and rate <= 1 else None


def production(record):
    avg = record.get('avg') or {}
    values = [nonnegative(avg.get(stat)) for stat in DD_STATS]
    return values if all(v is not None for v in values) else None


def historical_record(player, year):
    """Latest usable observed season before the target, at most three years old."""
    for season in range(year - 1, year - 4, -1):
        record = getattr(player, 'stats', {}).get(f'{season}_total', {})
        if dd_from_record(record) is not None:
            return season, record
    return None, None


def peer_rate(values, peers, exclude_id):
    if values is None:
        return None, 0
    neighbors = []
    for player_id, historical, rate, gp in peers:
        if player_id == exclude_id:
            continue
        distance = math.sqrt(sum(((a - b) / scale) ** 2 for a, b, scale in zip(values, historical, DD_SCALES)) / 5)
        if distance <= MAX_DISTANCE:
            neighbors.append((distance, rate, gp))
    neighbors.sort(key=lambda row: row[0])
    neighbors = neighbors[:MAX_PEERS]
    if len(neighbors) < MIN_PEERS:
        return None, len(neighbors)
    weights = [min(gp, 82) / (0.25 + distance) ** 2 for distance, _, gp in neighbors]
    return sum(row[1] * w for row, w in zip(neighbors, weights)) / sum(weights), len(neighbors)


def identity(player):
    return getattr(player, 'playerId', player.name)


def build_dd_peers(players, year):
    peers = []
    for player in players:
        _, record = historical_record(player, year)
        if record is None:
            continue
        gp = nonnegative((record.get('total') or {}).get('GP', (record.get('avg') or {}).get('GP')))
        values = production(record)
        if gp >= MIN_HISTORY_GAMES and values is not None:
            peers.append((identity(player), values, dd_from_record(record), gp))
    return peers


def resolve_double_doubles(player, stats_key, peers=()):
    """Observed DD, verified direct projection, or an explicitly estimated rate.

    The estimate uses empirical DD rates of similar historical production lines,
    preserving the observed joint event rather than assuming stat independence.
    With history: shrink toward peers (20 pseudo-games), then add the peer-rate
    change from historical to projected production. No comparable peers -> missing.
    """
    year = int(stats_key.split('_')[0])
    record = getattr(player, 'stats', {}).get(stats_key, {})
    rate = dd_from_record(record)
    projected = stats_key.endswith('_projected')
    if rate is not None:
        return {'value': rate, 'source': 'espn_projection' if projected else 'espn_observed',
                'estimated': False, 'stat_key': stats_key, 'reason': None}
    if not projected:
        return {'value': None, 'source': 'missing', 'estimated': False,
                'stat_key': stats_key, 'reason': 'No valid observed DD and GP for this period'}
    # Unmodified ESPN projected records are trusted only for explicit DD, checked
    # against GP and avg above. TD is never substituted or added.
    current_rate, peer_count = peer_rate(production(record), peers, identity(player))
    season, history = historical_record(player, year)
    old_values = production(history) if history else None
    current_values = production(record)
    old_peer_rate, old_peer_count = peer_rate(old_values, peers, identity(player))
    if (current_rate is None or old_peer_rate is None) and history and old_values and current_values:
        gp = (history.get('total') or {}).get('GP', (history.get('avg') or {}).get('GP'))
        # Unique stars can have no comparable peers. Carry forward their own
        # measured joint DD rate only when the projected role remains close.
        stable = all(abs(new - old) <= max(0.5, 0.20 * old)
                     for new, old in zip(current_values, old_values))
        if gp >= MIN_HISTORY_GAMES and stable:
            return {'value': dd_from_record(history), 'source': 'estimated_history_stable_production',
                    'estimated': True, 'stat_key': stats_key, 'history_season': season,
                    'history_games': gp, 'history_rate': dd_from_record(history),
                    'peer_count': peer_count,
                    'reason': 'No adequate peers; carry forward observed DD/GP only when each projection changes by <= max(0.5 per game, 20%)'}
    if current_rate is None:
        return {'value': None, 'source': 'missing', 'estimated': True, 'stat_key': stats_key,
                'history_season': season, 'peer_count': peer_count,
                'reason': 'Fewer than five comparable historical production lines or missing projection'}
    if history is None:
        return {'value': current_rate, 'source': 'estimated_peers_no_history', 'estimated': True,
                'stat_key': stats_key, 'history_season': None, 'peer_count': peer_count,
                'reason': 'No usable NBA DD history; rookie or missing history (not an observed zero)'}
    if old_peer_rate is None:
        return {'value': None, 'source': 'missing', 'estimated': True, 'stat_key': stats_key,
                'history_season': season, 'reason': 'Historical production has insufficient comparable peers'}
    gp = (history.get('total') or {}).get('GP', (history.get('avg') or {}).get('GP'))
    weight = gp / (gp + 20.0)
    shrunk_history = weight * dd_from_record(history) + (1 - weight) * old_peer_rate
    rate = max(0.0, min(1.0, shrunk_history + current_rate - old_peer_rate))
    return {'value': rate, 'source': 'estimated_history_adjusted', 'estimated': True,
            'stat_key': stats_key, 'history_season': season, 'history_rate': dd_from_record(history),
            'history_games': gp, 'peer_count': peer_count, 'history_peer_count': old_peer_count,
            'reason': 'Historical DD/GP shrunk by 20 pseudo-games; empirical production adjustment'}
