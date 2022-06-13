from debussy_concert.core.movement.movement_base import MovementBase
from debussy_concert.core.movement.protocols import (
    PStartPhrase,
    PIngestionSourceToRawVaultStoragePhrase,
    PRawVaultStorageToDataWarehouseRawPhrase,
    PEndPhrase
)
from debussy_concert.data_ingestion.config.rdbms_data_ingestion import ConfigRdbmsDataIngestion
from debussy_concert.core.config.movement_parameters.base import MovementParametersType


class DataIngestionMovement(MovementBase):
    config: ConfigRdbmsDataIngestion

    def __init__(
        self, name,
        start_phrase: PStartPhrase,
        ingestion_source_to_raw_vault_storage_phrase: PIngestionSourceToRawVaultStoragePhrase,
        raw_vault_storage_to_data_warehouse_raw_phrase: PRawVaultStorageToDataWarehouseRawPhrase,
        end_phrase: PEndPhrase,
        create_or_update_table_phrase=None,
    ) -> None:

        self.start_phrase = start_phrase
        self.ingestion_source_to_raw_vault_storage_phrase = ingestion_source_to_raw_vault_storage_phrase
        self.create_or_update_table_phrase = create_or_update_table_phrase
        self.raw_vault_storage_to_data_warehouse_raw_phrase = raw_vault_storage_to_data_warehouse_raw_phrase
        self.end_phrase = end_phrase
        phrases = [
            self.start_phrase,
            self.ingestion_source_to_raw_vault_storage_phrase]
        if create_or_update_table_phrase:
            phrases.append(self.create_or_update_table_phrase)
        phrases += [
            self.raw_vault_storage_to_data_warehouse_raw_phrase,
            self.end_phrase
        ]
        super().__init__(name=name, phrases=phrases)

    @ property
    def raw_vault_bucket_uri_prefix(self):
        return (f"gs://{self.config.environment.raw_vault_bucket}/"
                f"{self.config.source_type}/{self.config.source_name}/{self.movement_parameters.name}")

    @ property
    def raw_table_uri(self):
        return (f"{self.config.environment.project}."
                f"{self.config.environment.raw_dataset}."
                f"{self.config.table_prefix}_{self.movement_parameters.name}")

    def setup(
        self,
        movement_parameters: MovementParametersType
    ):
        self.movement_parameters = movement_parameters
        self.ingestion_source_to_raw_vault_storage_phrase.setup(
            destination_storage_uri=self.raw_vault_bucket_uri_prefix
        )
        if self.create_or_update_table_phrase:
            self.create_or_update_table_phrase.setup(
                table_uri=self.raw_table_uri
            )
        self.raw_vault_storage_to_data_warehouse_raw_phrase.setup(
            movement_parameters=movement_parameters,
            source_storage_uri_prefix=self.raw_vault_bucket_uri_prefix,
            datawarehouse_raw_uri=self.raw_table_uri
        )
        return self
