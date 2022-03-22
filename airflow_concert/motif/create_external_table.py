from debussy_framework.v2.operators.bigquery import BigQueryCreateExternalTableOperator

from airflow_concert.motif.motif_base import MotifBase
from airflow_concert.phrase.protocols import PCreateExternalTableMotif
from airflow_concert.entities.table import Table


class CreateExternalBigQueryTableMotif(MotifBase, PCreateExternalTableMotif):
    def __init__(
        self,
        config,
        table: Table,
        source_bucket_uri_prefix: str = None,
        destination_project_dataset_table: str = None,
        name=None
    ) -> None:
        self.table = table
        self.source_storage_uri_prefix = source_bucket_uri_prefix
        self.destination_table_uri = destination_project_dataset_table
        super().__init__(name=name, config=config)

    @property
    def table_resource(self):
        return {
            "type": "EXTERNAL",
                    "externalDataConfiguration": {
                        "hivePartitioningOptions": {
                            "mode": "AUTO",
                            "sourceUriPrefix": self.source_storage_uri_prefix,
                        },
                        "sourceFormat": "PARQUET",
                        "sourceUris": [f"{self.source_storage_uri_prefix}/*.parquet"],
                    },
        }

    def setup(
        self,
        source_bucket_uri_prefix: str,
        destination_project_dataset_table: str
    ):
        self.source_storage_uri_prefix = source_bucket_uri_prefix
        self.destination_table_uri = destination_project_dataset_table

    def create_landing_external_table(self, dag, task_group) -> BigQueryCreateExternalTableOperator:
        create_landing_external_table = BigQueryCreateExternalTableOperator(
            task_id=self.name,
            bucket=self.source_storage_uri_prefix,
            destination_project_dataset_table=self.destination_table_uri,
            table_resource=self.table_resource,
            dag=dag,
            task_group=task_group
        )
        return create_landing_external_table

    def build(self, dag, phrase_group):
        return self.create_landing_external_table(dag, phrase_group)
