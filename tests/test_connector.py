"""Local connector response checks using synthetic inputs; no network calls."""
import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

import main
from fantasynba.players import comparison_pool_ids
from fantasynba.stats import calculate_player_zscores, calculate_team_stats
from fantasynba.display import (display_player_scores, display_team_rankings,
                               display_team_statistics, display_stat_rankings,
                               display_overall_rankings)


class Player(SimpleNamespace):
    __hash__ = object.__hash__


def synthetic_players():
    players = []
    for index, player_id in enumerate(comparison_pool_ids()):
        averages = {
            'PTS': 18. + index % 9,
            'REB': 6. + index % 5,
            'AST': 3. + index % 4,
            'STL': .8 + (index % 4) * .2,
            'BLK': .5 + (index % 5) * .2,
            '3PM': 1. + (index % 6) * .3,
            'FTM': 2. + (index % 8) * .5,
            'FTA': 4. + (index % 8) * .5,
            'GP': 70,
        }
        if index == 0:
            # A unique veteran whose projected production matches history.
            averages.update(PTS=55., REB=20., AST=15., STL=3., BLK=4.)
        elif index == 1:
            # No history or comparable peers: DD must remain unavailable.
            averages.update(PTS=80., REB=35., AST=25., STL=5., BLK=7.)
        elif index == 3:
            averages['3PM'] = None
        stats = {'2027_projected': {'avg': averages, 'total': {'GP': 70}}}
        if index not in (1, 2):
            stats['2026_total'] = {
                'avg': dict(averages, GP=50),
                'total': {'DD': 5 + index % 30, 'GP': 50},
            }
        players.append(Player(name=f'Player {index}', playerId=player_id,
                              stats=stats, proTeam='NBA'))
    return players


class Connector(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.players = synthetic_players()
        self.team = SimpleNamespace(team_name='Test Team', roster=self.players[:3])
        self.league = SimpleNamespace(teams=[self.team], currentMatchupPeriod=1)
        self.scores = calculate_player_zscores(self.players)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('main.League', return_value=self.league))
        self.stack.enter_context(patch('main.get_league_players', return_value=(
            self.players, self.players[:3], self.players[3:])))
        self.stack.enter_context(patch('main.get_matchup_schedule', return_value={1: [1]}))
        self.stack.enter_context(patch('main.get_player_schedule', return_value=[]))

    async def test_player_exposes_ft_and_dd_sources(self):
        result = await main.get_player_stats.fn('Player 0', 'projected')
        score = self.scores['Player 0']
        self.assertEqual(result['per_game_power'], score['per_game_power'])
        self.assertEqual(result['zscores']['FT impact'], score['FT impact'])
        self.assertNotIn('FT%', result['zscores'])
        self.assertIn('FTA', result['stats'])
        self.assertEqual(result['dd']['source'], 'estimated_history_stable_production')
        json.dumps(result, allow_nan=False)

    async def test_free_agents_keep_full_reference_pool(self):
        result = await main.get_top_free_agents.fn('projected', 1)
        self.assertEqual(result['count'], 10)
        for row in result['free_agents']:
            self.assertEqual(row['per_game_power'], self.scores[row['player_name']]['per_game_power'])
            self.assertEqual(row['comparison_pool_size'], 100)
            self.assertIn('dd', row)

    async def test_roster_scoring_matches_player_scoring(self):
        result = await main.get_team_roster.fn('Test Team', 'projected', 1)
        self.assertEqual(result['roster_count'], 3)
        for row in result['roster']:
            self.assertEqual(row['per_game_power'], self.scores[row['player_name']]['per_game_power'])
            self.assertEqual(row['comparison_pool_size'], 100)

    async def test_missing_dd_response_is_incomplete(self):
        result = await main.get_player_stats.fn('Player 1', 'projected')
        self.assertIsNone(result['per_game_power'])
        self.assertIsNone(result['stats']['DD'])
        self.assertFalse(result['score_complete'])
        self.assertIn('DD', result['missing_contributions'])


class ScoringRegression(unittest.TestCase):
    def test_six_counting_categories_keep_population_zscores(self):
        players = synthetic_players()
        scores = calculate_player_zscores(players)
        self.assertEqual(len(scores), 100)
        for category in ('PTS', 'REB', 'AST', 'STL', 'BLK', '3PM'):
            available = [player.stats['2027_projected']['avg'][category]
                         for player in players
                         if player.stats['2027_projected']['avg'][category] is not None]
            mean, std = np.mean(available), np.std(available)
            for player in players:
                value = player.stats['2027_projected']['avg'][category]
                expected = (value - mean) / std if value is not None and std else 0.
                self.assertAlmostEqual(scores[player.name][category], expected, places=12)
        for score in scores.values():
            if score['score_complete']:
                contributions = sum(score[category] for category in (
                    'PTS', 'REB', 'AST', 'STL', 'BLK', '3PM', 'FT impact', 'DD'))
                self.assertAlmostEqual(score['per_game_power'], contributions, places=12)

    def test_display_handles_incomplete_scores_and_labels_units(self):
        scores = calculate_player_zscores(synthetic_players())
        teams = {'Test Team': scores, 'Free Agents': {}}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            display_player_scores(teams, [SimpleNamespace(team_name='Test Team')])
            display_team_rankings(teams)
            totals = calculate_team_stats(teams)
            display_team_statistics(totals, 'overall')
            display_stat_rankings(totals)
            display_overall_rankings(totals)
        self.assertIn('FT impact', output.getvalue())
        self.assertIn('N/A', output.getvalue())
        self.assertIn('estimated_peers_no_history', output.getvalue())
