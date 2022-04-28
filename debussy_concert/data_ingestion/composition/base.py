from debussy_concert.data_ingestion.config.base import ConfigDataIngestionBase
from debussy_concert.data_ingestion.config.movement_parameters.time_partitioned import TimePartitionedDataIngestionMovementParameters

from debussy_concert.core.composition.composition_base import CompositionBase
from debussy_concert.data_ingestion.movement.data_ingestion import DataIngestionMovement


from debussy_concert.data_ingestion.phrase.landing_to_raw import LandingStorageLoadToDataWarehouseRawPhrase
from debussy_concert.core.phrase.utils.start import StartPhrase
from debussy_concert.core.phrase.utils.end import EndPhrase
from debussy_concert.core.motif.mixins.bigquery_job import BigQueryTimePartitioning, HivePartitioningOptions
from debussy_concert.data_ingestion.motif.load_table_motif import LoadGcsToBigQueryHivePartitionMotif


class DataIngestionBase(CompositionBase):
    config: ConfigDataIngestionBase

    def ingestion_movement_builder(
            self, movement_parameters: TimePartitionedDataIngestionMovementParameters,
            ingestion_to_landing_phrase
    ) -> DataIngestionMovement:
        start_phrase = StartPhrase()
        gcs_partition = movement_parameters.data_partitioning.gcs_partition_schema
        gcs_landing_to_bigquery_raw_phrase = self.gcs_landing_to_bigquery_raw_phrase(movement_parameters, gcs_partition)
        end_phrase = EndPhrase()

        name = f'DataIngestionMovement_{movement_parameters.name}'
        movement = DataIngestionMovement(
            name=name,
            start_phrase=start_phrase,
            ingestion_source_to_landing_storage_phrase=ingestion_to_landing_phrase,
            landing_storage_to_data_warehouse_raw_phrase=gcs_landing_to_bigquery_raw_phrase,
            end_phrase=end_phrase
        )
        movement.setup(movement_parameters)
        return movement

    def gcs_landing_to_bigquery_raw_phrase(
        self, movement_parameters: TimePartitionedDataIngestionMovementParameters,
        gcs_partition
    ):
        source_uri_prefix = (f"gs://{self.config.environment.landing_bucket}/"
                             f"{self.config.source_type}/{self.config.source_name}/{movement_parameters.name}")
        load_bigquery_from_gcs = self.load_bigquery_from_gcs_hive_partition_motif(
            gcp_conn_id=movement_parameters.extract_connection_id,
            source_uri_prefix=source_uri_prefix,
            gcs_partition=gcs_partition,
            partition_granularity=movement_parameters.data_partitioning.partition_granularity,
            partition_field=movement_parameters.data_partitioning.partition_field,
            destination_partition=movement_parameters.data_partitioning.destination_partition
        )
        gcs_landing_to_bigquery_raw_phrase = LandingStorageLoadToDataWarehouseRawPhrase(
            load_table_from_storage_motif=load_bigquery_from_gcs
        )
        return gcs_landing_to_bigquery_raw_phrase

    def load_bigquery_from_gcs_hive_partition_motif(
            self, gcp_conn_id, source_uri_prefix,
            gcs_partition, partition_granularity,
            partition_field, destination_partition):
        hive_options = HivePartitioningOptions()
        hive_options.mode = "AUTO"
        hive_options.source_uri_prefix = source_uri_prefix
        time_partitioning = BigQueryTimePartitioning(type=partition_granularity, field=partition_field)
        motif = LoadGcsToBigQueryHivePartitionMotif(
            name='load_bigquery_from_gcs_hive_partition_motif',
            gcs_partition=gcs_partition,
            destination_partition=destination_partition,
            source_format='PARQUET',
            write_disposition='WRITE_TRUNCATE',
            create_disposition='CREATE_IF_NEEDED',
            hive_partitioning_options=hive_options,
            time_partitioning=time_partitioning,
            schema_update_options=None,
            gcp_conn_id=gcp_conn_id
        )
        return motif
