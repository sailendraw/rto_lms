# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""
slide.slide Extension - RTO Learning Activities
================================================

This extension transforms Odoo's slide.slide into RTO-compliant learning activities
including assessments, observations, and evidence uploads.

ACTIVITY TYPES:
    - learning: Standard learning content (videos, documents, articles)
    - assessment: Formal assessments requiring marking
    - observation: Workplace observations requiring sign-off
    - evidence: Evidence upload points for students
    - practical: Practical demonstrations

ASQA COMPLIANCE:
    Standard 1.8: Assessment conditions replicate workplace context
    Standard 2.2: Evidence gathered is valid, sufficient, authentic, current

AVETMISS:
    Assessment outcomes map to NAT00120 outcome codes:
    - 20: Competency achieved/pass
    - 30: Competency not achieved/fail
    - 40: Withdrawn
    - 60: Credit transfer
    - 70: Continuing/enrolled
"""

import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class SlideSlide(models.Model):
    """
    Extended slide.slide for RTO learning activities.

    Adds assessment tracking, evidence requirements, and outcome recording.
    """
    _inherit = 'slide.slide'

    # =========================================================================
    # ASSIGNMENT INTEGRATION
    # =========================================================================
    # Extend slide_category to add 'assignment' option
    slide_category = fields.Selection(
        selection_add=[('assignment', 'Assignment')],
        ondelete={'assignment': 'cascade'}
    )

    # Statistics field for when this slide is a category
    nbr_assignment = fields.Integer(
        string='Number of Assignments',
        compute='_compute_slides_statistics',
        store=True,
        help='Number of assignment slides under this category.',
    )

    # =========================================================================
    # RTO ACTIVITY TYPE
    # =========================================================================
    rto_activity_type = fields.Selection(
        selection=[
            ('learning', 'Learning Content'),
            ('assessment', 'Assessment'),
            ('observation', 'Observation'),
            ('evidence', 'Evidence Upload'),
            ('practical', 'Practical Demonstration'),
        ],
        string='Activity Type',
        default='learning',
        tracking=True,
        help='Type of RTO activity. '
             'Assessments and observations require formal outcomes.',
    )

    is_rto_assessable = fields.Boolean(
        string='Requires Assessment',
        compute='_compute_is_rto_assessable',
        store=True,
        help='Whether this activity requires formal assessment/marking.',
    )

    # =========================================================================
    # ASSESSMENT DETAILS
    # =========================================================================
    assessment_method = fields.Selection(
        selection=[
            ('written', 'Written Assessment'),
            ('practical', 'Practical Assessment'),
            ('oral', 'Oral/Verbal Assessment'),
            ('observation', 'Workplace Observation'),
            ('portfolio', 'Portfolio Evidence'),
            ('third_party', 'Third Party Report'),
            ('rpl', 'Recognition of Prior Learning'),
        ],
        string='Assessment Method',
        tracking=True,
        help='Method used to assess this activity.',
    )

    assessment_instructions = fields.Html(
        string='Assessment Instructions',
        translate=True,
        sanitize_attributes=False,
        help='Instructions provided to the student for completing this assessment.',
    )

    marking_guide = fields.Html(
        string='Marking Guide',
        translate=True,
        sanitize_attributes=False,
        groups='website_slides.group_website_slides_officer',
        help='Internal marking guide for trainers/assessors.',
    )

    # =========================================================================
    # EVIDENCE REQUIREMENTS
    # =========================================================================
    evidence_required = fields.Boolean(
        string='Evidence Required',
        default=False,
        help='Whether students must upload evidence for this activity.',
    )

    evidence_description = fields.Text(
        string='Evidence Description',
        translate=True,
        help='Description of what evidence is required.',
    )

    min_evidence_count = fields.Integer(
        string='Minimum Evidence Items',
        default=1,
        help='Minimum number of evidence items required.',
    )

    allowed_file_types = fields.Char(
        string='Allowed File Types',
        default='pdf,doc,docx,jpg,png',
        help='Comma-separated list of allowed file extensions.',
    )

    max_file_size_mb = fields.Integer(
        string='Max File Size (MB)',
        default=10,
        help='Maximum file size in megabytes.',
    )

    # =========================================================================
    # PERFORMANCE CRITERIA MAPPING
    # =========================================================================
    # Links to elements/performance criteria from the unit
    performance_criteria = fields.Text(
        string='Performance Criteria',
        help='Performance criteria from the unit that this activity addresses. '
             'Example: PC1.1, PC1.2, PC2.3',
    )

    knowledge_evidence = fields.Text(
        string='Knowledge Evidence',
        help='Knowledge evidence from the unit that this activity assesses.',
    )

    performance_evidence = fields.Text(
        string='Performance Evidence',
        help='Performance evidence from the unit that this activity assesses.',
    )

    # =========================================================================
    # ASSESSMENT CONDITIONS
    # =========================================================================
    assessment_conditions = fields.Html(
        string='Assessment Conditions',
        translate=True,
        help='Conditions under which this assessment must be conducted. '
             'Per ASQA Standard 1.8, must replicate workplace conditions.',
    )

    reasonable_adjustments = fields.Text(
        string='Reasonable Adjustments',
        help='Available reasonable adjustments for this assessment.',
    )

    # =========================================================================
    # TIMING & ATTEMPTS
    # =========================================================================
    time_limit_minutes = fields.Integer(
        string='Time Limit (minutes)',
        default=0,
        help='Time limit for timed assessments. 0 = no limit.',
    )

    max_attempts = fields.Integer(
        string='Maximum Attempts',
        default=3,
        help='Maximum number of attempts allowed. 0 = unlimited.',
    )

    attempt_gap_days = fields.Integer(
        string='Days Between Attempts',
        default=0,
        help='Minimum days required between assessment attempts.',
    )

    # =========================================================================
    # WEIGHTING
    # =========================================================================
    weighting = fields.Float(
        string='Weighting (%)',
        default=0.0,
        help='Weighting of this assessment towards overall unit outcome.',
    )

    is_critical = fields.Boolean(
        string='Critical Assessment',
        default=False,
        help='If checked, must be passed to achieve competency regardless of weighting.',
    )

    # =========================================================================
    # QUIZ DEFINITION LINK
    # =========================================================================
    quiz_definition_id = fields.Many2one(
        'lms.quiz.definition',
        string='Quiz Definition',
        help='Link to Moodle-style quiz definition with question bank.',
        domain="[('slide_id', '=', id)]",
    )

    # =========================================================================
    # ASSIGNMENT LINK (One2one relationship - one slide = one assignment)
    # =========================================================================
    assignment_id = fields.Many2one(
        'rto.assignment',
        string='Assignment',
        help='File submission assignment configuration for this slide.',
        ondelete='cascade',
    )

    has_assignment = fields.Boolean(
        string='Has Assignment',
        compute='_compute_has_assignment',
        store=True,
        help='Whether this slide has an assignment configured.',
    )

    # Related fields for inline editing of assignment properties
    assignment_description = fields.Html(related='assignment_id.description', readonly=False, string="Description")
    assignment_instructions = fields.Html(related='assignment_id.instructions', readonly=False, string="Instructions")
    assignment_allow_submission_from = fields.Datetime(related='assignment_id.allow_submission_from', readonly=False, string="Allow Submissions From")
    assignment_due_date = fields.Datetime(related='assignment_id.due_date', readonly=False, string="Due Date")
    assignment_cut_off_date = fields.Datetime(related='assignment_id.cut_off_date', readonly=False, string="Cut-off Date")
    assignment_max_files = fields.Integer(related='assignment_id.max_files', readonly=False, string="Max Files")
    assignment_max_file_size_mb = fields.Integer(related='assignment_id.max_file_size_mb', readonly=False, string="Max File Size (MB)")
    assignment_accepted_file_types = fields.Char(related='assignment_id.accepted_file_types', readonly=False, string="Accepted File Types")
    assignment_require_submit_button = fields.Boolean(related='assignment_id.require_submit_button', readonly=False, string="Require Submit Button")
    assignment_allow_resubmission = fields.Boolean(related='assignment_id.allow_resubmission', readonly=False, string="Allow Resubmission")
    assignment_max_attempts = fields.Integer(related='assignment_id.max_attempts', readonly=False, string="Max Attempts")
    assignment_reopen_method = fields.Selection(related='assignment_id.reopen_method', readonly=False, string="Reopen Method")
    assignment_grading_type = fields.Selection(related='assignment_id.grading_type', readonly=False, string="Grading Type")
    assignment_max_grade = fields.Float(related='assignment_id.max_grade', readonly=False, string="Maximum Grade")
    assignment_pass_grade = fields.Float(related='assignment_id.pass_grade', readonly=False, string="Pass Grade")
    assignment_always_show_description = fields.Boolean(related='assignment_id.always_show_description', readonly=False, string="Always Show Description")
    assignment_is_available = fields.Boolean(related='assignment_id.is_available', string="Is Available")
    assignment_is_past_due = fields.Boolean(related='assignment_id.is_past_due', string="Is Past Due")
    assignment_is_past_cutoff = fields.Boolean(related='assignment_id.is_past_cutoff', string="Is Past Cutoff")

    # =========================================================================
    # LINKS TO OUTCOMES
    # =========================================================================
    outcome_ids = fields.One2many(
        comodel_name='rto.assessment.outcome',
        inverse_name='activity_id',
        string='Assessment Outcomes',
        help='Student outcomes for this activity.',
    )

    outcome_count = fields.Integer(
        string='Outcome Count',
        compute='_compute_outcome_count',
    )

    # =========================================================================
    # LINKS TO EVIDENCE
    # =========================================================================
    evidence_log_ids = fields.One2many(
        comodel_name='rto.evidence.log',
        inverse_name='activity_id',
        string='Evidence Records',
        help='Evidence records generated from this activity.',
    )

    evidence_log_count = fields.Integer(
        string='Evidence Count',
        compute='_compute_evidence_log_count',
    )

    # =========================================================================
    # THIRD PARTY OBSERVATION
    # =========================================================================
    requires_third_party = fields.Boolean(
        string='Requires Third Party',
        default=False,
        help='Whether a third party report/observation is required.',
    )

    third_party_type = fields.Selection(
        selection=[
            ('supervisor', 'Workplace Supervisor'),
            ('employer', 'Employer'),
            ('colleague', 'Work Colleague'),
            ('client', 'Client/Customer'),
            ('other', 'Other'),
        ],
        string='Third Party Type',
        help='Type of third party required for verification.',
    )

    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================

    @api.depends('rto_activity_type')
    def _compute_is_rto_assessable(self):
        """Determine if activity requires formal assessment."""
        assessable_types = ('assessment', 'observation', 'practical')
        for activity in self:
            activity.is_rto_assessable = activity.rto_activity_type in assessable_types

    def _compute_outcome_count(self):
        """Count assessment outcomes."""
        for activity in self:
            activity.outcome_count = len(activity.outcome_ids)

    def _compute_evidence_log_count(self):
        """Count evidence log entries."""
        for activity in self:
            activity.evidence_log_count = len(activity.evidence_log_ids)

    @api.depends('assignment_id')
    def _compute_has_assignment(self):
        """Check if slide has an assignment configured."""
        for slide in self:
            slide.has_assignment = bool(slide.assignment_id)

    # =========================================================================
    # VALIDATION
    # =========================================================================

    @api.constrains('weighting')
    def _check_weighting(self):
        """Validate weighting percentage."""
        for activity in self:
            if activity.weighting < 0 or activity.weighting > 100:
                raise ValidationError(_(
                    'Weighting must be between 0 and 100 percent.'
                ))

    @api.constrains('min_evidence_count')
    def _check_evidence_count(self):
        """Validate minimum evidence count."""
        for activity in self:
            if activity.evidence_required and activity.min_evidence_count < 1:
                raise ValidationError(_(
                    'Minimum evidence count must be at least 1 when evidence is required.'
                ))

    # =========================================================================
    # ONCHANGE HANDLERS
    # =========================================================================

    @api.onchange('rto_activity_type')
    def _onchange_rto_activity_type(self):
        """Set defaults based on activity type."""
        if self.rto_activity_type == 'assessment':
            self.evidence_required = True
            self.is_critical = True
        elif self.rto_activity_type == 'observation':
            self.requires_third_party = True
            self.assessment_method = 'observation'
        elif self.rto_activity_type == 'evidence':
            self.evidence_required = True
            self.assessment_method = 'portfolio'
        elif self.rto_activity_type == 'practical':
            self.assessment_method = 'practical'

    # =========================================================================
    # CRUD HOOKS
    # =========================================================================


    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================

    def action_view_assignment_submissions(self):
        """Open submissions list filtered by this slide's assignment."""
        self.ensure_one()
        if not self.assignment_id:
            raise UserError(_('No assignment is configured for this slide.'))

        action = self.env.ref('rto_lms.action_rto_assignment_submission').read()[0]
        action['name'] = _('Submissions - %s', self.assignment_id.name)
        action['domain'] = [('assignment_id', '=', self.assignment_id.id)]
        action['context'] = {
            'default_assignment_id': self.assignment_id.id,
            'search_default_submitted': 1,
        }
        return action

    def action_sync_quiz_questions(self):
        """Sync questions from quiz definition to slide questions."""
        self.ensure_one()
        if not self.quiz_definition_id:
            raise UserError(_('No quiz definition selected. Please select a quiz definition first.'))
        
        # Clear existing slide questions
        question_count = len(self.question_ids)
        self.question_ids.unlink()
        
        # Create slide questions from quiz definition with constraints deferred
        SlideQuestion = self.env['slide.question'].sudo()
        synced_count = 0
        for bank_question in self.quiz_definition_id.question_ids:
            # Prepare answer values first for MCQ/TF questions
            answer_vals_list = []
            if bank_question.question_type in ('mcq_single', 'mcq_multi', 'tf'):
                _logger.info('RTO SYNC: Processing MCQ question %s with %s answers', 
                            bank_question.id, len(bank_question.answer_ids))
                for answer in bank_question.answer_ids:
                    # Strip HTML tags from answer text
                    answer_text = html2plaintext(answer.answer_html) if answer.answer_html else ''
                    answer_vals_list.append((0, 0, {
                        'text_value': answer_text.strip(),
                        'is_correct': answer.is_correct,
                        'sequence': answer.sequence,
                    }))
                _logger.info('RTO SYNC: Created %s answer values', len(answer_vals_list))
            
            # Strip HTML tags from question text
            question_text = html2plaintext(bank_question.question_html) if bank_question.question_html else bank_question.name
            
            # Create the slide question with answers in one transaction
            question_vals = {
                'slide_id': self.id,
                'question': question_text.strip(),
                'sequence': bank_question.id,  # Use bank question ID as sequence
                'question_type': self._map_question_type(bank_question.question_type),
                'answer_ids': answer_vals_list,
                'question_points': bank_question.max_score,
            }
            
            # Copy text-based question fields (short_answer, numerical)
            if bank_question.question_type in ('short', 'numerical'):
                # Strip HTML from expected answer
                if bank_question.expected_answer_text:
                    expected_text = html2plaintext(bank_question.expected_answer_text)
                    question_vals['expected_answer_text'] = expected_text.strip()
                
                # Copy case sensitivity for short answer
                if bank_question.question_type == 'short':
                    question_vals['case_sensitive'] = bank_question.case_sensitive
                
                # Copy numerical fields
                if bank_question.question_type == 'numerical':
                    question_vals['numerical_tolerance'] = bank_question.numerical_tolerance
                    if bank_question.numerical_unit:
                        question_vals['numerical_unit'] = bank_question.numerical_unit
            
            # Use with_context to bypass constraint checks during creation
            new_question = SlideQuestion.with_context(skip_constraint_check=True).create(question_vals)
            synced_count += 1
            _logger.info('Synced question %s (%s): expected_answer=%s', 
                        new_question.id, bank_question.question_type,
                        new_question.expected_answer_text[:50] if new_question.expected_answer_text else 'NONE')
        
        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Questions Synced Successfully'),
                'message': _('Synced %s questions from Question Bank (replaced %s existing questions)') % (synced_count, question_count),
                'type': 'success',
                'sticky': False,
            }
        }

    def _map_question_type(self, bank_question_type):
        """Map question bank type to slide question type."""
        mapping = {
            'mcq_single': 'multiple_choice_single',
            'mcq_multi': 'multiple_choice_multi',
            'tf': 'true_false',
            'short': 'short_answer',
            'numerical': 'numerical',
            'matching': 'matching',
        }
        return mapping.get(bank_question_type, 'multiple_choice_single')

    @api.model_create_multi
    def create(self, vals_list):
        """Override to handle quiz and assignment slide creation."""
        # Map slide fields to assignment fields
        assignment_field_mapping = {
            'assignment_description': 'description',
            'assignment_instructions': 'instructions',
            'assignment_always_show_description': 'always_show_description',
            'assignment_allow_submission_from': 'allow_submission_from',
            'assignment_due_date': 'due_date',
            'assignment_cut_off_date': 'cut_off_date',
            'assignment_max_files': 'max_files',
            'assignment_max_file_size_mb': 'max_file_size_mb',
            'assignment_accepted_file_types': 'accepted_file_types',
            'assignment_require_submit_button': 'require_submit_button',
            'assignment_allow_resubmission': 'allow_resubmission',
            'assignment_max_attempts': 'max_attempts',
            'assignment_reopen_method': 'reopen_method',
            'assignment_grading_type': 'grading_type',
            'assignment_max_grade': 'max_grade',
            'assignment_pass_grade': 'pass_grade',
        }

        # Extract assignment-related fields from vals to avoid related-field writes during create
        assignment_vals_list = []
        for vals in vals_list:
            assignment_vals = {}
            for slide_field, assignment_field in assignment_field_mapping.items():
                if slide_field in vals:
                    assignment_vals[assignment_field] = vals.pop(slide_field)
            assignment_vals_list.append(assignment_vals)

        slides = super().create(vals_list)

        for slide, assignment_vals in zip(slides, assignment_vals_list):
            # Ensure assignment exists with slide_id and apply extracted fields
            if slide.slide_category == 'assignment':
                if slide.assignment_id:
                    if not slide.assignment_id.slide_id:
                        slide.assignment_id.write({'slide_id': slide.id})
                    if assignment_vals:
                        slide.assignment_id.write(assignment_vals)
                else:
                    assignment_vals.setdefault('name', slide.name or _('New Assignment'))
                    assignment_vals['slide_id'] = slide.id
                    assignment = self.env['rto.assignment'].with_context(allow_assignment_without_slide=True).create(assignment_vals)
                    slide.assignment_id = assignment.id

            # Handle quiz slides with quiz definition
            if slide.slide_category == 'quiz' and slide.quiz_definition_id:
                slide.action_sync_quiz_questions()

        return slides

    def write(self, vals):
        """Override to sync questions when quiz definition changes and handle assignment fields."""
        import logging
        _logger = logging.getLogger(__name__)

        _logger.info("="*80)
        _logger.info("SLIDE WRITE - vals keys: %s", list(vals.keys()))

        # Map of assignment-related field names
        assignment_field_mapping = {
            'assignment_description': 'description',
            'assignment_instructions': 'instructions',
            'assignment_always_show_description': 'always_show_description',
            'assignment_allow_submission_from': 'allow_submission_from',
            'assignment_due_date': 'due_date',
            'assignment_cut_off_date': 'cut_off_date',
            'assignment_max_files': 'max_files',
            'assignment_max_file_size_mb': 'max_file_size_mb',
            'assignment_accepted_file_types': 'accepted_file_types',
            'assignment_require_submit_button': 'require_submit_button',
            'assignment_allow_resubmission': 'allow_resubmission',
            'assignment_max_attempts': 'max_attempts',
            'assignment_reopen_method': 'reopen_method',
            'assignment_grading_type': 'grading_type',
            'assignment_max_grade': 'max_grade',
            'assignment_pass_grade': 'pass_grade',
        }

        # Check if any assignment-related fields are being written
        has_assignment_fields = any(field in vals for field in assignment_field_mapping)

        # Handle assignment creation BEFORE super().write() to prevent ORM auto-creation
        if has_assignment_fields:
            for slide in self:
                _logger.info("Processing slide %s, category=%s, has_assignment=%s", slide.id, slide.slide_category, bool(slide.assignment_id))
                # Create assignment if slide category is assignment and no assignment exists
                if slide.slide_category == 'assignment' and not slide.assignment_id:
                    assignment_vals = {
                        'name': vals.get('name', slide.name or _('New Assignment')),
                        'slide_id': slide.id,
                    }
                    
                    # Add assignment field values
                    for slide_field, assignment_field in assignment_field_mapping.items():
                        if slide_field in vals:
                            assignment_vals[assignment_field] = vals[slide_field]
                    
                    _logger.info("Creating assignment for slide %s with vals: %s", slide.id, assignment_vals)
                    assignment = self.env['rto.assignment'].create(assignment_vals)
                    vals['assignment_id'] = assignment.id
                    _logger.info("Assignment %s created and linked to slide", assignment.id)

        result = super().write(vals)

        # Sync quiz questions if quiz definition changed
        if 'quiz_definition_id' in vals:
            for slide in self:
                if slide.slide_category == 'quiz' and slide.quiz_definition_id:
                    slide.action_sync_quiz_questions()

        return result

    def action_view_outcomes(self):
        """Open assessment outcomes for this activity."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assessment Outcomes - %s', self.name),
            'res_model': 'rto.assessment.outcome',
            'view_mode': 'tree,form',
            'domain': [('activity_id', '=', self.id)],
            'context': {
                'default_activity_id': self.id,
                'default_course_id': self.channel_id.id,
            },
        }

    def action_view_evidence(self):
        """Open evidence log for this activity."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Evidence Log - %s', self.name),
            'res_model': 'rto.evidence.log',
            'view_mode': 'tree,form',
            'domain': [('activity_id', '=', self.id)],
            'context': {
                'default_activity_id': self.id,
                'default_course_id': self.channel_id.id,
            },
        }
    
    def _log_evidence(self, student_id, evidence_type, data, attachments=None):
        """
        Create an immutable evidence log entry for this activity.

        Args:
            student_id: res.partner ID of the student
            evidence_type: Type of evidence being logged
            data: Dictionary of evidence data
            attachments: List of attachment records (optional)

        Returns:
            rto.evidence.log record
        """
        self.ensure_one()
        return self.env['rto.evidence.log'].create({
            'activity_id': self.id,
            'course_id': self.channel_id.id,
            'student_id': student_id,
            'evidence_type': evidence_type,
            'evidence_data': data,
            'attachment_ids': [(6, 0, attachments.ids)] if attachments else [],
        })

    def _record_outcome(self, student_id, outcome_code, assessor_id, comments=None):
        """
        Record an assessment outcome for a student.

        Args:
            student_id: res.partner ID of the student
            outcome_code: AVETMISS outcome code (20, 30, 40, etc.)
            assessor_id: hr.employee ID of the assessor
            comments: Optional assessor comments

        Returns:
            rto.assessment.outcome record
        """
        self.ensure_one()
        return self.env['rto.assessment.outcome'].create({
            'activity_id': self.id,
            'course_id': self.channel_id.id,
            'student_id': student_id,
            'outcome_code': outcome_code,
            'assessor_id': assessor_id,
            'assessor_comments': comments,
        })
