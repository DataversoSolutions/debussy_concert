#  from airflow import DAG  # noqa: F401
from airflow_concert.composition.vivaldi import Vivaldi
from airflow.configuration import conf

dags_folder = conf.get('core', 'dags_folder')
env_file = f'{dags_folder}/examples/vivaldi_four_seasons/environment.yaml'
integration_file = f'{dags_folder}/examples/vivaldi_four_seasons/integration.yaml'

vivaldi = Vivaldi.crate_from_yaml(environment_yaml_filepath=env_file, integration_yaml_filepath=integration_file)
four_seasons_movement = vivaldi.four_seasons
dag = vivaldi.play(four_seasons_movement)
