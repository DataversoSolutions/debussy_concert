from airflow.utils.task_group import TaskGroup
from airflow.operators.python import PythonOperator

from airflow_concert.operators.bigquery import BigQueryCreateExternalTableOperator
from airflow_concert.motif.motif_base import MotifBase
from airflow_concert.phrase.protocols import PMergeLandingToRawMotif
from airflow_concert.entities.table import Table


def build_bigquery_merge_query(
    sql_template,
    main_table,
    delta_table,
    pii_columns,
    pii_table,
    delta_date_partition,
    delta_date_value,
    delta_time_partition,
    delta_time_value,
    primary_key,
    min_partition_value,
    max_partition_value,
    fields,
    partition_field=None,
):

    if pii_columns:
        except_columns = f"EXCEPT ({pii_columns})"
        extra_columns = ",".join(f"PII.{column}" for column in pii_columns.split(","))
        join_clause = f"INNER JOIN {pii_table} PII USING ({primary_key})"
    else:
        except_columns = ""
        extra_columns = ""
        join_clause = ""

    where_clause = f"""
    {delta_date_partition} = '{delta_date_value}' AND
    {delta_time_partition} = '{delta_time_value}'
    """
    if partition_field:
        merge_clause = f"""
        main.{primary_key} = delta.{primary_key} AND
        main.{partition_field} BETWEEN '{min_partition_value}' AND '{max_partition_value}'
        """
    else:
        merge_clause = f"""
        main.{primary_key} = delta.{primary_key}
        """
    update_clause = ", ".join(f"main.{field} = delta.{field}" for field in fields)
    insert_list = ", ".join(f"`{field}`" for field in fields)
    insert_values_list = ", ".join(f"delta.{field}" for field in fields)
    return sql_template.format(
        main_table=main_table,
        except_columns=except_columns,
        extra_columns=extra_columns,
        join_clause=join_clause,
        delta_table=delta_table,
        where_clause=where_clause,
        merge_clause=merge_clause,
        update_clause=update_clause,
        insert_list=insert_list,
        insert_values_list=insert_values_list,
    )


MERGE = """
    MERGE 
        `{main_table}` AS main
    USING
        (
        SELECT
            * {except_columns},
            {extra_columns}
        FROM
            `{delta_table}` {join_clause}
        WHERE
            {where_clause}
        ) AS delta
    ON
        {merge_clause}
    WHEN MATCHED THEN UPDATE SET
        {update_clause}
    WHEN NOT MATCHED THEN INSERT(
        {insert_list}
    ) VALUES (
        {insert_values_list}
    )
"""


class MergeReplaceBigQueryMotif(MotifBase, PMergeLandingToRawMotif):
    def __init__(
        self,
        config,
        table: Table,
        origin_bucket,
        destiny_dataset: str,
        name=None
    ) -> None:
        self.table = table
        self.origin_bucket = origin_bucket
        self.destiny_dataset = destiny_dataset
        super().__init__(name=name, config=config)

    @property
    def table_resource(self):
        return {
            "type": "EXTERNAL",
                    "externalDataConfiguration": {
                        "hivePartitioningOptions": {
                            "mode": "AUTO",
                            "sourceUriPrefix": self.origin_bucket,
                        },
                        "sourceFormat": "PARQUET",
                        "sourceUris": [f"{self.origin_bucket}/*.parquet"],
                    },
        }

    def build(self, dag, task_group):
        task_group = TaskGroup(group_id=self.name, dag=dag, parent_group=task_group)
        table_prefix = self.config.database.lower()
        destination_project_dataset_table = f"{self.config.environment.project}.{self.destiny_dataset}.{table_prefix}_{self.table.name}"
        create_landing_external_table = BigQueryCreateExternalTableOperator(
            task_id="create_landing_external_table",
            bucket=self.origin_bucket,
            destination_project_dataset_table=destination_project_dataset_table,
            table_resource=self.table_resource,
            dag=dag,
            task_group=task_group
        )
        main_table = (f"{self.config.environment.project}."
                      f"{self.config.environment.raw_dataset}."
                      f"{table_prefix}_{self.table.name}")
        delta_table = (f"{self.config.environment.project}."
                       f"{self.config.environment.landing_dataset}."
                       f"{table_prefix}_{self.table.name}")
        pii_columns = ','.join([column.name for column in self.table.pii_columns])
        primary_key = self.table.primary_key.name
        fields_list = [field.name for field in self.table.fields]
        delta_date_partition = "loadDate"
        delta_date_value = "{{ ds }}"
        delta_time_partition = "loadTimestamp"
        delta_time_value = "{{ ts_nodash }}"
        build_merge_query = PythonOperator(
            task_id="build_merge_query",
            python_callable=build_bigquery_merge_query,
            op_kwargs={
                "sql_template": MERGE,
                "main_table": main_table,
                "delta_table": delta_table,
                "pii_columns": pii_columns,
                "pii_table": "",
                "delta_date_partition": delta_date_partition,
                "delta_date_value": delta_date_value,
                "delta_time_partition": delta_time_partition,
                "delta_time_value": delta_time_value,
                "primary_key": primary_key,
                "partition_field": None,
                "min_partition_value": None,
                "max_partition_value": None,
                "fields": fields_list,
            },
            dag=dag,
            task_group=task_group
        )
        create_landing_external_table >> build_merge_query
        return task_group
