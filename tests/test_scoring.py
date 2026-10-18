import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from fantasynba.scoring import (ft_line, ft_impact, dd_from_record, resolve_double_doubles,
                               build_dd_peers)
from fantasynba.stats import (calculate_player_zscores, extract_player_stats, calculate_zscores,
                             add_double_doubles, calculate_team_stats, SCORING_CATEGORIES)
from fantasynba.players import attach_espn_records, get_league_players, comparison_pool_ids
from fantasynba.matchups import calculate_team_matchup_stats, compare_teams, optimize_lineup


class Player:
    def __init__(self, name, averages=None, history=None, total=None):
        self.name = name
        self.playerId = name
        self.position = 'C'
        self.stats = {'2027_projected': {'avg': averages or {}, 'total': total or {'GP': 70}}}
        if history is not None:
            self.stats['2026_total'] = history


def production(**overrides):
    values = dict(PTS=20., REB=8., AST=4., STL=1., BLK=1., **{'3PM': 2., 'FT%': .8, 'FTM': 4., 'FTA': 5., 'GP': 70})
    values.update(overrides)
    return values


def record(dd=20, gp=50, **overrides):
    return {'total': {'DD': dd, 'GP': gp}, 'avg': production(**overrides)}


def peers():
    return [Player(str(i), production(), record(dd=i * 4, gp=50, PTS=18 + i * .4)) for i in range(8)]


class FreeThrows(unittest.TestCase):
    def test_volume_changes_impact(self):
        self.assertAlmostEqual(ft_impact({'FTM': .9, 'FTA': 1}, .8), .1)
        self.assertAlmostEqual(ft_impact({'FTM': 9., 'FTA': 10}, .8), 1.)
        self.assertAlmostEqual(ft_impact({'FTM': 5., 'FTA': 10}, .8), -3.)

    def test_zero_attempts(self):
        self.assertEqual(ft_impact({'FTM': 0., 'FTA': 0.}, .8), 0.)
        self.assertEqual(ft_impact({'FTA': 0.}, None), 0.)
        self.assertIsNone(ft_line({'FTA': 0.})[2])

    def test_missing_invalid_attempts_and_makes(self):
        for line in ({'FTM': 2}, {'FTA': 4}, {'FTM': 2, 'FTA': None}, {'FTM': 2, 'FTA': float('nan')}, {'FTM': 5, 'FTA': 4}):
            self.assertIsNone(ft_impact(line, .8))

    def test_baseline_weights_attempts_and_sum_impacts_zero(self):
        a = Player('A', production(FTM=.9, FTA=1, DD=.1))
        b = Player('B', production(FTM=5., FTA=10, DD=.3))
        scores = calculate_player_zscores([a,b], comparison_players=[a,b])
        self.assertAlmostEqual(scores['A']['ft_baseline'], 5.9 / 11.)
        self.assertAlmostEqual(sum(s['raw_stats']['FT impact'] for s in scores.values()), 0.)
        self.assertNotIn('FT%', scores['A'])
        self.assertEqual(scores['A']['raw_stats']['FTA'], 1)

    def test_baseline_uses_projected_season_totals(self):
        a = Player('A', production(FTM=.9, FTA=1, DD=.1), total={'FTM': 9., 'FTA': 10., 'GP': 10})
        b = Player('B', production(FTM=5., FTA=10, DD=.3), total={'FTM': 350., 'FTA': 700., 'GP': 70})
        result = calculate_player_zscores([a,b], comparison_players=[a,b])
        self.assertAlmostEqual(result['A']['ft_baseline'],359 / 710)

    def test_missing_pool_attempts_invalidate_baseline_and_power(self):
        a = Player('A', production(DD=.1))
        b = Player('B', production(FTA=None, DD=.3))
        scores = calculate_player_zscores([a,b], comparison_players=[a,b])
        self.assertIsNone(scores['A']['ft_baseline'])
        self.assertIsNone(scores['B']['per_game_power'])
        self.assertFalse(scores['B']['score_complete'])
        self.assertIn('FT impact',scores['B']['missing_contributions'])

    def test_team_ft_percentage_is_combined_makes_over_attempts(self):
        a = Player('A',production(FTM=1.,FTA=1.,DD=.1))
        b = Player('B',production(FTM=5.,FTA=10.,DD=.3))
        scores = calculate_player_zscores([a,b],comparison_players=[a,b])
        result = calculate_team_stats({'team':scores})['team']
        self.assertAlmostEqual(result['FT%'],6/11)
        self.assertNotAlmostEqual(result['FT%'],.75)


class DoubleDoubles(unittest.TestCase):
    def test_total_conversion_and_avg_not_divided_twice(self):
        self.assertEqual(dd_from_record(record(20,50)),.4)
        self.assertEqual(dd_from_record({'total':{'GP':50},'avg':{'DD':.4,'GP':50}}),.4)
        self.assertEqual(dd_from_record({'total':{'DD':20,'GP':50},'avg':{'DD':.4}}),.4)

    def test_invalid_or_missing_not_zero(self):
        for r in ({},record(0,0),record(51,50),{'total':{'TD':20,'GP':50}}, {'total':{'DD':20,'GP':50},'avg':{'DD':.8}}):
            self.assertIsNone(dd_from_record(r))
        self.assertEqual(dd_from_record(record(0,50)),0.)

    def test_historical_uses_observed_not_projection(self):
        p=Player('A',production(DD=.8),record(10,50))
        result=resolve_double_doubles(p,'2026_total')
        self.assertEqual(result['value'],.2)
        self.assertEqual(result['source'],'espn_observed')
        self.assertFalse(result['estimated'])

    def test_missing_historical_never_falls_back_to_projection(self):
        p=Player('A',production(DD=.8))
        self.assertIsNone(resolve_double_doubles(p,'2026_total')['value'])

    def test_direct_projection_preferred(self):
        p=Player('A',production(DD=.6),record(10,50),{'DD':42,'GP':70})
        result=resolve_double_doubles(p,'2027_projected',build_dd_peers(peers(),2027))
        self.assertEqual(result['value'],.6)
        self.assertEqual(result['source'],'espn_projection')
        self.assertFalse(result['estimated'])

    def test_projection_td_not_substituted(self):
        p=Player('rookie',production(TD=.6))
        self.assertIsNone(resolve_double_doubles(p,'2027_projected')['value'])

    def test_history_adjusted_fallback(self):
        p=Player('veteran',production(),record(30,60))
        result=resolve_double_doubles(p,'2027_projected',build_dd_peers(peers(),2027))
        self.assertEqual(result['source'],'estimated_history_adjusted')
        self.assertTrue(result['estimated'])
        self.assertGreater(result['value'],0.)
        self.assertLess(result['value'],1.)

    def test_projection_change_moves_history_estimate(self):
        population=peers(); ref=build_dd_peers(population,2027)
        p=Player('veteran',production(PTS=18),record(20,50,PTS=18))
        low=resolve_double_doubles(p,'2027_projected',ref)['value']
        p.stats['2027_projected']['avg']['PTS']=21
        high=resolve_double_doubles(p,'2027_projected',ref)['value']
        self.assertGreater(high,low)

    def test_rookie_or_missing_history_explicit_peer_estimate(self):
        p=Player('rookie',production())
        result=resolve_double_doubles(p,'2027_projected',build_dd_peers(peers(),2027))
        self.assertEqual(result['source'],'estimated_peers_no_history')
        self.assertTrue(result['estimated'])
        self.assertIsNone(result['history_season'])

    def test_no_defensible_estimate_marks_power_incomplete(self):
        p=Player('rookie',production())
        result=calculate_player_zscores([p],comparison_players=[p])['rookie']
        self.assertIsNone(result['DD'])
        self.assertIsNone(result['per_game_power'])
        self.assertEqual(result['missing_contributions'],['DD'])

    def test_unique_stable_veteran_can_use_own_history(self):
        p=Player('star',production(PTS=27),record(40,60,PTS=26))
        result=resolve_double_doubles(p,'2027_projected')
        self.assertEqual(result['source'],'estimated_history_stable_production')
        self.assertAlmostEqual(result['value'],40/60)

    def test_unique_veteran_major_change_cannot_carry_forward(self):
        p=Player('star',production(PTS=40),record(40,60,PTS=20))
        self.assertIsNone(resolve_double_doubles(p,'2027_projected')['value'])

    def test_unreliable_projection_uses_fallback(self):
        p=Player('vet',production(DD=.8),record(20,50),{'DD':90,'GP':70})
        result=resolve_double_doubles(p,'2027_projected',build_dd_peers(peers(),2027))
        self.assertTrue(result['source'].startswith('estimated_'))


class Integration(unittest.TestCase):
    def test_both_scoring_paths_agree(self):
        ps=peers()
        named=calculate_player_zscores(ps,comparison_players=ps)
        stats,raw=extract_player_stats(ps,2027,'2027_projected',comparison_players=ps)
        add_double_doubles(stats,raw)
        keyed=calculate_zscores(stats,raw,2027,'2027_projected')
        self.assertEqual(named,{p.name:s for p,s in keyed.items()})

    def test_drafted_filter_does_not_change_baseline(self):
        ps=peers(); pool=ps[:6]
        before=calculate_player_zscores(ps,comparison_players=pool)
        # Ownership changes while the complete reference pool remains available.
        ps[0].onTeamId=1
        after=calculate_player_zscores(list(reversed(ps)),comparison_players=pool)
        self.assertEqual(before,after)

    def test_all_three_util_slots_accumulate(self):
        ps=[Player(str(i),production(DD=.2)) for i in range(10)]
        for p in ps:p.position='PG,SG,SF,PF,C'
        scores=calculate_player_zscores(ps,comparison_players=ps)
        lineup=optimize_lineup(ps,scores)
        self.assertEqual(len([x for x in lineup.values() if x]),10)

    def test_matchup_reuses_dd_and_combines_ft(self):
        ps=[Player('A',production(FTM=1.,FTA=1.,DD=.2)),Player('B',production(FTM=5.,FTA=10.,DD=.4))]
        scores=calculate_player_zscores(ps,comparison_players=ps)
        team=SimpleNamespace(roster=ps)
        league=SimpleNamespace(matchup_ids={1:[1,2]})
        with patch('fantasynba.matchups.get_players_playing_on_date',return_value=ps):
            result=calculate_team_matchup_stats(team,1,league,scores)
        self.assertAlmostEqual(result['FT%'],6/11)
        self.assertAlmostEqual(result['DD'],1.2)
        self.assertEqual(result['games_played'],4)

    def test_matchup_missing_ft_and_dd_do_not_count_as_zero(self):
        p=Player('A',production(FTA=None))
        scores=calculate_player_zscores([p],comparison_players=[p])
        with patch('fantasynba.matchups.get_players_playing_on_date',return_value=[p]):
            result=calculate_team_matchup_stats(SimpleNamespace(roster=[p]),1,SimpleNamespace(matchup_ids={1:[1]}),scores)
        self.assertIsNone(result['DD'])
        self.assertIsNone(result['FT%'])
        self.assertFalse(result['score_complete'])
        winners,_,_=compare_teams('A',result,'B',dict(result,DD=2))
        self.assertEqual(winners['DD'],'Unavailable')

    def test_raw_source_mapping_preserves_history(self):
        p=Player('A')
        attach_espn_records(p,{'player':{'stats':[
            {'seasonId':2026,'statSourceId':0,'statSplitTypeId':0,'stats':{'37':20,'38':5,'42':50,'15':100,'16':125},'averageStats':{'37':.4,'38':.1,'42':50,'15':2,'16':2.5}},
            {'seasonId':2027,'statSourceId':1,'statSplitTypeId':0,'stats':{'37':35,'42':70},'averageStats':{'37':.5,'42':70}}]}})
        self.assertEqual(resolve_double_doubles(p,'2026_total')['value'],.4)
        self.assertEqual(resolve_double_doubles(p,'2027_projected')['value'],.5)
        self.assertEqual(p.stats['2026_total']['avg']['FTM'],2)

    def test_pool_snapshot_is_100_unique_players(self):
        self.assertEqual(len(set(comparison_pool_ids())),100)

    def test_league_fetch_keeps_pool_when_free_agents_change(self):
        ids=comparison_pool_ids()
        ps=[Player(str(i),production(DD=.2)) for i in range(100)]
        for p,player_id in zip(ps,ids):p.playerId=player_id
        entries=[{'player':{'id':p.playerId,'stats':[]}} for p in ps]
        class League:
            def __init__(self):
                self.teams=[SimpleNamespace(roster=ps)]
                self.espn_request=SimpleNamespace(league_get=lambda **kwargs:{'players':entries})
                self.free_agents=lambda **kwargs:[]
        result,roster,available=get_league_players(League(),2027)
        self.assertEqual(len(result),100)
        scores=calculate_player_zscores(result)
        self.assertEqual(scores[ps[0].name]['comparison_pool_size'],100)


if __name__ == '__main__':
    unittest.main()
