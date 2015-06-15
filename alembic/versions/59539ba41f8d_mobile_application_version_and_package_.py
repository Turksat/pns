"""mobile application version and package name

Revision ID: 59539ba41f8d
Revises: 
Create Date: 2015-06-12 10:59:03.539115

"""

# revision identifiers, used by Alembic.
revision = '59539ba41f8d'
down_revision = None
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('device', sa.Column('mobile_app_id', sa.Text, index=True))
    op.add_column('device', sa.Column('mobile_app_ver', sa.Integer, index=True))


def downgrade():
    op.drop_column('device', 'mobile_app_id')
    op.drop_column('device', 'mobile_app_ver')
