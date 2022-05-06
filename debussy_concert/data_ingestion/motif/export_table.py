from typing import List, Optional
from airflow import DAG
from google.protobuf.duration_pb2 import Duration
from airflow.utils.task_group import TaskGroup
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.dataproc import DataprocSubmitJobOperator
from debussy_framework.v3.operators.mysql_check import MySQLCheckOperator
from debussy_framework.v2.operators.basic import StartOperator
from debussy_framework.v2.operators.datastore import DatastoreGetEntityOperator

from debussy_concert.core.motif.motif_base import MotifBase, PClusterMotifMixin
from debussy_concert.core.motif.mixins.dataproc import DataprocClusterHandlerMixin
from debussy_concert.core.motif.bigquery_query_job import BigQueryQueryJobMotif
from debussy_concert.core.phrase.protocols import PExportDataToStorageMotif
from debussy_concert.data_ingestion.config.movement_parameters.rdbms_data_ingestion import RdbmsDataIngestionMovementParameters
from debussy_concert.data_ingestion.config.rdbms_data_ingestion import ConfigRdbmsDataIngestion


class ExportBigQueryQueryToGcsMotif(BigQueryQueryJobMotif):
    extract_query_template = """
    EXPORT DATA OPTIONS(overwrite=false,format='PARQUET',uri='{uri}')
    AS {extract_query}
    """

    def __init__(self, extract_query, gcs_partition: str,
                 name=None, gcp_conn_id='google_cloud_default', **op_kw_args):
        super().__init__(name, gcp_conn_id=gcp_conn_id, **op_kw_args)
        self.extract_query = extract_query
        self.gcs_partition = gcs_partition

    def setup(self, destination_storage_uri):
        self.destination_storage_uri = destination_storage_uri
        uri = (f'{destination_storage_uri}/'
               f'{self.gcs_partition}/'
               f'*.parquet')
        self.sql_query = self.extract_query_template.format(
            uri=uri, extract_query=self.extract_query)

        return self


def build_query_from_datastore_entity_json(entity_json_str):
    import json
    import pendulum

    entity_dict = json.loads(entity_json_str)
    entity = entity_dict["entity"]
    source_table = entity.get("SourceTable")
    fields = entity.get("Fields")
    fields = fields.split(",")
    if "METADATA" in fields:
        fields.remove("METADATA")

    fields = [f"`{field}`" for field in fields]
    fields = ", ".join(fields)
    offset_type = entity.get("OffsetType")
    offset_value = entity.get("OffsetValue")
    offset_field = entity.get("OffsetField")
    source_timezone = entity.get("SourceTimezone")
    if offset_value == "NONE":
        offset_value = None
    if offset_type == "TIMESTAMP":
        offset_value = "'{}'".format(
            pendulum.parse(offset_value)
            .in_timezone(source_timezone)
            .strftime("%Y-%m-%dT%H:%M:%S")
        )
    elif offset_type == "ROWVERSION":
        offset_value = f"0x{offset_value}"
    elif offset_type == "STRING":
        offset_value = f"'{offset_value}'"

    if offset_value:
        query = (
            f"SELECT {fields} FROM {source_table}"
            f" WHERE {offset_field} > {offset_value}"
        )
    else:
        query = f"SELECT {fields} FROM {source_table}"

    return query


class ExportFullMySqlTableToGcsMotif(
        MotifBase, DataprocClusterHandlerMixin, PClusterMotifMixin, PExportDataToStorageMotif):
    config: ConfigRdbmsDataIngestion
    cluster_tags = ["dataproc"]
    gcs_connector_version = "2.2.0"
    bigquery_connector_version = "1.2.0"
    spark_bigquery_connector_version = "0.19.1"
    service_account_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    master_machine_type_uri = "n1-standard-4"
    software_config_image_version = "1.4"
    work_num_instances = 2
    worker_disk_config = {
        "boot_disk_type": "pd-standard",
        "boot_disk_size_gb": 1000,
    }
    endpoint_enable_http_port_access = True
    _cluster_name_task_id = None

    def __init__(
            self,
            movement_parameters: RdbmsDataIngestionMovementParameters,
            name=None
    ) -> None:
        super().__init__(name=name)
        self.movement_parameters = movement_parameters
        self.pip_packages = self.config.dataproc_config.get(
            "pip_packages", [])
        self.spark_jars_packages = self.config.dataproc_config.get(
            "spark_jars_packages", "")
        self.service_account_scopes = self.config.dataproc_config.get(
            "service_account_scopes", self.service_account_scopes)
        self.cluster_tags = self.config.dataproc_config.get(
            "cluster_tags", self.cluster_tags)
        self.gcs_connector_version = self.config.dataproc_config.get(
            "gcs_connector_version", self.gcs_connector_version)
        self.bigquery_connector_version = self.config.dataproc_config.get(
            "bigquery_connector_version", self.bigquery_connector_version)
        self.spark_bigquery_connector_version = self.config.dataproc_config.get(
            "spark_bigquery_connector_version", self.spark_bigquery_connector_version)
        self.master_machine_type_uri = self.config.dataproc_config.get(
            "master_machine_type_uri", self.master_machine_type_uri)
        self.software_config_image_version = self.config.dataproc_config.get(
            "software_config_image_version", self.software_config_image_version)
        self.endpoint_enable_http_port_access = self.config.dataproc_config.get(
            "endpoint_enable_http_port_access", self.endpoint_enable_http_port_access)

    @property
    def config(self) -> ConfigRdbmsDataIngestion:
        return super().config

    @property
    def cluster_name(self):
        if not self._cluster_name_task_id:
            raise RuntimeError("Cluster name is not defined or being accessed before being defined")
        return self._cluster_name_task_id

    @property
    def cluster_config(self):
        environment = self.config.environment
        project = environment.project
        region = environment.region
        zone = environment.zone
        staging_bucket = environment.staging_bucket

        init_action_timeout = Duration()
        init_action_timeout.FromSeconds(500)
        cluster_config = {
            "temp_bucket": staging_bucket,
            "gce_cluster_config": {
                "zone_uri": zone,
                "subnetwork_uri": self.config.dataproc_config["subnet"],
                "tags": self.cluster_tags,
                "metadata": {
                    "gcs-connector-version": self.gcs_connector_version,
                    "bigquery-connector-version": self.bigquery_connector_version,
                    "spark-bigquery-connector-version": self.spark_bigquery_connector_version,
                    "PIP_PACKAGES": " ".join(self.pip_packages),
                },
                "service_account_scopes": self.service_account_scopes
            },
            "master_config": {"machine_type_uri": self.master_machine_type_uri},
            "software_config": {
                "image_version": self.software_config_image_version,
                "properties": {
                    "spark:spark.default.parallelism": str(
                        self.config.dataproc_config["parallelism"]
                    ),
                    "spark:spark.sql.shuffle.partitions": str(
                        self.config.dataproc_config["parallelism"]
                    ),
                    "spark:spark.sql.legacy.parquet.int96RebaseModeInWrite": "CORRECTED",
                    "spark:spark.jars.packages": self.spark_jars_packages,
                    "spark:spark.jars.excludes": "net.sourceforge.f2j:arpack_combined_all",
                    "dataproc:dataproc.conscrypt.provider.enable": "false",
                },
            },
            "worker_config": {
                "disk_config": self.worker_disk_config,
                "machine_type_uri": self.config.dataproc_config["machine_type"],
                "num_instances": self.work_num_instances,
            },
            "secondary_worker_config": {
                "disk_config": self.worker_disk_config,
                "machine_type_uri": self.config.dataproc_config["machine_type"],
                "num_instances": self.config.dataproc_config["num_workers"],
            },
            "autoscaling_config": {
                "policy_uri": f"projects/{project}/regions/{region}/autoscalingPolicies/ephemeral-clusters"
            },
            "initialization_actions": [
                {
                    "executable_file": f"gs://goog-dataproc-initialization-actions-{region}/python/pip-install.sh",
                    "execution_timeout": init_action_timeout,
                },
                {
                    "executable_file": f"gs://goog-dataproc-initialization-actions-{region}/connectors/connectors.sh",
                    "execution_timeout": init_action_timeout,
                },
            ],
            "endpoint_config": {"enable_http_port_access": self.endpoint_enable_http_port_access},
        }
        return cluster_config

    def setup(self, destination_storage_uri: str):
        self.destination_storage_uri = destination_storage_uri
        return self

    def get_db_conn_data(self):
        """Get database connection data from Secret Manager"""
        from google.cloud import secretmanager
        import json

        client = secretmanager.SecretManagerServiceClient()

        name = f"{self.config.secret_manager_uri}/versions/latest"
        response = client.access_secret_version(name=name)
        secret = response.payload.data.decode("UTF-8")
        db_conn_data = json.loads(secret)
        db_conn_data.update({"database": self.config.database})
        return db_conn_data

    def build(self, dag, parent_task_group: TaskGroup):
        task_group = TaskGroup(group_id=self.name, parent_group=parent_task_group)

        start = StartOperator(phase=self.movement_parameters.name, dag=dag, task_group=task_group)

        cluster_name_id = self.cluster_name_id(dag, task_group)
        self._cluster_name_task_id = self.build_cluster_name(dag, cluster_name_id)
        get_datastore_entity = self.get_datastore_entity(dag, self.movement_parameters, task_group)
        check_mysql_table = self.check_mysql_table(dag, task_group, get_datastore_entity.task_id)
        build_extract_query = self.build_extract_query(dag, task_group, get_datastore_entity.task_id)
        create_dataproc_cluster = self.create_dataproc_cluster(dag, task_group)
        jdbc_to_landing = self.jdbc_to_landing(dag, task_group, build_extract_query.task_id)
        delete_dataproc_cluster = self.delete_dataproc_cluster(dag, task_group)
        self.workflow_service.chain_tasks(
            start,
            get_datastore_entity,
            check_mysql_table,
            build_extract_query,
            cluster_name_id,
            create_dataproc_cluster,
            jdbc_to_landing,
            delete_dataproc_cluster
        )
        return task_group

    def build_cluster_name(self, dag: DAG, cluster_name_task):
        # max number of characters for dataproc cluster names is 34
        # for usage in cluster_name property
        return (f"dby{{{{ ti.xcom_pull(dag_id='{dag.dag_id}', task_ids='{cluster_name_task.task_id}') }}}}"
                f"{self.config.database.replace('_', '').lower()[:22]}")

    def cluster_name_id(self, dag, task_group):
        cluster_name_id = PythonOperator(
            task_id='cluster_name_id',
            python_callable=lambda x: x,
            op_args=['{{ ti.job_id }}'],
            dag=dag,
            task_group=task_group)
        return cluster_name_id

    def jdbc_to_landing(self, dag, task_group, build_extract_query_id):
        secret_uri = f"{self.config.secret_manager_uri}/versions/latest"
        run_ts = "{{ ts_nodash }}"

        # path and naming parameters
        load_timestamp_partition = "loadTimestamp"
        run_ts = "{{ ts_nodash }}"
        load_date_partition = "loadDate"
        run_date = "{{ ds }}"
        pyspark_scripts_uri = f"gs://{self.config.environment.artifact_bucket}/pyspark-scripts"

        driver = "com.mysql.cj.jdbc.Driver"
        jdbc_url = "jdbc:mysql://{host}:{port}/" + self.config.database

        jdbc_to_landing = DataprocSubmitJobOperator(
            task_id="jdbc_to_landing",
            job={
                    "reference": {"project_id": self.config.environment.project},
                    "placement": {"cluster_name": self.cluster_name},
                    "pyspark_job": {
                        "main_python_file_uri": f"{pyspark_scripts_uri}/jdbc-to-gcs/jdbc_to_gcs.py",
                        "args": [
                            driver,
                            jdbc_url,
                            secret_uri,
                            self.config.database,
                            f"{{{{ task_instance.xcom_pull('{build_extract_query_id}') }}}}",
                            run_ts,
                            (f"{self.destination_storage_uri}/{load_date_partition}={run_date}/"
                             f"{load_timestamp_partition}={run_ts}/"),
                        ],
                    },
            },
            region=self.config.environment.region,
            project_id=self.config.environment.project,
            dag=dag,
            task_group=task_group
        )

        return jdbc_to_landing

    def build_extract_query(self, dag, task_group, get_datastore_entity_task_id):
        build_extract_query = PythonOperator(
            task_id="build_extract_query",
            python_callable=build_query_from_datastore_entity_json,
            op_args=[
                    f"{{{{ task_instance.xcom_pull('{get_datastore_entity_task_id}') }}}}"],
            dag=dag,
            task_group=task_group
        )

        return build_extract_query

    def check_mysql_table(self, dag, task_group, get_datastore_entity_task_id):
        check_mysql_table = MySQLCheckOperator(
            task_id="check_mysql_table",
            entity_json_str=f"{{{{ task_instance.xcom_pull('{get_datastore_entity_task_id}') }}}}",
            db_conn_data_callable=self.get_db_conn_data,
            dag=dag,
            task_group=task_group
        )

        return check_mysql_table

    def get_datastore_entity(self, dag, movement_parameters: RdbmsDataIngestionMovementParameters, task_group):
        db_kind = self.config.database[0].upper() + self.config.database[1:]
        kind = f"MySql{db_kind}Tables"
        get_datastore_entity = DatastoreGetEntityOperator(
            task_id="get_datastore_entity",
            project=self.config.environment.project,
            namespace="TABLE",
            kind=kind,
            filters=("SourceTable", "=", movement_parameters.name),
            dag=dag,
            task_group=task_group
        )

        return get_datastore_entity
