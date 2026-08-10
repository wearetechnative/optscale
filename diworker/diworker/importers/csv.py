#!/usr/bin/env python
import logging
import csv
import io
from datetime import datetime
from diworker.diworker.importers.base import BaseReportImporter
import tools.optscale_time as opttime

LOG = logging.getLogger(__name__)
CHUNK_SIZE = 200


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
            response = self.s3_client.get_object(Bucket=bucket_name, Key=csv_file_key)
            csv_content = response['Body'].read().decode('utf-8')

            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            # Get and normalize headers
            headers = csv_reader.fieldnames
            header_mapping = self._normalize_csv_headers(headers)

            LOG.info(f'Processing CSV with headers: {headers}')
            LOG.info(f'Header mapping: {header_mapping}')

            chunk = []
            row_count = 0

            for row in csv_reader:
                row_count += 1

                # Map row data to normalized fields
                normalized_row = {
                    header_mapping[key]: value
                    for key, value in row.items()
                }

                # Parse required fields
                start_date = self._parse_date(normalized_row.get('start_date', ''))
                if not start_date:
                    LOG.warning(f'Skipping row {row_count}: invalid or missing date')
                    continue

                try:
                    cost = float(normalized_row.get('cost', 0))
                except (ValueError, TypeError):
                    cost = 0.0

                resource_id = normalized_row.get('resource_id', f'csv-resource-{row_count}')

                # Build expense record
                expense = {
                    'start_date': start_date,
                    'cost': cost,
                    'resource_id': resource_id,
                    'cloud_account_id': self.cloud_acc_id,
                    'resource_type': normalized_row.get('resource_type', 'Unknown'),
                    'service_name': normalized_row.get('service_name'),
                    'region': normalized_row.get('region'),
                    'usage_quantity': float(normalized_row.get('usage_quantity', 0) or 0),
                    'tags': {},
                }

                chunk.append(expense)

                if len(chunk) >= CHUNK_SIZE:
                    LOG.info(f'Updating {len(chunk)} raw records (processed {row_count} rows)')
                    self.update_raw_records(chunk)
                    chunk = []

            # Update remaining records
            if chunk:
                LOG.info(f'Updating final {len(chunk)} raw records (total {row_count} rows)')
                self.update_raw_records(chunk)

            LOG.info(f'CSV import completed. Total rows processed: {row_count}')

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
