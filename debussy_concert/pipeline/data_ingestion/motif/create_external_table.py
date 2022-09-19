from airflow.providers.google.cloud.operators.bigquery import (
    BigQueryCreateExternalTableOperator,
)

from debussy_concert.core.motif.motif_base import MotifBase
from debussy_concert.core.phrase.protocols import PCreateExternalTableMotif


class CreateExternalBigQueryTableMotif(MotifBase, PCreateExternalTableMotif):
    def __init__(self, gcp_conn_id="google_cloud_default", name=None) -> None:
        super().__init__(name=name)
        self.gcp_conn_id = gcp_conn_id

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
        self, source_bucket_uri_prefix: str, destination_project_dataset_table: str
    ):
        self.source_storage_uri_prefix = source_bucket_uri_prefix
        self.destination_table_uri = destination_project_dataset_table
        return self

    def create_raw_vault_external_table(
        self, dag, task_group
    ) -> BigQueryCreateExternalTableOperator:
        create_raw_vault_external_table = BigQueryCreateExternalTableOperator(
            task_id=self.name,
            bucket=self.source_storage_uri_prefix,
            destination_project_dataset_table=self.destination_table_uri,
            table_resource=self.table_resource,
            dag=dag,
            task_group=task_group,
            bigquery_conn_id=self.gcp_conn_id,
        )
        return create_raw_vault_external_table

    def build(self, dag, phrase_group):
        return self.create_raw_vault_external_table(dag, phrase_group)
