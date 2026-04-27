from dagster import ConfigurableResource, EnvVar
import snowflake.connector

class SnowflakeResource(ConfigurableResource):
      account: str
      user: str
      password: str
      warehouse: str = "HEALTHCARE_WH"
      database: str = "HEALTHCARE_CLAIMS"
      role: str = "transformer"
      schema_name: str = "RAW"

      def get_connection(self):
          return snowflake.connector.connect(
              account=self.account,
              user=self.user,
              password=self.password,
              warehouse=self.warehouse,
              database=self.database,
              role=self.role,
              schema=self.schema_name,
          )