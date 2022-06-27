import os
from airflow.configuration import conf

from debussy_concert.data_ingestion.config.rdbms_data_ingestion import ConfigRdbmsDataIngestion
from debussy_concert.data_ingestion.composition.feux_dartifice import FeuxDArtifice
from debussy_concert.core.service.injection import inject_dependencies
from debussy_concert.core.service.workflow.airflow import AirflowService


dags_folder = conf.get('core', 'dags_folder')
os.environ['DEBUSSY_CONCERT__DAGS_FOLDER'] = dags_folder  # of course you can set this on your system env var
env_file = f'{dags_folder}/examples/pixdict/environment.yaml'
composition_file = f'{dags_folder}/examples/pixdict/composition_15_minutes.yaml'
workflow_service = AirflowService()
config_composition = ConfigRdbmsDataIngestion.load_from_file(
    composition_config_file_path=composition_file,
    env_file_path=env_file)

inject_dependencies(workflow_service, config_composition)

debussy_composition = FeuxDArtifice()

dag = debussy_composition.auto_play()
