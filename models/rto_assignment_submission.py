# -*- coding: utf-8 -*-
"""RTO Assignment Submission"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class RtoAssignmentSubmission(models.Model):
    _name = 'rto.assignment.submission'
    _description = 'Assignment Submission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # IDENTIFICATION
    display_name = fields.Char(
        compute='_compute_display_name',
        store=True
    )
    submission_reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default=lambda self: _('New')
    )

    # RELATIONSHIPS
    assignment_id = fields.Many2one(
        'rto.assignment',
        string='Assignment',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    course_id = fields.Many2one(
        related='assignment_id.course_id',
        string='Course',
        store=True,
        index=True
    )
    slide_id = fields.Many2one(
        related='assignment_id.slide_id',
        string='Activity',
        store=True,
        index=True
    )
    user_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        default=lambda self: self.env.user.partner_id,
        ondelete='restrict',
        index=True,
        tracking=True
    )

    # ATTEMPT TRACKING
    attempt_number = fields.Integer(
        string='Attempt #',
        default=1,
        readonly=True,
        copy=False
    )

    # STATE MACHINE
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
    ], string='Status', default='draft', required=True,
       tracking=True, index=True)

    # FILE ATTACHMENTS
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'rto_assignment_submission_attachment_rel',
        'submission_id',
        'attachment_id',
        string='Submitted Files',
        help='Files uploaded by student'
    )
    attachment_count = fields.Integer(
        compute='_compute_attachment_count',
        string='File Count'
    )

    # TIMESTAMPS
    created_on = fields.Datetime(
        string='Created On',
        default=fields.Datetime.now,
        readonly=True
    )
    submitted_on = fields.Datetime(
        string='Submitted On',
        readonly=True,
        tracking=True
    )
    graded_on = fields.Datetime(
        string='Graded On',
        readonly=True,
        tracking=True
    )

    # GRADING
    grade = fields.Float(
        string='Grade',
        digits=(5, 2),
        tracking=True,
        help='Grade assigned by trainer/assessor'
    )
    grade_percentage = fields.Float(
        compute='_compute_grade_percentage',
        store=True,
        string='Grade %'
    )
    passed = fields.Boolean(
        compute='_compute_passed',
        store=True,
        string='Passed'
    )
    grader_id = fields.Many2one(
        'res.users',
        string='Graded By',
        readonly=True,
        tracking=True
    )
    feedback = fields.Html(
        string='Grader Feedback',
        sanitize_attributes=False,
        tracking=False
    )
    feedback_attachment_ids = fields.Many2many(
        'ir.attachment',
        'rto_assignment_submission_feedback_attachment_rel',
        'submission_id',
        'attachment_id',
        string='Feedback Files',
        help='Files attached by grader as feedback'
    )
    feedback_attachment_count = fields.Integer(
        compute='_compute_feedback_attachment_count',
        string='Feedback File Count'
    )

    # LATE SUBMISSION
    is_late = fields.Boolean(
        compute='_compute_is_late',
        store=True,
        string='Late Submission'
    )

    # OUTCOME LINKING
    outcome_id = fields.Many2one(
        'rto.assessment.outcome',
        string='Assessment Outcome',
        readonly=True,
        ondelete='set null',
        help='Link to created assessment outcome record'
    )

    # EVIDENCE LINKING
    evidence_log_ids = fields.One2many(
        'rto.evidence.log',
        compute='_compute_evidence_log_ids',
        string='Evidence Records'
    )

    # SQL CONSTRAINTS
    _sql_constraints = [
        ('unique_attempt',
         'unique(assignment_id, user_id, attempt_number)',
         'Attempt number must be unique per student and assignment.')
    ]

    # COMPUTED FIELDS
    @api.depends('assignment_id.name', 'user_id.name', 'attempt_number')
    def _compute_display_name(self):
        for submission in self:
            if submission.submission_reference and submission.submission_reference != _('New'):
                submission.display_name = submission.submission_reference
            else:
                assignment_name = submission.assignment_id.name or 'Assignment'
                student_name = submission.user_id.name or 'Student'
                submission.display_name = f"{assignment_name} - {student_name} (Attempt {submission.attempt_number})"

    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        for submission in self:
            submission.attachment_count = len(submission.attachment_ids)

    @api.depends('feedback_attachment_ids')
    def _compute_feedback_attachment_count(self):
        for submission in self:
            submission.feedback_attachment_count = len(submission.feedback_attachment_ids)

    @api.depends('grade', 'assignment_id.max_grade')
    def _compute_grade_percentage(self):
        for submission in self:
            if submission.assignment_id.max_grade > 0:
                submission.grade_percentage = (submission.grade / submission.assignment_id.max_grade) * 100
            else:
                submission.grade_percentage = 0.0

    @api.depends('grade_percentage', 'assignment_id.pass_grade', 'state')
    def _compute_passed(self):
        for submission in self:
            submission.passed = bool(
                submission.state == 'graded' and
                submission.grade_percentage >= submission.assignment_id.pass_grade
            )

    @api.depends('submitted_on', 'assignment_id.due_date')
    def _compute_is_late(self):
        for submission in self:
            if submission.submitted_on and submission.assignment_id.due_date:
                submission.is_late = submission.submitted_on > submission.assignment_id.due_date
            else:
                submission.is_late = False

    def _compute_evidence_log_ids(self):
        """Find evidence log entries for this submission"""
        for submission in self:
            domain = [
                ('student_id', '=', submission.user_id.id),
                ('activity_id', '=', submission.slide_id.id),
                ('evidence_type', 'in', ['submission', 'outcome']),
            ]
            submission.evidence_log_ids = self.env['rto.evidence.log'].search(domain)

    # CRUD OVERRIDES
    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference and attempt number on create"""
        for vals in vals_list:
            # Generate reference
            if vals.get('submission_reference', _('New')) == _('New'):
                vals['submission_reference'] = self.env['ir.sequence'].sudo().next_by_code(
                    'rto.assignment.submission'
                ) or _('New')

            # Auto-increment attempt number
            if not vals.get('attempt_number') and vals.get('assignment_id') and vals.get('user_id'):
                existing_count = self.search_count([
                    ('assignment_id', '=', vals['assignment_id']),
                    ('user_id', '=', vals['user_id']),
                ])
                vals['attempt_number'] = existing_count + 1

        return super().create(vals_list)

    # BUSINESS METHODS
    def action_submit(self):
        """Submit assignment for grading"""
        self.ensure_one()

        if self.state != 'draft':
            raise UserError(_('Only draft submissions can be submitted.'))

        # Validate files uploaded
        if not self.attachment_ids:
            raise UserError(_('You must upload at least one file before submitting.'))

        # Check max files
        if self.assignment_id.max_files > 0 and len(self.attachment_ids) > self.assignment_id.max_files:
            raise UserError(_('Maximum %d files allowed.') % self.assignment_id.max_files)

        # Check cut-off date
        if self.assignment_id.is_past_cutoff:
            raise UserError(_('The cut-off date has passed. Submissions are no longer accepted.'))

        # Update state
        self.write({
            'state': 'submitted',
            'submitted_on': fields.Datetime.now(),
        })

        # Create evidence log
        self._create_submission_evidence()

        # Notify trainer
        self._notify_submission()

        return True

    def action_grade(self, grade, feedback=None, feedback_attachments=None):
        """
        Grade a submission.

        Args:
            grade: Float grade value
            feedback: HTML feedback text (optional)
            feedback_attachments: ir.attachment recordset (optional)
        """
        self.ensure_one()

        if self.state != 'submitted':
            raise UserError(_('Only submitted assignments can be graded.'))

        # Validate grade
        if grade < 0 or grade > self.assignment_id.max_grade:
            raise ValidationError(_('Grade must be between 0 and %s') % self.assignment_id.max_grade)

        # Update submission
        vals = {
            'state': 'graded',
            'grade': grade,
            'feedback': feedback,
            'graded_on': fields.Datetime.now(),
            'grader_id': self.env.user.id,
        }

        if feedback_attachments:
            vals['feedback_attachment_ids'] = [(6, 0, feedback_attachments.ids)]

        self.write(vals)

        # Create assessment outcome
        self._create_assessment_outcome()

        # Create evidence log for grading
        self._create_grading_evidence()

        # Trigger slide completion if passed
        if self.passed:
            self._trigger_slide_completion()

        # Notify student
        self._notify_grading()

        return True

    def action_reopen(self):
        """Reopen submission for resubmission"""
        self.ensure_one()

        if self.state != 'graded':
            raise UserError(_('Only graded submissions can be reopened.'))

        if not self.assignment_id.allow_resubmission:
            raise UserError(_('Resubmission is not allowed for this assignment.'))

        # Check max attempts
        attempt_count = self.search_count([
            ('assignment_id', '=', self.assignment_id.id),
            ('user_id', '=', self.user_id.id),
        ])

        if self.assignment_id.max_attempts > 0 and attempt_count >= self.assignment_id.max_attempts:
            raise UserError(_('Maximum attempts (%d) reached.') % self.assignment_id.max_attempts)

        # Create new draft submission
        new_submission = self.create({
            'assignment_id': self.assignment_id.id,
            'user_id': self.user_id.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'rto.assignment.submission',
            'res_id': new_submission.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _create_submission_evidence(self):
        """Create immutable evidence log on submission"""
        self.ensure_one()

        evidence_data = {
            'submission_reference': self.submission_reference,
            'attempt_number': self.attempt_number,
            'submitted_on': str(self.submitted_on),
            'file_count': len(self.attachment_ids),
            'is_late': self.is_late,
        }

        self.env['rto.evidence.log'].sudo().create({
            'course_id': self.course_id.id,
            'activity_id': self.slide_id.id,
            'student_id': self.user_id.id,
            'evidence_type': 'submission',
            'summary': f'Assignment submission: {self.assignment_id.name} (Attempt {self.attempt_number})',
            'evidence_data': str(evidence_data),
            'evidence_text': f'Submitted {len(self.attachment_ids)} file(s) {"(LATE)" if self.is_late else ""}',
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
            'actor_type': 'student',
            'actor_id': self.user_id.id,
        })

    def _create_grading_evidence(self):
        """Create immutable evidence log on grading"""
        self.ensure_one()

        evidence_data = {
            'submission_reference': self.submission_reference,
            'grade': self.grade,
            'max_grade': self.assignment_id.max_grade,
            'grade_percentage': self.grade_percentage,
            'passed': self.passed,
            'grader_id': self.grader_id.id,
            'grader_name': self.grader_id.name,
            'graded_on': str(self.graded_on),
        }

        self.env['rto.evidence.log'].sudo().create({
            'course_id': self.course_id.id,
            'activity_id': self.slide_id.id,
            'student_id': self.user_id.id,
            'evidence_type': 'outcome',
            'summary': f'Assignment graded: {self.grade}/{self.assignment_id.max_grade} ({"PASS" if self.passed else "FAIL"})',
            'evidence_data': str(evidence_data),
            'evidence_text': self.feedback or '',
            'attachment_ids': [(6, 0, self.feedback_attachment_ids.ids)],
            'actor_type': 'assessor',
            'actor_id': self.grader_id.partner_id.id if self.grader_id.partner_id else False,
        })

    def _create_assessment_outcome(self):
        """Create rto.assessment.outcome record"""
        self.ensure_one()

        # Resolve assessor employee
        assessor = self.env.user.employee_ids[:1]
        if not assessor:
            raise ValidationError(_('The current user must have an employee record to grade submissions.'))

        # Determine outcome code
        outcome_code = '20' if self.passed else '30'  # 20=Competent, 30=Not Competent

        outcome_vals = {
            'course_id': self.course_id.id,
            'activity_id': self.slide_id.id,
            'student_id': self.user_id.id,
            'outcome_level': 'activity',
            'outcome_code': outcome_code,
            'assessor_id': assessor.id,
            'assessor_comments': self.feedback or f'Assignment submission graded: {self.grade}/{self.assignment_id.max_grade}',
            'attempt_number': self.attempt_number,
            'score': self.grade,
            'max_score': self.assignment_id.max_grade,
        }

        self.outcome_id = self.env['rto.assessment.outcome'].create(outcome_vals)

    def _trigger_slide_completion(self):
        """Mark slide as complete if passed"""
        self.ensure_one()

        # Find slide.slide.partner record
        slide_partner = self.env['slide.slide.partner'].search([
            ('slide_id', '=', self.slide_id.id),
            ('partner_id', '=', self.user_id.id),
        ], limit=1)

        if slide_partner and not slide_partner.completed:
            slide_partner.write({'completed': True})
            # This will trigger _recompute_completion on slide.channel.partner

    def _notify_submission(self):
        """Notify trainer of new submission"""
        self.ensure_one()
        # Use mail.thread to post message
        self.message_post(
            body=_('Assignment submitted by %s (Attempt %d)') % (self.user_id.name, self.attempt_number),
            subject=_('New Assignment Submission'),
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )

    def _notify_grading(self):
        """Notify student of grading"""
        self.ensure_one()
        # Use mail.thread to post message
        self.message_post(
            body=_('Your assignment has been graded: %s/%s (%s)') % (
                self.grade, self.assignment_id.max_grade,
                'PASS' if self.passed else 'NOT YET COMPETENT'
            ),
            subject=_('Assignment Graded'),
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.user_id.id],
        )
