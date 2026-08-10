import logging
import uuid
import boto3
from boto3.session import Config as BotoConfig
from tornado.web import stream_request_body
import io

from rest_api.rest_api_server.handlers.v1.base_async import BaseAsyncCollectionHandler
from rest_api.rest_api_server.handlers.v1.base import BaseAuthHandler
from rest_api.rest_api_server.exceptions import Err
from tools.optscale_exceptions.http_exc import OptHTTPError
from tools.optscale_exceptions.common_exc import ForbiddenException
from rest_api.rest_api_server.controllers.cloud_account import CloudAccountAsyncController
from rest_api.rest_api_server.utils import run_task, ModelEncoder
import json

MAX_BODY_SIZE = 1024 * 1024 * 1024  # 1GB for large CSV files
LOG = logging.getLogger()


@stream_request_body
class CsvUploadHandler(BaseAsyncCollectionHandler, BaseAuthHandler):
    """Handler for streaming large CSV file uploads"""

    def _get_controller_class(self):
        return CloudAccountAsyncController

    def initialize(self):
        super().initialize()
        self._csv_buffer = io.BytesIO()
        self._bytes_received = 0
        self._filename = None
        self._name = None
        self._organization_id = None

    async def prepare(self):
        await super().prepare()
        # Set max body size to allow large CSV files
        # stream_request_body decorator ensures tornado doesn't load entire file into memory
        self.request.connection.set_max_body_size(MAX_BODY_SIZE)

        self._organization_id = self.path_kwargs.get('organization_id')
        LOG.info(f'Starting CSV upload for organization {self._organization_id}')

    async def data_received(self, chunk):
        """Receive file data in chunks"""
        self._csv_buffer.write(chunk)
        self._bytes_received += len(chunk)

        # Log progress for large files
        if self._bytes_received % (50 * 1024 * 1024) == 0:  # Every 50MB
            LOG.info(f'CSV upload progress: {self._bytes_received / (1024 * 1024):.1f} MB received')

    async def post(self, organization_id):
        """
        ---
        description: |
            Upload CSV file with cost data
            Required permission: MANAGE_CLOUD_CREDENTIALS
        tags: [cloud_account]
        summary: Upload CSV cost data file
        parameters:
        -   name: organization_id
            in: path
            description: Organization id
            required: true
            type: string
        -   in: formData
            name: csv_file
            description: CSV file containing cost and usage data
            required: true
            type: file
        -   in: formData
            name: name
            description: Name for the data source
            required: true
            type: string
        responses:
            201:
                description: Success (returns created cloud account)
            400:
                description: Bad request
            401:
                description: Unauthorized
            403:
                description: Forbidden
        security:
        - token: []
        """
        await self.check_permissions('MANAGE_CLOUD_CREDENTIALS', 'organization', organization_id)

        try:
            # Parse multipart form data from buffer
            content_type = self.request.headers.get("Content-Type", "")

            if not content_type.startswith("multipart/form-data"):
                raise OptHTTPError(400, Err.OE0214, ['Content-Type must be multipart/form-data'])

            # Extract form fields from body
            body_data = self._csv_buffer.getvalue()

            # Parse manually to extract filename and name
            # Since we're streaming, we need to parse the multipart data ourselves
            import re

            # Extract filename
            filename_match = re.search(rb'filename="([^"]+)"', body_data[:2000])  # Check first 2KB for headers
            if not filename_match:
                raise OptHTTPError(400, Err.OE0216, ['csv_file'])

            filename = filename_match.group(1).decode('utf-8')

            if not filename.lower().endswith('.csv'):
                raise OptHTTPError(400, Err.OE0214, ['File must be in CSV format'])

            # Extract name field
            name_match = re.search(rb'name="name"\r?\n\r?\n([^\r\n]+)', body_data[:5000])
            if not name_match:
                raise OptHTTPError(400, Err.OE0216, ['name'])

            name = name_match.group(1).decode('utf-8').strip()

            # Extract file content (everything between file headers and final boundary)
            file_start = re.search(rb'\r?\n\r?\n', body_data[filename_match.end():])
            if not file_start:
                raise OptHTTPError(400, Err.OE0214, ['Invalid file data'])

            file_data_start = filename_match.end() + file_start.end()

            # Find the final boundary
            boundary_match = re.search(rb'------WebKitFormBoundary[a-zA-Z0-9]+', body_data[:500])
            if boundary_match:
                boundary = boundary_match.group(0)
                # Find last occurrence of boundary
                final_boundary_pos = body_data.rfind(boundary + b'--')
                if final_boundary_pos > file_data_start:
                    file_content = body_data[file_data_start:final_boundary_pos-4]  # -4 for \r\n before boundary
                else:
                    file_content = body_data[file_data_start:]
            else:
                file_content = body_data[file_data_start:]

            LOG.info(f'CSV upload completed: {filename}, size: {len(file_content)} bytes, name: {name}')

            # Generate unique file key
            file_key = f"csv-uploads/{organization_id}/{uuid.uuid4()}/{filename}"

            # Upload to MinIO using streaming
            s3_params = self._config.read_branch('/minio')
            s3_client = boto3.client(
                's3',
                endpoint_url=f"http://{s3_params['host']}:{s3_params['port']}",
                aws_access_key_id=s3_params['access'],
                aws_secret_access_key=s3_params['secret'],
                config=BotoConfig(s3={'addressing_style': 'path'})
            )

            bucket_name = 'optscale-csv-uploads'

            # Create bucket if it doesn't exist
            try:
                s3_client.head_bucket(Bucket=bucket_name)
            except Exception:
                s3_client.create_bucket(Bucket=bucket_name)

            # Upload file to MinIO
            s3_client.put_object(
                Bucket=bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType='text/csv'
            )

            LOG.info(f'CSV file uploaded to MinIO: {file_key}')

            # Create cloud account with CSV file reference
            data = {
                'name': name,
                'type': 'csv_upload',
                'csvUploadConfig': {
                    'csv_file_key': file_key,
                    'bucket_name': bucket_name,
                    'original_filename': filename
                },
                'auto_import': True,
                'process_recommendations': False
            }

            controller = self._get_controller_class()(
                self._session(), self._config, self.token
            )
            result = await run_task(controller.create, organization_id, **data)

            LOG.info(f'Cloud account created for CSV upload: {result.get("id")}')

            self.set_status(201)
            self.write(json.dumps(result, cls=ModelEncoder))

        except ForbiddenException as ex:
            raise OptHTTPError.from_opt_exception(403, ex)
        except Exception as ex:
            LOG.exception(f'CSV upload failed: {ex}')
            raise
        finally:
            # Clean up buffer
            self._csv_buffer.close()
