from difflib import SequenceMatcher

import numpy as np
import pandas as pd
from nba_api.stats.endpoints import (commonplayerinfo, leaguegamefinder,
                                     playergamelog, shotchartdetail)
from nba_api.stats.static import players, teams


def find_player_id(player_name):

    """
    Finds the player id for a given player name
    :param player_name: The player name to find the id for
    :return: The player id
    """

    possible_matches = players.find_players_by_full_name(player_name)

    if len(possible_matches) == 1:
        return str(possible_matches[0]['id'])
    elif len(possible_matches) > 1:
        idx_closest_match = np.argmax([SequenceMatcher(None, player_name, match['full_name']).ratio() for match in possible_matches])
        return str(possible_matches[idx_closest_match]['id'])
    else:
        return np.nan

def get_player_game_log(player_id: str, season: str):
    
    if not type(player_id) == str:
        raise TypeError('player_id must be a string')

    game_log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    game_log_df = game_log.get_data_frames()[0]

    return game_log_df

def get_player_shot_loc_data(player_name: str, team_id: int = None, context_measure_simple: str = 'FGA'):

    """
    Gets the shot location data for a given player
    :param player_name: The name of the player to get the shot data for
    :param season: The season to get the shot data for
    :param team_id: The team id to get the shot data for
    :param context_measure_simple: Types of shots to get (eg. FGA, FG3A, etc.)
    :return: A pandas dataframe containing the shot data
    """

    player_id = players.find_players_by_full_name(player_name)[0]['id']
    player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
    team_id = player_info.get_data_frames()[0]['TEAM_ID'][0]
    shot_chart = shotchartdetail.ShotChartDetail(player_id=player_id, team_id=team_id, context_measure_simple=context_measure_simple)
    df = pd.concat(shot_chart.get_data_frames())

    return df

def get_league_shot_loc_data(season:str='2022', context_measure_simple: str = 'FGA'):
    """
    Get league shot data
    :param season: The season to get the shot data for
    :param context_measure_simple: Types of shots to get (eg. FGA, FG3A, etc.)
    :return: A pandas dataframe containing the shot data
    """

    def find_team_abrv(team_name):
        try:
            abrv = teams.find_teams_by_full_name(team_name.strip())[0]['abbreviation']
            return abrv
        except IndexError:
            return np.nan
        
    def find_matchup(row):
        game_df = games_df[games_df['GAME_ID'] == str(row['GAME_ID'])]
        matchup = game_df['MATCHUP'].values[0]
        return matchup
    
    def find_defense(row):
        team_abrv = row['TEAM_ABRV']
        team_a = row['MATCHUP'].split()[0]
        team_b = row['MATCHUP'].split()[-1]
        if team_abrv != team_a:
            return team_a
        if team_abrv != team_b:
            return team_b
        
    games_df = pd.concat(leaguegamefinder.LeagueGameFinder().get_data_frames())
    league_shots = shotchartdetail.ShotChartDetail(
        player_id=0,
        team_id=0,
        season_type_all_star='Regular Season',
        context_measure_simple = 'FG3A'
    )
    league_df = pd.concat(league_shots.get_data_frames())
    league_df = league_df.loc[(league_df['GRID_TYPE'] == 'Shot Chart Detail'), ['GAME_ID', 'TEAM_NAME', 'TEAM_ID', 'LOC_X', 'LOC_Y', 'SHOT_MADE_FLAG']]
    league_df['TEAM_ABRV'] = league_df['TEAM_NAME'].apply(find_team_abrv)

    matchups_table = league_df[['TEAM_ID', 'GAME_ID']].groupby('GAME_ID').size().reset_index().drop(0, axis=1)
    matchups_table['MATCHUP'] = matchups_table.apply(find_matchup, axis=1)

    league_df = league_df.merge(matchups_table, on='GAME_ID')

    league_df['DEF'] = league_df.apply(find_defense, axis=1)

    return league_df[['DEF', 'LOC_X', 'LOC_Y', 'SHOT_MADE_FLAG']]