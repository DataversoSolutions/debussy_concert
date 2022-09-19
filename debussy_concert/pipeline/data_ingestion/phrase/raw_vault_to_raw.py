from debussy_concert.pipeline.data_ingestion.config.rdbms_data_ingestion import (
    ConfigRdbmsDataIngestion,
)
from debussy_concert.pipeline.data_ingestion.config.movement_parameters.rdbms_data_ingestion import (
    RdbmsDataIngestionMovementParameters,
)
from debussy_concert.core.movement.protocols import (
    PRawVaultStorageToDataWarehouseRawPhrase,
)
from debussy_concert.core.phrase.protocols import (
    PMergeTableMotif,
    PCreateExternalTableMotif,
)
from debussy_concert.core.phrase.phrase_base import PhraseBase


class RawVaultStorageExternalTableToDataWarehouseRawPhrase(
    PhraseBase, PRawVaultStorageToDataWarehouseRawPhrase
):
    config: ConfigRdbmsDataIngestion

    def __init__(
        self,
        create_external_table_motif: PCreateExternalTableMotif,
        merge_table_motif: PMergeTableMotif,
        name=None,
    ) -> None:
        self.create_external_table_motif = create_external_table_motif
        self.merge_table_motif = merge_table_motif
        motifs = [self.create_external_table_motif, self.merge_table_motif]
        super().__init__(name=name, motifs=motifs)

    @property
    def raw_vault_external_table_uri(self):
        return (
            f"{self.config.environment.project}."
            f"{self.config.environment.raw_vault_dataset}."
            f"{self.config.table_prefix}_{self.movement_parameters.name}"
        )

    def setup(
        self,
        movement_parameters: RdbmsDataIngestionMovementParameters,
        source_storage_uri_prefix,
        datawarehouse_raw_uri,
    ):
        self.movement_parameters = movement_parameters
        self.create_external_table_motif.setup(
            source_bucket_uri_prefix=source_storage_uri_prefix,
            destination_project_dataset_table=self.raw_vault_external_table_uri,
        )
        self.merge_table_motif.setup(
            main_table_uri=datawarehouse_raw_uri,
            delta_table_uri=self.raw_vault_external_table_uri,
        )
        return self


class RawVaultStorageLoadToDataWarehouseRawPhrase(
    PhraseBase, PRawVaultStorageToDataWarehouseRawPhrase
):
    def __init__(self, load_table_from_storage_motif, name=None):
        self.load_table_from_storage_motif = load_table_from_storage_motif
        motifs = [self.load_table_from_storage_motif]
        super().__init__(name=name, motifs=motifs)

    def setup(
        self, movement_parameters, source_storage_uri_prefix, datawarehouse_raw_uri
    ):
        self.load_table_from_storage_motif.setup(
            source_storage_uri_prefix=source_storage_uri_prefix,
            destination_table_uri=datawarehouse_raw_uri,
        )
