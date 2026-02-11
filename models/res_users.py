# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResUsers(models.Model):
    """Extend res.users to add trainer filtering support."""
    _inherit = 'res.users'

    is_rto_trainer = fields.Boolean(
        string='Is RTO Trainer',
        compute='_compute_is_rto_trainer',
        store=True,
        help='Computed field to identify users with RTO Trainer role.',
    )

    @api.depends('group_ids')
    def _compute_is_rto_trainer(self):
        """Check if user belongs to the RTO Trainer group."""
        trainer_group = self.env.ref('rto_user_role.group_rto_trainer', raise_if_not_found=False)
        for user in self:
            if trainer_group:
                user.is_rto_trainer = trainer_group in user.group_ids
            else:
                user.is_rto_trainer = False
