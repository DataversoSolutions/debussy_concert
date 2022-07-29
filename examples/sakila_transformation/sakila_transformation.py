import os

from airflow.configuration import conf
from debussy_concert.pipeline.transform.config.transform import ConfigTransformComposition
from debussy_concert.pipeline.transform.composition.dbt_transformation import DbtTransformationComposition 

from debussy_concert.core.service.injection import inject_dependencies
from debussy_concert.core.service.workflow.airflow import AirflowService


dags_folder = conf.get('core', 'dags_folder')
os.environ['DEBUSSY_CONCERT__DAGS_FOLDER'] = dags_folder
os.environ['PARTICIPANT_WINDOW_START'] = "{{ execution_date.strftime('%Y-%m-%d 00:00:00') }}"
os.environ['PARTICIPANT_WINDOW_END'] = "{{ next_execution_date.strftime('%Y-%m-%d 00:00:00') }}"

workflow_service = AirflowService()
env_file = f'{dags_folder}/examples/sakila_transformation/environment.yaml'
composition_file = f'{dags_folder}/examples/sakila_transformation/composition.yaml'
config_composition = ConfigTransformComposition.load_from_file(
    composition_config_file_path=composition_file,
    env_file_path=env_file
)

inject_dependencies(workflow_service, config_composition)

debussy_composition = DbtTransformationComposition()
movement_builder = debussy_composition.dbt_transformation_builder
dag = debussy_composition.build(movement_builder)
