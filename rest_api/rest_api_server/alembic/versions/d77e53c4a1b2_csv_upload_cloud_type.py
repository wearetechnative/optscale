"""Add CSV upload cloud account type.

Revision ID: d77e53c4a1b2
Revises: c1d4f7a92b08
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = 'd77e53c4a1b2'
down_revision = 'c1d4f7a92b08'
branch_labels = None
depends_on = None


old_cloud_types = sa.Enum(
    'AWS_CNR', 'ALIBABA_CNR', 'AZURE_CNR', 'AZURE_TENANT',
    'KUBERNETES_CNR', 'ENVIRONMENT', 'GCP_CNR', 'GCP_TENANT', 'NEBIUS',
    'DATABRICKS')
new_cloud_types = sa.Enum(
    'AWS_CNR', 'ALIBABA_CNR', 'AZURE_CNR', 'AZURE_TENANT',
    'KUBERNETES_CNR', 'ENVIRONMENT', 'GCP_CNR', 'GCP_TENANT', 'NEBIUS',
    'DATABRICKS', 'CSV_UPLOAD')


def upgrade():
    op.alter_column('cloudaccount', 'type', existing_type=old_cloud_types,
                    type_=new_cloud_types, nullable=False)


def downgrade():
    cloud_accounts = sa.sql.table(
        'cloudaccount', sa.sql.column('type', new_cloud_types),
        sa.sql.column('deleted_at', sa.Integer()))
    op.execute(
        cloud_accounts.update().where(
            cloud_accounts.c.type == 'CSV_UPLOAD').values(
                type='ENVIRONMENT',
                deleted_at=int(datetime.now(tz=timezone.utc).timestamp())))
    op.alter_column('cloudaccount', 'type', existing_type=new_cloud_types,
                    type_=old_cloud_types, nullable=False)
