from airflow_concert.movement.movement_base import MovementBase
from airflow_concert.phrase.bigquery_to_bigquery import BigQueryToBigQueryPhrase


class BigQueryToBigQueryMovement(MovementBase):
    def __init__(self, config, name=None) -> None:
        super().__init__(name=name,
                         config=config,
                         phrases=[BigQueryToBigQueryPhrase(config)])
