"""empty message

Revision ID: 2a7cf641066b
Revises: 5c06451a77b7
Create Date: 2020-12-05 17:54:44.267762

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2a7cf641066b'
down_revision = '5c06451a77b7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('gym_instructors',
    sa.Column('user', sa.Integer(), nullable=False),
    sa.Column('gym', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['gym'], ['gyms.id'], ),
    sa.ForeignKeyConstraint(['user'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user', 'gym')
    )
    # ### end Alembic commands ###


def downgrade():
    op.drop_table('gym_instructors')
    # ### end Alembic commands ###
