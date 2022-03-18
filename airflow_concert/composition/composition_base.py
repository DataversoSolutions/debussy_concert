from typing import Callable, TypeVar, List, Protocol, Sequence

from airflow import DAG

from airflow_concert.movement.movement_base import PMovement
from airflow_concert.config.config_composition import ConfigComposition
from airflow_concert.service.tables.tables import TablesService
from airflow_concert.entities.table import Table


class PComposition(Protocol):
    config: ConfigComposition
    tables_service: TablesService

    def play(self, *args, **kwargs) -> DAG:
        pass

    def multi_play(self, *args, **kwargs) -> Sequence[DAG]:
        pass

    def build_multi_dag(self, movement_builder: Callable[[Table], PMovement]) -> Sequence[DAG]:
        pass

    def build(self, movement_builder: Callable[[Table], PMovement]) -> DAG:
        pass


class CompositionBase(PComposition):
    def __init__(self, config: ConfigComposition):
        self.config = config
        self.tables_service = TablesService.create_from_dict(config.tables)

    @classmethod
    def create_from_yaml(cls, environment_config_yaml_filepath, composition_config_yaml_filepath) -> PComposition:
        config = ConfigComposition.load_from_file(
            composition_config_file_path=composition_config_yaml_filepath,
            env_file_path=environment_config_yaml_filepath
        )
        return cls(config)

    def play(self, *args, **kwargs):
        return self.build(*args, **kwargs)

    def multi_play(self, *args, **kwargs):
        return self.build_multi_dag(*args, **kwargs)

    def build_multi_dag(self, movement_builder: Callable[[Table], PMovement]) -> List[DAG]:
        from airflow import DAG
        dags = list()
        for table in self.tables_service.tables():
            name = self.config.dag_parameters.dag_id + '.' + table.name
            kwargs = {**self.config.dag_parameters}
            del kwargs['dag_id']
            dag = DAG(dag_id=name, **kwargs)
            movement_builder(table).play(dag=dag)
            dags.append(dag)
        return dags

    def build(self, movement_builder: Callable[[Table], PMovement]) -> DAG:
        dag = DAG(**self.config.dag_parameters)

        for table in self.tables_service.tables():
            movement = movement_builder(table)
            movement.build(dag=dag)
        return dag
