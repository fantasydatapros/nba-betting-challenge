import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from sklearn.mixture import GaussianMixture as GMM
from sklearn.model_selection import GridSearchCV
from tqdm import trange

from model.nba_api_helpers import (get_league_shot_loc_data,
                                   get_player_shot_loc_data)


class ThreesModel:

    """
    Model class for simulating three point shots for given player and opponent defense
    """

    @staticmethod
    def run_threes_model(
            player_name:str="Buddy Hield", 
            opponent:str="BOS",
            n_components:int=5, 
            bootstrap_samples:int=100_000,
            n_simulated_games:int=200_000,
            plot:bool=True
        ):

        """
        Main method to run the model
        :param player_name: The name of the player to simulate shots for
        :param opponent: The opponent defense to simulate shots against
        :param n_components: The number of clusters to use for the GMM
        :param bootstrap_samples: The number of bootstrap samples to use for the simulation
        :param n_simulated_games: The number of simulated games to run
        :param plot: Whether to plot the results
        :return: A pandas dataframe containing the results
        """

        player_df = get_player_shot_loc_data(player_name, context_measure_simple='FG3A')
        threes = player_df.loc[:, ['GAME_ID', 'LOC_X', 'LOC_Y', 'SHOT_MADE_FLAG', 'SHOT_ATTEMPTED_FLAG']]
        threes = threes.dropna()

        threes['SHOT_MADE_FLAG'] = threes['SHOT_MADE_FLAG'].astype(np.int64)
        
        threes_train_xy = threes[['LOC_X', 'LOC_Y']].values.reshape(-1, 2)
        fga_per_game_data = threes.groupby('GAME_ID')['SHOT_ATTEMPTED_FLAG'].count().values

        #get league shot data
        
        league_df = get_league_shot_loc_data(context_measure_simple='FG3A')
        league_test_xy = league_df[['LOC_X', 'LOC_Y']].values.reshape(-1, 2)

        param_grid = {
            "n_components": range(3, 15),
            "covariance_type": ["spherical", "tied", "diag", "full"],
        }
        grid_search = GridSearchCV(
            GMM(), param_grid=param_grid, scoring=lambda estimator, x: -estimator.bic(x)
        )

        grid_search.fit(threes_train_xy)
        
        covariance_type = grid_search.best_params_['covariance_type']
        n_components = grid_search.best_params_['n_components']
        model = GMM(n_components=n_components, covariance_type=covariance_type, random_state=0).fit(threes_train_xy)
        model_labels_ = model.predict(threes_train_xy)

        league_model_labels_ = model.predict(league_test_xy)
        league_df['cluster'] = league_model_labels_
        
        #filter for opponent after assigning clusters
        opponent_df = league_df.loc[league_df['DEF'] == opponent]
        
        #create a dataframe from the cluster data dictionary
        cluster_df = pd.DataFrame({
            'shot_made': threes['SHOT_MADE_FLAG'],
            'cluster': model_labels_
        })

        #shooting percentage by cluster
        fg_percent_by_cluster = pd.DataFrame(cluster_df.groupby('cluster')['shot_made'].value_counts(normalize=True)).rename({'shot_made': 'fg_percent'}, axis=1).reset_index()
        fg_percent_by_cluster = fg_percent_by_cluster.loc[fg_percent_by_cluster['shot_made'] == 1].drop('shot_made', axis=1)['fg_percent']

        #league fg% by cluster
        league_fg_percent_by_cluster = pd.DataFrame(league_df.groupby('cluster')['SHOT_MADE_FLAG'].value_counts(normalize=True)).rename({'SHOT_MADE_FLAG': 'fg_percent'}, axis=1).reset_index()
        league_fg_percent_by_cluster = league_fg_percent_by_cluster.loc[league_fg_percent_by_cluster['SHOT_MADE_FLAG'] == 1].drop('SHOT_MADE_FLAG', axis=1)['fg_percent']

        #opponent def fg% by cluster
        opponent_fg_percent_by_cluster = pd.DataFrame(opponent_df.groupby('cluster')['SHOT_MADE_FLAG'].value_counts(normalize=True)).rename({'SHOT_MADE_FLAG': 'fg_percent'}, axis=1).reset_index()
        opponent_fg_percent_by_cluster = opponent_fg_percent_by_cluster.loc[opponent_fg_percent_by_cluster['SHOT_MADE_FLAG'] == 1].drop('SHOT_MADE_FLAG', axis=1)['fg_percent']
        
        #opponent ratings
        def_adjustment = opponent_fg_percent_by_cluster / league_fg_percent_by_cluster

        #bootstrap resample from FGA data to find normal distribution fo estimated mean FGA per game
        fga_per_game_est = [np.random.choice(fga_per_game_data, size=len(fga_per_game_data), replace=True).mean() for _ in range(bootstrap_samples)]
        fga_per_game_est_mean = np.mean(fga_per_game_est)
        fga_per_game_est_std = np.std(fga_per_game_est)

        fg3m_s = []
        #simulate n_simulations games
        for _ in trange(n_simulated_games, desc=f'Simulating 3PM outcomes for {player_name} vs {opponent}...'):

            #simulate FGA
            fga_i = np.random.poisson(np.random.normal(fga_per_game_est_mean, fga_per_game_est_std))

            if fga_i == 0:
                fg3m_s.append(0)
                continue

            #simulate shot locations based off density of where shots are taken
            sampled_shot_locs = model.sample(fga_i)[0]

            #apply weighting to each shot based off cluster
            weighted_fg_percent = np.dot(
                fg_percent_by_cluster.values * def_adjustment, model.predict_proba(sampled_shot_locs).T
            )

            fgm_i = np.vectorize(np.random.binomial)(1, weighted_fg_percent)

            fg3m_s.append(fgm_i.sum())

        if plot:
            sns.set_style('darkgrid')
            sns.set_context("poster")
            plt.figure(figsize=(10, 10))
            sns.ecdfplot(fg3m_s, stat='proportion', color='red', alpha=0.5)
            plt.title(f'Results of {n_simulated_games} simulated games for {player_name}')
            plt.xlabel('3PM')
            plt.ylabel('Density')
            plt.show()

        return np.array(fg3m_s)