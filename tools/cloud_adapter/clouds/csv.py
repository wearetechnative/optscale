from tools.cloud_adapter.clouds.base import CloudBase
from tools.cloud_adapter.utils import CloudParameter


class CsvUpload(CloudBase):
    """Cloud adapter for CSV uploaded cost data"""

    BILLING_CREDS = [
        CloudParameter(name='csv_file_key', type=str, required=True),
        CloudParameter(name='bucket_name', type=str, required=False),
    ]

    def __init__(self, cloud_config, *args, **kwargs):
        self.config = cloud_config

    def validate_credentials(self, org_id=None):
        """Validate that CSV file exists"""
        csv_file_key = self.config.get('csv_file_key')
        if not csv_file_key:
            raise ValueError('CSV file key is required')

        return {
            # Every uploaded file is a distinct data source. Using only the
            # organization id made all uploads after the first look like
            # duplicate cloud accounts.
            'account_id': 'csv-upload-%s' % csv_file_key.split('/')[-2],
            'warnings': []
        }

    def configure_report(self):
        """No report configuration needed for CSV uploads"""
        pass

    def discovery_calls_map(self):
        """No resource discovery for CSV uploads"""
        return {}

    def configure_last_import_modified_at(self):
        """Not applicable for CSV uploads"""
        pass

    def volume_discovery_calls(self):
        raise NotImplementedError

    def instance_discovery_calls(self):
        raise NotImplementedError

    def snapshot_discovery_calls(self):
        raise NotImplementedError

    def bucket_discovery_calls(self):
        raise NotImplementedError

    def pod_discovery_calls(self):
        raise NotImplementedError

    def snapshot_chain_discovery_calls(self):
        raise NotImplementedError

    def rds_instance_discovery_calls(self):
        raise NotImplementedError

    def ip_address_discovery_calls(self):
        raise NotImplementedError

    def get_regions_coordinates(self, load=True):
        return {}

    def set_currency(self, currency):
        self._currency = currency
