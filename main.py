import logging
import sys

from config import DEBUG, EXPORT_FOLDER, ODDS_API_KEY
from model import Model
import argparse

parser = argparse.ArgumentParser(description='Run the model.')
parser.add_argument('-b', '--boostrap_samples', default=100_000, help='Set # of boostrap samples')
parser.add_argument('-n', '--n_simulated_games', default=10_000, help='Set # of simulated games')
args = parser.parse_args()
bootstrap_samples = int(args.boostrap_samples)
n_simulated_games = int(args.n_simulated_games)

#logging settings
root = logging.getLogger()
root.setLevel(logging.DEBUG if DEBUG else logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)

model = Model(export_folder=EXPORT_FOLDER, odds_api_key=ODDS_API_KEY)

model.run_model(
    bootstrap_samples=bootstrap_samples,
    n_simulated_games=n_simulated_games
)