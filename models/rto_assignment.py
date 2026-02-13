# -*- coding: utf-8 -*-
"""RTO Assignment - File Submission Only"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

class RtoAssignment(models.Model):
    _name = 'rto.assignment'
    _description = 'RTO Assignment (File Submission)'
    _inherit = ['mail.thread']
    _order = 'create_date desc'

    # IDENTIFICATION
    name = fields.Char(
        string='Assignment Name',
        required=True,
        tracking=True
    )
    slide_id = fields.Many2one(
        'slide.slide',
        string='Activity Slide',
        required=False,
        ondelete='cascade',
        help='The slide/activity this assignment belongs to'
    )
    course_id = fields.Many2one(
        related='slide_id.channel_id',
        string='Course',
        store=True,
        index=True
    )

    # CONTENT
    description = fields.Html(
        string='Description',
        sanitize_attributes=False,
        help='Overview of the assignment visible to students'
    )
    instructions = fields.Html(
        string='Instructions',
        sanitize_attributes=False,
        help='Detailed instructions for completing the assignment'
    )

    # AVAILABILITY
    allow_submission_from = fields.Datetime(
        string='Allow Submissions From',
        help='Students can submit from this date/time. Leave blank for immediate availability.'
    )
    due_date = fields.Datetime(
        string='Due Date',
        tracking=True,
        help='Expected submission deadline. Submissions after this are marked as late.'
    )
    cut_off_date = fields.Datetime(
        string='Cut-off Date',
        tracking=True,
        help='Hard deadline. No submissions accepted after this date.'
    )
    always_show_description = fields.Boolean(
        string='Always Show Description',
        default=True,
        help='Show description even before allow_submission_from date'
    )

    # FILE SETTINGS
    max_files = fields.Integer(
        string='Maximum Files',
        default=5,
        help='Maximum number of files student can upload. 0 = unlimited.'
    )
    max_file_size_mb = fields.Integer(
        string='Max File Size (MB)',
        default=10,
        help='Maximum size per file in megabytes'
    )
    accepted_file_types = fields.Char(
        string='Accepted File Types',
        default='pdf,doc,docx,xls,xlsx,ppt,pptx,jpg,jpeg,png,zip',
        help='Comma-separated list of allowed extensions (e.g., pdf,docx,jpg)'
    )
    require_submit_button = fields.Boolean(
        string='Require Explicit Submit',
        default=True,
        help='If True, students must click Submit. If False, draft saves trigger submission.'
    )

    # RESUBMISSION
    allow_resubmission = fields.Boolean(
        string='Allow Resubmission',
        default=True,
        help='Allow students to submit multiple times'
    )
    max_attempts = fields.Integer(
        string='Maximum Attempts',
        default=3,
        help='Maximum number of submission attempts. 0 = unlimited.'
    )
    reopen_method = fields.Selection([
        ('manual', 'Manual (Trainer reopens)'),
        ('auto_until_pass', 'Automatic until pass'),
        ('auto_unlimited', 'Automatic unlimited'),
    ], string='Reopen Method', default='manual',
       help='How resubmissions are enabled after grading')

    # GRADING
    grading_type = fields.Selection([
        ('points', 'Points (0-100)'),
        ('pass_fail', 'Pass/Fail Only'),
        ('scale', 'Custom Scale'),
    ], string='Grading Type', default='points', required=True, tracking=True)

    max_grade = fields.Float(
        string='Maximum Grade',
        default=100.0,
        digits=(5, 2),
        help='Maximum points/grade for this assignment'
    )
    pass_grade = fields.Float(
        string='Pass Grade',
        default=50.0,
        digits=(5, 2),
        help='Minimum grade required to pass (triggers competency)'
    )

    # STATISTICS
    submission_ids = fields.One2many(
        'rto.assignment.submission',
        'assignment_id',
        string='Submissions'
    )
    submission_count = fields.Integer(
        compute='_compute_submission_count',
        string='Total Submissions'
    )
    graded_count = fields.Integer(
        compute='_compute_graded_count',
        string='Graded Submissions'
    )

    # COMPUTED
    is_available = fields.Boolean(
        compute='_compute_is_available',
        string='Currently Available'
    )
    is_past_due = fields.Boolean(
        compute='_compute_is_past_due',
        string='Past Due Date'
    )
    is_past_cutoff = fields.Boolean(
        compute='_compute_is_past_cutoff',
        string='Past Cut-off'
    )

    @api.depends('submission_ids')
    def _compute_submission_count(self):
        for assignment in self:
            assignment.submission_count = len(assignment.submission_ids)

    @api.depends('submission_ids.state')
    def _compute_graded_count(self):
        for assignment in self:
            assignment.graded_count = len(assignment.submission_ids.filtered(lambda s: s.state == 'graded'))

    @api.depends('allow_submission_from', 'cut_off_date')
    def _compute_is_available(self):
        now = fields.Datetime.now()
        for assignment in self:
            start_ok = not assignment.allow_submission_from or assignment.allow_submission_from <= now
            end_ok = not assignment.cut_off_date or assignment.cut_off_date >= now
            assignment.is_available = start_ok and end_ok

    @api.depends('due_date')
    def _compute_is_past_due(self):
        now = fields.Datetime.now()
        for assignment in self:
            assignment.is_past_due = bool(assignment.due_date and assignment.due_date < now)

    @api.depends('cut_off_date')
    def _compute_is_past_cutoff(self):
        now = fields.Datetime.now()
        for assignment in self:
            assignment.is_past_cutoff = bool(assignment.cut_off_date and assignment.cut_off_date < now)

    # VALIDATION
    @api.constrains('due_date', 'cut_off_date', 'allow_submission_from')
    def _check_dates(self):
        for assignment in self:
            if assignment.allow_submission_from and assignment.due_date:
                if assignment.due_date < assignment.allow_submission_from:
                    raise ValidationError(_('Due date must be after submission start date.'))
            if assignment.due_date and assignment.cut_off_date:
                if assignment.cut_off_date < assignment.due_date:
                    raise ValidationError(_('Cut-off date must be after due date.'))

    @api.constrains('max_grade', 'pass_grade')
    def _check_grades(self):
        for assignment in self:
            if assignment.max_grade <= 0:
                raise ValidationError(_('Maximum grade must be greater than 0.'))
            if assignment.pass_grade < 0 or assignment.pass_grade > assignment.max_grade:
                raise ValidationError(_('Pass grade must be between 0 and maximum grade.'))

    @api.constrains('max_files', 'max_file_size_mb')
    def _check_file_limits(self):
        for assignment in self:
            if assignment.max_files < 0:
                raise ValidationError(_('Maximum files cannot be negative. Use 0 for unlimited.'))
            if assignment.max_file_size_mb <= 0:
                raise ValidationError(_('Maximum file size must be greater than 0 MB.'))

    @api.constrains('slide_id')
    def _check_slide_id(self):
        for assignment in self:
            if not assignment.slide_id:
                raise ValidationError(_('Assignment must be linked to an Activity Slide.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('slide_id'):
                default_slide_id = self.env.context.get('default_slide_id')
                if default_slide_id:
                    vals['slide_id'] = default_slide_id
                # Allow creation without slide_id if called from slide.create() context
                elif not self.env.context.get('allow_assignment_without_slide'):
                    raise ValidationError(_('You must select an Activity Slide before creating an assignment.'))
        return super().create(vals_list)

    # BUSINESS METHODS
    def action_view_submissions(self):
        """View all submissions for this assignment"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Submissions - %s', self.name),
            'res_model': 'rto.assignment.submission',
            'view_mode': 'tree,form',
            'domain': [('assignment_id', '=', self.id)],
            'context': {
                'default_assignment_id': self.id,
            },
        }

    def validate_file_upload(self, filename, size_bytes):
        """
        Validate file before upload.

        Args:
            filename: Name of file
            size_bytes: File size in bytes

        Returns:
            dict: {'valid': bool, 'error': str or None}
        """
        self.ensure_one()

        # Check file extension
        extension = filename.split('.')[-1].lower() if '.' in filename else ''
        allowed_extensions = [ext.strip().lower() for ext in (self.accepted_file_types or '').split(',')]

        if allowed_extensions and extension not in allowed_extensions:
            return {
                'valid': False,
                'error': _('File type .%s not allowed. Accepted types: %s') % (extension, self.accepted_file_types)
            }

        # Check file size
        max_bytes = self.max_file_size_mb * 1024 * 1024
        if size_bytes > max_bytes:
            return {
                'valid': False,
                'error': _('File size %.2f MB exceeds maximum allowed size of %d MB') % (
                    size_bytes / 1024 / 1024, self.max_file_size_mb
                )
            }

        return {'valid': True, 'error': None}
