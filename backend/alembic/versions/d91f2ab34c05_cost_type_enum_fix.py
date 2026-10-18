"""cost_scenario_items.cost_type uses CostType (line-item kinds), not CostCategory

Revision ID: d91f2ab34c05
Revises: 87c762517efe
Create Date: 2026-10-18 22:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd91f2ab34c05'
down_revision: Union[str, None] = '87c762517efe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # line items are cost *kinds* (tuition, mandatory_fee, living, ...) per UI flow;
    # CostCategory describes living-cost categories and stays on living_cost_facts
    op.drop_constraint('costcategory', 'cost_scenario_items', type_='check')
    op.create_check_constraint(
        'costtype', 'cost_scenario_items',
        "cost_type IN ('tuition', 'mandatory_fee', 'living', 'insurance', "
        "'travel_visa', 'deposit', 'setup', 'contingency', 'other')")


def downgrade() -> None:
    op.drop_constraint('costtype', 'cost_scenario_items', type_='check')
    op.create_check_constraint(
        'costcategory', 'cost_scenario_items',
        "cost_type IN ('housing', 'food', 'transport', 'insurance', "
        "'utilities', 'personal', 'other')")
