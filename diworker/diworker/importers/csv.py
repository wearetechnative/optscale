import csv
import gzip
import io
import logging
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime

from diworker.diworker.importers.base import BaseReportImporter
import tools.optscale_time as opttime

LOG = logging.getLogger(__name__)
CHUNK_SIZE = 200
SQL_BATCH_SIZE = 10000


class CsvReportImporter(BaseReportImporter):
    """
    CSV Report Importer for uploaded cost data files
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_update_fields(self):
        return [
            'cost',
            'usage_quantity',
            'resource_name',
            'resource_type',
            'service_name',
            'region',
            'tags'
        ]

    def get_unique_field_list(self):
        return [
            'start_date',
            'resource_id',
            'cloud_account_id',
        ]

    def _parse_date(self, date_str):
        """Parse date from various formats"""
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%m/%d/%Y',
            '%d/%m/%Y',
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # If no format matches, try to parse as timestamp
        try:
            return datetime.fromtimestamp(float(date_str))
        except (ValueError, TypeError):
            LOG.warning(f'Unable to parse date: {date_str}')
            return None

    def _normalize_csv_headers(self, headers):
        """Normalize CSV headers to standard field names"""
        header_mapping = {
            # Date fields
            'date': 'start_date',
            'usage_date': 'start_date',
            'lineitem/usagestartdate': 'start_date',
            'usage start date': 'start_date',
            'billingperiodstart': 'start_date',

            # Cost fields
            'cost': 'cost',
            'lineitem/unblendedcost': 'cost',
            'unblendedcost': 'cost',
            'pretaxcost': 'cost',
            'totalcost': 'cost',

            # Resource ID fields
            'resource_id': 'resource_id',
            'resourceid': 'resource_id',
            'lineitem/resourceid': 'resource_id',
            'instance_id': 'resource_id',
            'instanceid': 'resource_id',

            # Service/Product fields
            'service': 'service_name',
            'service_name': 'service_name',
            'product/servicename': 'service_name',
            'servicename': 'service_name',
            'metercategory': 'service_name',

            # Resource type fields
            'resource_type': 'resource_type',
            'resourcetype': 'resource_type',
            'product/instancetype': 'resource_type',
            'instancetype': 'resource_type',
            'metersubcategory': 'resource_type',

            # Region fields
            'region': 'region',
            'product/region': 'region',
            'resourcelocation': 'region',
            'location': 'region',

            # Usage quantity
            'usage_quantity': 'usage_quantity',
            'usagequantity': 'usage_quantity',
            'lineitem/usageamount': 'usage_quantity',
            'quantity': 'usage_quantity',
        }

        normalized = {}
        for header in headers:
            header_lower = header.lower().strip()
            normalized_name = header_mapping.get(header_lower, header_lower)
            normalized[header] = normalized_name

        return normalized

    @staticmethod
    def _as_float(value):
        try:
            return float(value or 0)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _create_aggregation_db(path):
        db = sqlite3.connect(path)
        db.execute('''
            CREATE TABLE expenses (
                start_date TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                cost REAL NOT NULL,
                usage_quantity REAL NOT NULL,
                resource_type TEXT,
                service_name TEXT,
                region TEXT,
                PRIMARY KEY (start_date, resource_id)
            )
        ''')
        return db

    def _aggregate_row(self, db, expense):
        db.execute('''
            INSERT INTO expenses VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(start_date, resource_id) DO UPDATE SET
                cost = cost + excluded.cost,
                usage_quantity = usage_quantity + excluded.usage_quantity,
                resource_type = COALESCE(NULLIF(resource_type, ''),
                                         excluded.resource_type),
                service_name = COALESCE(NULLIF(service_name, ''),
                                        excluded.service_name),
                region = COALESCE(NULLIF(region, ''), excluded.region)
        ''', (
            expense['start_date'].isoformat(), expense['resource_id'],
            expense['cost'], expense['usage_quantity'],
            expense['resource_type'], expense['service_name'],
            expense['region']))

    def _store_aggregated_expenses(self, db):
        cursor = db.execute('''
            SELECT start_date, resource_id, cost, usage_quantity,
                   resource_type, service_name, region
            FROM expenses
        ''')
        while True:
            rows = cursor.fetchmany(CHUNK_SIZE)
            if not rows:
                break
            chunk = [{
                'start_date': datetime.fromisoformat(row[0]),
                'resource_id': row[1],
                'cost': row[2],
                'usage_quantity': row[3],
                'resource_type': row[4] or 'Unknown',
                'service_name': row[5],
                'region': row[6],
                'cloud_account_id': self.cloud_acc_id,
                'tags': {},
            } for row in rows]
            self.update_raw_records(chunk)

    def load_raw_data(self):
        """Load and parse CSV file from MinIO storage"""
        csv_file_key = self.cloud_acc['config'].get('csv_file_key')
        if not csv_file_key:
            LOG.error('No CSV file key found in cloud account config')
            return

        bucket_name = self.cloud_acc['config'].get('bucket_name', 'optscale-csv-uploads')

        try:
            # Download CSV file from MinIO
            LOG.info(f'Downloading CSV file: {csv_file_key} from bucket: {bucket_name}')
            response = self.s3_client.get_object(
                Bucket=bucket_name, Key=csv_file_key)
            body = response['Body']
            binary_stream = (gzip.GzipFile(fileobj=body) if
                             csv_file_key.lower().endswith('.gz') else body)

            # utf-8-sig accepts normal UTF-8 and removes the BOM used by
            # Azure cost exports. Newline handling is delegated to csv.
            with closing(body), io.TextIOWrapper(
                    binary_stream, encoding='utf-8-sig', newline='') as stream, \
                    tempfile.TemporaryDirectory() as temp_dir:
                csv_reader = csv.DictReader(stream)
                headers = csv_reader.fieldnames
                if not headers:
                    raise ValueError('CSV file does not contain a header row')
                header_mapping = self._normalize_csv_headers(headers)

                LOG.info(f'Processing CSV with headers: {headers}')
                db = self._create_aggregation_db(
                    f'{temp_dir}/aggregated-expenses.sqlite')
                try:
                    row_count = 0
                    skipped_count = 0
                    for row in csv_reader:
                        row_count += 1
                        normalized_row = {
                            header_mapping[key]: value
                            for key, value in row.items()
                        }
                        start_date = self._parse_date(
                            normalized_row.get('start_date', ''))
                        if not start_date:
                            skipped_count += 1
                            continue

                        expense = {
                            'start_date': start_date,
                            'cost': self._as_float(
                                normalized_row.get('cost')),
                            'resource_id': (
                                normalized_row.get('resource_id') or
                                f'csv-resource-{row_count}'),
                            'resource_type': normalized_row.get(
                                'resource_type') or 'Unknown',
                            'service_name': normalized_row.get('service_name'),
                            'region': normalized_row.get('region'),
                            'usage_quantity': self._as_float(
                                normalized_row.get('usage_quantity')),
                        }
                        self._aggregate_row(db, expense)
                        if row_count % SQL_BATCH_SIZE == 0:
                            db.commit()
                            LOG.info('Processed %s CSV rows', row_count)

                    db.commit()
                    self._store_aggregated_expenses(db)
                finally:
                    db.close()

            LOG.info('CSV import completed: %s rows processed, %s skipped',
                     row_count, skipped_count)

        except Exception as e:
            LOG.error(f'Error loading CSV data: {str(e)}', exc_info=True)
            raise

    def get_resource_info_from_expenses(self, expenses):
        """Extract resource information from expenses"""
        first_seen = opttime.utcnow()
        last_seen = opttime.utcfromtimestamp(0)
        resource_type = None
        service_name = None
        region = None

        for e in expenses:
            if not resource_type:
                resource_type = e.get('resource_type', 'Unknown')
            if not service_name:
                service_name = e.get('service_name')
            if not region:
                region = e.get('region')

            start_date = e.get('start_date')
            if start_date and start_date < first_seen:
                first_seen = start_date
            if start_date and start_date > last_seen:
                last_seen = start_date

        if last_seen < first_seen:
            last_seen = first_seen

        info = {
            'tags': e.get('tags', {}),
            'first_seen': int(first_seen.timestamp()),
            'last_seen': int(last_seen.timestamp()),
            'resource_type': resource_type,
            'service_name': service_name,
            'region': region,
        }

        return info

    def get_resource_data(self, r_id, info, unique_id_field='cloud_resource_id'):
        """Get resource data for storage"""
        return {
            'cloud_resource_id': r_id,
            'tags': info.get('tags', {}),
            'service_name': info.get('service_name'),
            'region': info.get('region'),
            'first_seen': info['first_seen'],
            'last_seen': info['last_seen'],
            'resource_type': info['resource_type'],
            **self._get_fake_cad_extras(info)
        }

    def clean_expenses_for_resource(self, resource_id, expenses):
        """Clean and aggregate expenses by date"""
        clean_expenses = {}
        for e in expenses:
            usage_date = e['start_date']
            if usage_date in clean_expenses:
                clean_expenses[usage_date]['cost'] += e['cost']
            else:
                clean_expenses[usage_date] = {
                    'date': usage_date,
                    'cost': e['cost'],
                    'resource_id': resource_id,
                    'cloud_account_id': e['cloud_account_id']
                }
        return clean_expenses
