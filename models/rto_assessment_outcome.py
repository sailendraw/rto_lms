# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""
RTO Assessment Outcome
======================

Records individual assessment outcomes for activities and aggregates them
to unit-level outcomes for AVETMISS reporting.

AVETMISS OUTCOME CODES (Element 441 - Outcome Identifier National):
    20 - Competency achieved/pass
    30 - Competency not achieved/fail
    40 - Withdrawn
    51 - Recognition of Prior Learning - granted
    52 - Recognition of Prior Learning - not granted
    53 - Recognition of Current Competency - granted
    54 - Recognition of Current Competency - not granted
    60 - Credit transfer
    65 - Gap training only
    66 - Did not start
    70 - Continuing/enrolled
    81 - Non-assessed - Satisfactorily completed
    82 - Non-assessed - Withdrawn or not completed

OUTCOME FLOW:
    1. Student completes activity (assessment, observation, etc.)
    2. Trainer/assessor records activity-level outcome
    3. System aggregates activity outcomes to unit-level outcome
    4. Unit outcome flows to AVETMISS NAT00120

IMMUTABILITY:
    Outcomes can be recorded but not deleted.
    Changes create new records with superseding chain.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class RtoAssessmentOutcome(models.Model):
    """
    Assessment outcome record for RTO compliance.

    Records outcomes at both activity level and aggregates to unit level.
    """
    _name = 'rto.assessment.outcome'
    _description = 'RTO Assessment Outcome'
    _order = 'create_date desc'
    _rec_name = 'display_name'
    _inherit = ['mail.thread']

    # =========================================================================
    # IDENTIFICATION
    # =========================================================================
    display_name = fields.Char(
        string='Reference',
        compute='_compute_display_name',
        store=True,
    )
    outcome_reference = fields.Char(
        string='Outcome Reference',
        compute='_compute_outcome_reference',
        store=True,
        index=True,
    )

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    course_id = fields.Many2one(
        comodel_name='slide.channel',
        string='Course (Unit Delivery)',
        required=True,
        index=True,
        ondelete='restrict',
        domain="[('is_rto_course', '=', True)]",
        help='The unit delivery course.',
    )
    activity_id = fields.Many2one(
        comodel_name='slide.slide',
        string='Activity',
        index=True,
        ondelete='restrict',
        domain="[('channel_id', '=', course_id), ('is_rto_assessable', '=', True)]",
        help='The specific assessment activity. Leave blank for unit-level outcomes.',
    )
    student_id = fields.Many2one(
        comodel_name='res.partner',
        string='Student',
        required=True,
        index=True,
        ondelete='restrict',
        tracking=True,
        help='The student receiving this outcome.',
    )

    # From course
    unit_id = fields.Many2one(
        related='course_id.unit_id',
        string='Unit of Competency',
        store=True,
        index=True,
    )
    unit_code = fields.Char(
        related='course_id.unit_code',
        string='Unit Code',
        store=True,
    )

    # =========================================================================
    # OUTCOME CLASSIFICATION
    # =========================================================================
    outcome_level = fields.Selection(
        selection=[
            ('activity', 'Activity Level'),
            ('unit', 'Unit Level'),
        ],
        string='Outcome Level',
        required=True,
        default='activity',
        index=True,
        help='Whether this is an activity-level or unit-level (aggregated) outcome.',
    )

    outcome_code = fields.Selection(
        selection=[
            ('20', '20 - Competency achieved/pass'),
            ('30', '30 - Competency not achieved/fail'),
            ('40', '40 - Withdrawn'),
            ('51', '51 - RPL granted'),
            ('52', '52 - RPL not granted'),
            ('53', '53 - RCC granted'),
            ('54', '54 - RCC not granted'),
            ('60', '60 - Credit transfer'),
            ('65', '65 - Gap training only'),
            ('66', '66 - Did not start'),
            ('70', '70 - Continuing/enrolled'),
            ('81', '81 - Non-assessed - satisfactorily completed'),
            ('82', '82 - Non-assessed - withdrawn or not completed'),
        ],
        string='Outcome Code',
        required=True,
        tracking=True,
        index=True,
        help='AVETMISS outcome code (Element 441).',
    )

    outcome_name = fields.Char(
        string='Outcome Name',
        compute='_compute_outcome_name',
        store=True,
    )

    # =========================================================================
    # DATES
    # =========================================================================
    outcome_date = fields.Date(
        string='Outcome Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True,
        help='Date the outcome was determined.',
    )

    # For AVETMISS NAT00120
    activity_start_date = fields.Date(
        string='Activity Start Date',
        help='Start date of training activity (for AVETMISS).',
    )
    activity_end_date = fields.Date(
        string='Activity End Date',
        help='End date of training activity (for AVETMISS).',
    )

    # =========================================================================
    # ASSESSOR DETAILS
    # =========================================================================
    assessor_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Assessor',
        required=True,
        tracking=True,
        domain="[('is_trainer', '=', True)]",
        help='The trainer/assessor who determined this outcome.',
    )
    assessor_name = fields.Char(
        related='assessor_id.name',
        string='Assessor Name',
        store=True,
    )

    assessor_comments = fields.Text(
        string='Assessor Comments',
        tracking=True,
        help='Comments or feedback from the assessor.',
    )

    # =========================================================================
    # ASSESSMENT DETAILS
    # =========================================================================
    attempt_number = fields.Integer(
        string='Attempt Number',
        default=1,
        help='Which attempt this outcome is for.',
    )

    score = fields.Float(
        string='Score',
        digits=(5, 2),
        help='Numerical score if applicable.',
    )
    max_score = fields.Float(
        string='Maximum Score',
        digits=(5, 2),
        help='Maximum possible score.',
    )
    score_percentage = fields.Float(
        string='Score (%)',
        compute='_compute_score_percentage',
        store=True,
        digits=(5, 2),
    )

    # =========================================================================
    # COMPETENCY DETERMINATION
    # =========================================================================
    is_competent = fields.Boolean(
        string='Competent',
        compute='_compute_is_competent',
        store=True,
        help='Whether this outcome indicates competency.',
    )

    competency_decision = fields.Selection(
        selection=[
            ('competent', 'Competent (C)'),
            ('not_yet_competent', 'Not Yet Competent (NYC)'),
            ('not_competent', 'Not Competent (NC)'),
            ('withdrawn', 'Withdrawn (W)'),
            ('credit_transfer', 'Credit Transfer (CT)'),
            ('rpl', 'Recognition of Prior Learning (RPL)'),
        ],
        string='Competency Decision',
        tracking=True,
        help='Competency decision for RTO reporting.',
    )

    # =========================================================================
    # EVIDENCE LINKING
    # =========================================================================
    evidence_log_ids = fields.One2many(
        comodel_name='rto.evidence.log',
        compute='_compute_evidence_log_ids',
        string='Related Evidence',
        help='Evidence records supporting this outcome.',
    )
    evidence_count = fields.Integer(
        string='Evidence Count',
        compute='_compute_evidence_count',
    )

    # =========================================================================
    # MODERATION/VALIDATION
    # =========================================================================
    is_moderated = fields.Boolean(
        string='Moderated',
        default=False,
        tracking=True,
        help='Whether this outcome has been moderated/validated.',
    )
    moderator_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Moderator',
        tracking=True,
        help='The person who moderated this outcome.',
    )
    moderation_date = fields.Date(
        string='Moderation Date',
        tracking=True,
    )
    moderation_notes = fields.Text(
        string='Moderation Notes',
    )

    # =========================================================================
    # VERSIONING (for audit trail)
    # =========================================================================
    version = fields.Integer(
        string='Version',
        default=1,
        readonly=True,
    )
    supersedes_id = fields.Many2one(
        comodel_name='rto.assessment.outcome',
        string='Supersedes',
        readonly=True,
        ondelete='restrict',
    )
    superseded_by_id = fields.Many2one(
        comodel_name='rto.assessment.outcome',
        string='Superseded By',
        readonly=True,
        ondelete='restrict',
    )
    is_current = fields.Boolean(
        string='Is Current Version',
        default=True,
        index=True,
    )

    # =========================================================================
    # AVETMISS SYNC
    # =========================================================================
    nat00120_synced = fields.Boolean(
        string='Synced to NAT00120',
        default=False,
        help='Whether this outcome has been synced to AVETMISS NAT00120.',
    )
    nat00120_sync_date = fields.Datetime(
        string='NAT00120 Sync Date',
    )

    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================

    @api.depends('outcome_code', 'student_id', 'unit_code')
    def _compute_display_name(self):
        for record in self:
            student_name = record.student_id.name or 'Unknown'
            unit = record.unit_code or 'Unit'
            record.display_name = f"{unit} - {student_name} - {record.outcome_code}"

    @api.depends('create_date')
    def _compute_outcome_reference(self):
        for record in self:
            if record.id and record.create_date:
                date_str = record.create_date.strftime('%Y%m%d')
                record.outcome_reference = f"OUT-{date_str}-{record.id:06d}"
            else:
                record.outcome_reference = False

    @api.depends('outcome_code')
    def _compute_outcome_name(self):
        """Extract readable outcome name."""
        outcome_names = {
            '20': 'Competency achieved',
            '30': 'Competency not achieved',
            '40': 'Withdrawn',
            '51': 'RPL granted',
            '52': 'RPL not granted',
            '53': 'RCC granted',
            '54': 'RCC not granted',
            '60': 'Credit transfer',
            '65': 'Gap training only',
            '66': 'Did not start',
            '70': 'Continuing',
            '81': 'Satisfactorily completed',
            '82': 'Not completed',
        }
        for record in self:
            record.outcome_name = outcome_names.get(record.outcome_code, 'Unknown')

    @api.depends('outcome_code')
    def _compute_is_competent(self):
        """Determine if outcome indicates competency."""
        competent_codes = ('20', '51', '53', '60', '81')
        for record in self:
            record.is_competent = record.outcome_code in competent_codes

    @api.depends('score', 'max_score')
    def _compute_score_percentage(self):
        for record in self:
            if record.max_score and record.max_score > 0:
                record.score_percentage = (record.score / record.max_score) * 100
            else:
                record.score_percentage = 0.0

    def _compute_evidence_log_ids(self):
        """Find related evidence records."""
        for record in self:
            domain = [
                ('student_id', '=', record.student_id.id),
                ('course_id', '=', record.course_id.id),
            ]
            if record.activity_id:
                domain.append(('activity_id', '=', record.activity_id.id))
            record.evidence_log_ids = self.env['rto.evidence.log'].search(domain)

    def _compute_evidence_count(self):
        for record in self:
            record.evidence_count = len(record.evidence_log_ids)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    @api.constrains('outcome_date', 'activity_start_date', 'activity_end_date')
    def _check_dates(self):
        """Validate date consistency."""
        for record in self:
            if record.activity_start_date and record.activity_end_date:
                if record.activity_end_date < record.activity_start_date:
                    raise ValidationError(_(
                        'Activity end date cannot be before start date.'
                    ))
            if record.activity_end_date and record.outcome_date:
                if record.outcome_date < record.activity_end_date:
                    pass  # Outcome can be before activity end in some cases

    @api.constrains('attempt_number')
    def _check_attempt_number(self):
        for record in self:
            if record.attempt_number < 1:
                raise ValidationError(_('Attempt number must be at least 1.'))

    # =========================================================================
    # ONCHANGE
    # =========================================================================

    @api.onchange('outcome_code')
    def _onchange_outcome_code(self):
        """Set competency decision based on outcome code."""
        mapping = {
            '20': 'competent',
            '30': 'not_yet_competent',
            '40': 'withdrawn',
            '51': 'rpl',
            '52': 'not_competent',
            '53': 'competent',
            '54': 'not_competent',
            '60': 'credit_transfer',
        }
        if self.outcome_code in mapping:
            self.competency_decision = mapping[self.outcome_code]

    # =========================================================================
    # CRUD OVERRIDES
    # =========================================================================

    def unlink(self):
        """Prevent deletion - outcomes must be superseded, not deleted."""
        raise UserError(_(
            'Assessment outcomes cannot be deleted. '
            'Use the supersede function to record a corrected outcome.'
        ))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to auto-generate evidence log entry."""
        records = super().create(vals_list)

        # Create evidence log entry for each outcome
        for record in records:
            assessor = record.assessor_id
            assessor_home = getattr(assessor, 'address_home_id', False)
            assessor_user = getattr(assessor, 'user_id', False)
            actor_partner = assessor_home or (assessor_user.partner_id if assessor_user else False)
            self.env['rto.evidence.log'].create({
                'company_id': record.company_id.id,
                'course_id': record.course_id.id,
                'activity_id': record.activity_id.id if record.activity_id else False,
                'student_id': record.student_id.id,
                'evidence_type': 'outcome',
                'summary': f"Assessment outcome recorded: {record.outcome_code} - {record.outcome_name}",
                'evidence_data': {
                    'outcome_reference': record.outcome_reference,
                    'outcome_code': record.outcome_code,
                    'assessor_id': record.assessor_id.id,
                    'assessor_name': record.assessor_name,
                    'outcome_date': str(record.outcome_date),
                    'attempt_number': record.attempt_number,
                    'is_competent': record.is_competent,
                },
                'actor_type': 'assessor',
                'actor_id': actor_partner.id if actor_partner else False,
            })

        return records

    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================

    def supersede(self, new_outcome_code, reason, assessor_id=None):
        """
        Create a new outcome that supersedes this one.

        Used when an outcome needs to be corrected (e.g., appeal granted).
        """
        self.ensure_one()

        if not reason:
            raise UserError(_('A reason must be provided when superseding an outcome.'))

        if not self.is_current:
            raise UserError(_('Cannot supersede an outcome that has already been superseded.'))

        new_record = self.create({
            'company_id': self.company_id.id,
            'course_id': self.course_id.id,
            'activity_id': self.activity_id.id if self.activity_id else False,
            'student_id': self.student_id.id,
            'outcome_level': self.outcome_level,
            'outcome_code': new_outcome_code,
            'outcome_date': fields.Date.today(),
            'assessor_id': assessor_id or self.assessor_id.id,
            'assessor_comments': f"SUPERSEDES: {self.outcome_reference}\nREASON: {reason}\n\n{self.assessor_comments or ''}",
            'attempt_number': self.attempt_number,
            'version': self.version + 1,
            'supersedes_id': self.id,
        })

        # Mark old record as superseded
        super(RtoAssessmentOutcome, self).write({
            'superseded_by_id': new_record.id,
            'is_current': False,
        })

        return new_record

    def action_moderate(self):
        """Open moderation wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Moderate Outcome'),
            'res_model': 'rto.assessment.outcome.moderate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_outcome_id': self.id},
        }

    def action_view_evidence(self):
        """View related evidence."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Related Evidence'),
            'res_model': 'rto.evidence.log',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.evidence_log_ids.ids)],
        }

    def action_sync_to_nat00120(self):
        """Sync outcome to AVETMISS NAT00120."""
        for record in self:
            if record.outcome_level != 'unit':
                raise UserError(_(
                    'Only unit-level outcomes can be synced to NAT00120. '
                    'Activity outcomes are aggregated first.'
                ))
            # TODO: Implement actual NAT00120 sync
            record.write({
                'nat00120_synced': True,
                'nat00120_sync_date': fields.Datetime.now(),
            })

    # =========================================================================
    # AGGREGATION METHODS
    # =========================================================================

    @api.model
    def aggregate_unit_outcome(self, course_id, student_id, assessor_id):
        """
        Aggregate activity-level outcomes to determine unit-level outcome.

        Logic:
        1. All critical assessments must be passed
        2. Weighted average of non-critical assessments
        3. Overall: If all critical passed AND weighted >= threshold → Competent
        """
        course = self.env['slide.channel'].browse(course_id)
        activities = course.slide_ids.filtered(lambda s: s.is_rto_assessable)

        activity_outcomes = self.search([
            ('course_id', '=', course_id),
            ('student_id', '=', student_id),
            ('outcome_level', '=', 'activity'),
            ('is_current', '=', True),
        ])

        # Check all critical activities
        critical_activities = activities.filtered('is_critical')
        critical_outcomes = activity_outcomes.filtered(
            lambda o: o.activity_id in critical_activities
        )

        # All critical must be competent
        all_critical_passed = all(o.is_competent for o in critical_outcomes)

        # Calculate weighted average for non-critical
        non_critical = activity_outcomes.filtered(
            lambda o: o.activity_id and not o.activity_id.is_critical
        )
        weighted_sum = sum(
            o.score_percentage * (o.activity_id.weighting / 100)
            for o in non_critical if o.activity_id.weighting > 0
        )

        # Determine unit outcome
        if all_critical_passed and (not non_critical or weighted_sum >= 50):
            outcome_code = '20'  # Competent
        else:
            outcome_code = '70'  # Continuing (not yet determined)

        # Create or update unit-level outcome
        existing = self.search([
            ('course_id', '=', course_id),
            ('student_id', '=', student_id),
            ('outcome_level', '=', 'unit'),
            ('is_current', '=', True),
        ], limit=1)

        if existing:
            if existing.outcome_code != outcome_code:
                return existing.supersede(outcome_code, 'Automated aggregation update', assessor_id)
            return existing
        else:
            return self.create({
                'course_id': course_id,
                'student_id': student_id,
                'outcome_level': 'unit',
                'outcome_code': outcome_code,
                'assessor_id': assessor_id,
                'assessor_comments': 'Aggregated from activity outcomes.',
            })
