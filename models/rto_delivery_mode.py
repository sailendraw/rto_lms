# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""
RTO Delivery Mode
=================

Stores delivery modes for unit delivery aligned with AVETMISS specifications.

AVETMISS Delivery Mode Identifier (Element 429):
- 10: Internal (classroom-based)
- 20: External (distance education)
- 30: Workplace-based
- 40: Online (electronic-based)
- 90: Not applicable
- 99: Not specified

Note: Blended delivery is typically coded as the predominant mode.
"""

from odoo import api, fields, models


class RtoDeliveryMode(models.Model):
    """
    Delivery Mode for RTO courses.

    Aligned with AVETMISS Element 429 - Delivery Mode Identifier.
    """
    _name = 'rto.delivery.mode'
    _description = 'RTO Delivery Mode'
    _order = 'sequence, avetmiss_code'
    _rec_name = 'display_name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
        help='User-friendly name for the delivery mode.',
    )
    avetmiss_code = fields.Char(
        string='AVETMISS Code',
        size=2,
        required=True,
        help='AVETMISS Delivery Mode Identifier (Element 429).',
    )
    description = fields.Text(
        string='Description',
        translate=True,
        help='Detailed description of when to use this delivery mode.',
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    # Classification flags
    is_face_to_face = fields.Boolean(
        string='Face-to-Face Component',
        default=False,
        help='Whether this mode includes face-to-face delivery.',
    )
    is_online = fields.Boolean(
        string='Online Component',
        default=False,
        help='Whether this mode includes online/electronic delivery.',
    )
    is_workplace = fields.Boolean(
        string='Workplace Component',
        default=False,
        help='Whether this mode includes workplace-based delivery.',
    )

    _avetmiss_code_unique = models.Constraint(
        'UNIQUE(avetmiss_code)',
        'AVETMISS Code must be unique!',
    )

    @api.depends('name', 'avetmiss_code')
    def _compute_display_name(self):
        for record in self:
            if record.avetmiss_code and record.name:
                record.display_name = f"[{record.avetmiss_code}] {record.name}"
            else:
                record.display_name = record.name or 'New'
