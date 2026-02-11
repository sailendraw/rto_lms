# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Reusable quiz question bank for Moodle-style quizzes."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LMSQuizQuestion(models.Model):
    """Reusable quiz question record scoped to an RTO course."""

    _name = 'lms.quiz.question'
    _description = 'Quiz Question'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Question Title',
        required=True,
        tracking=True,
        help='Internal title used to identify this question in the bank.',
    )
    course_id = fields.Many2one(
        'slide.channel',
        string='Course',
        required=False,
        index=True,
        tracking=True,
        help='Unit delivery course that owns this question bank item.',
    )
    question_type = fields.Selection(
        selection=[
            ('mcq_single', 'Multiple Choice (Single)'),
            ('mcq_multi', 'Multiple Choice (Multi)'),
            ('tf', 'True / False'),
            ('short', 'Short Answer'),
            ('numerical', 'Numerical'),
            ('matching', 'Matching'),
        ],
        string='Question Type',
        required=True,
        default='mcq_single',
        tracking=True,
    )
    question_html = fields.Html(
        string='Question Text',
        sanitize=True,
        required=True,
    )
    max_score = fields.Float(
        string='Maximum Score',
        default=1.0,
        required=True,
        help='Score awarded for fully correct response.',
    )
    active = fields.Boolean(
        default=True,
        help='Inactive questions are hidden from authoring but kept for audit.',
    )

    answer_ids = fields.One2many(
        'lms.quiz.question.answer',
        'question_id',
        string='Answer Options',
    )
    definition_ids = fields.Many2many(
        comodel_name='lms.quiz.definition',
        relation='lms_quiz_definition_question_rel',
        column1='question_id',
        column2='definition_id',
        string='Quiz Definitions',
        help='Quiz variants that can use this question.',
    )

    # Text-based question fields (essay, short answer)
    expected_answer_text = fields.Html(
        string='Expected Answer',
        sanitize=True,
        help='Model answer for grading reference (essay/short answer).',
    )
    case_sensitive = fields.Boolean(
        string='Case Sensitive',
        default=False,
        help='For short answer auto-grading: whether case must match exactly.',
    )

    # Numerical question fields
    expected_answer_numerical = fields.Float(
        string='Expected Numerical Answer',
        help='The correct numerical value for this question.',
    )
    numerical_tolerance = fields.Float(
        string='Tolerance (±)',
        default=0.0,
        help='Acceptable margin of error for numerical answers.',
    )
    numerical_unit = fields.Char(
        string='Unit',
        help='Expected unit of measurement (e.g., kg, m/s, °C).',
    )

    # MCQ Multi partial credit
    allow_partial_credit = fields.Boolean(
        string='Allow Partial Credit',
        default=False,
        help='For multi-select questions: award proportional points for partially correct answers.',
    )

    # Matching question pairs
    matching_pair_ids = fields.One2many(
        'lms.quiz.question.matching.pair',
        'question_id',
        string='Matching Pairs',
        help='Prompt-response pairs for matching questions.',
    )

    depends_on_question_id = fields.Many2one(
        'lms.quiz.question',
        string='Depends On Question',
        domain="[('course_id', '=', course_id)]",
        help='Select another question that must be answered before this one.',
    )
    depends_on_answer_ids = fields.Many2many(
        'lms.quiz.question.answer',
        'lms_quiz_question_dependency_answer_rel',
        'question_id',
        'answer_id',
        string='Unlock Answers',
        help='Specific answer values from the dependency question that unlock this question.',
    )
    dependency_type = fields.Selection(
        selection=[
            ('sequence', 'Sequential'),
            ('answer_value', 'Answer Based'),
        ],
        string='Dependency Type',
        default='sequence',
    )

    is_manual_grading = fields.Boolean(
        string='Requires Manual Grading',
        compute='_compute_is_manual_grading',
        store=True,
    )

    @api.depends('question_type')
    def _compute_is_manual_grading(self):
        for question in self:
            question.is_manual_grading = question.question_type in ('short', 'essay')

    @api.constrains('max_score')
    def _check_positive_score(self):
        for question in self:
            if question.max_score <= 0:
                raise ValidationError(_('Maximum score must be greater than zero.'))

    @api.constrains('depends_on_question_id')
    def _check_dependency_course(self):
        for question in self:
            if question.depends_on_question_id and question.depends_on_question_id.course_id != question.course_id:
                raise ValidationError(_('Dependency question must belong to the same course.'))

    @api.constrains('depends_on_question_id')
    def _check_dependency_cycles(self):
        for question in self:
            seen = set()
            dependency = question.depends_on_question_id
            while dependency:
                if dependency == question:
                    raise ValidationError(_('Questions cannot depend on themselves (directly or indirectly).'))
                if dependency.id in seen:
                    raise ValidationError(_('Circular question dependencies are not allowed.'))
                seen.add(dependency.id)
                dependency = dependency.depends_on_question_id

    @api.constrains('question_type', 'answer_ids')
    def _check_answer_requirements(self):
        """Validate answer requirements, but allow empty state during creation."""
        for question in self:
            # Allow empty answers during creation - users add them after creating the question
            # Only validate if answers exist
            if question.answer_ids:
                if question.question_type in ('mcq_single', 'mcq_multi', 'tf'):
                    correct_answers = question.answer_ids.filtered('is_correct')
                    if not correct_answers:
                        raise ValidationError(_('Multiple choice and true/false questions must have at least one correct answer.'))

                    if question.question_type == 'mcq_single' and len(correct_answers) > 1:
                        raise ValidationError(_('Single-choice questions can only have one correct answer. Found %d correct answers.') % len(correct_answers))

                    if question.question_type == 'tf' and len(question.answer_ids) != 2:
                        raise ValidationError(_('True/False questions must have exactly two answer options.'))

                # Prevent adding answers to text-based questions
                if question.question_type in ('short', 'essay', 'numerical', 'matching'):
                    raise ValidationError(_('Text, numerical, and matching questions cannot have predefined answer options.'))

    @api.model_create_multi
    def create(self, vals_list):
        """Trigger sync on related quiz slides when questions are created."""
        questions = super().create(vals_list)
        questions._sync_related_slides()
        return questions

    def write(self, vals):
        """Trigger sync on related quiz slides when questions are updated."""
        result = super().write(vals)
        # Sync if question content changes or definitions change
        sync_fields = [
            'question_html', 'name', 'question_type', 'definition_ids',
            'expected_answer_text', 'case_sensitive',  # Text answer fields
            'expected_answer_numerical', 'numerical_tolerance', 'numerical_unit',  # Numerical fields
            'answer_ids',  # MCQ answers
        ]
        if any(key in vals for key in sync_fields):
            self._sync_related_slides()
        return result

    def unlink(self):
        """Trigger sync on related quiz slides after deletion."""
        # Store related slides before deletion
        slides = self.env['slide.slide'].search([
            ('quiz_definition_id', 'in', self.definition_ids.ids),
            ('slide_category', '=', 'quiz')
        ])
        
        # Delete the question
        result = super().unlink()
        
        # Sync slides after deletion (question is now gone from Question Bank)
        for slide in slides:
            slide.action_sync_quiz_questions()
        
        return result

    def _sync_related_slides(self):
        """Sync all quiz slides that use these questions via quiz definitions."""
        slides = self.env['slide.slide'].search([
            ('quiz_definition_id', 'in', self.definition_ids.ids),
            ('slide_category', '=', 'quiz')
        ])
        for slide in slides:
            slide.action_sync_quiz_questions()

    @api.constrains('depends_on_answer_ids', 'depends_on_question_id')
    def _check_dependency_answers(self):
        for question in self:
            if question.depends_on_answer_ids and not question.depends_on_question_id:
                raise ValidationError(_('Select a dependency question before choosing specific dependency answers.'))
            if question.depends_on_answer_ids and question.depends_on_question_id:
                invalid = question.depends_on_answer_ids.filtered(
                    lambda ans: ans.question_id != question.depends_on_question_id
                )
                if invalid:
                    raise ValidationError(_('Dependency answers must belong to the dependency question.'))

    @api.constrains('question_type', 'numerical_tolerance')
    def _check_numerical_fields(self):
        """Validate numerical question settings."""
        for question in self:
            if question.question_type == 'numerical':
                # Note: expected_answer_numerical can be 0.0, which is valid
                # Validation of required fields happens when adding question to quiz
                if question.numerical_tolerance < 0:
                    raise ValidationError(_('Tolerance cannot be negative.'))

    @api.constrains('question_type', 'matching_pair_ids')
    def _check_matching_pairs(self):
        """Validate matching pairs, but allow empty state during creation."""
        for question in self:
            if question.question_type == 'matching' and question.matching_pair_ids:
                # Only validate if pairs exist (users add them after creating question)
                if len(question.matching_pair_ids) < 2:
                    raise ValidationError(_('Matching questions require at least 2 pairs.'))
                for pair in question.matching_pair_ids:
                    if not pair.correct_match_id:
                        raise ValidationError(_(
                            'All matching pairs must have a correct match selected. '
                            'Pair "%(prompt)s" is missing a correct match.',
                            prompt=pair.prompt
                        ))

    def get_dependency_config(self):
        """Return dependency metadata for runtime evaluation."""
        self.ensure_one()
        return {
            'question_id': self.id,
            'dependency_type': self.dependency_type,
            'depends_on_question_id': self.depends_on_question_id.id,
            'depends_on_answer_ids': self.depends_on_answer_ids.ids,
        }

    def action_open_question_form(self):
        """Open main question form after type selection in dialog."""
        self.ensure_one()

        question_type_labels = dict(self._fields['question_type'].selection)
        question_type_label = question_type_labels.get(self.question_type, self.question_type)

        return {
            'name': _('Create %s Question') % question_type_label,
            'type': 'ir.actions.act_window',
            'res_model': 'lms.quiz.question',
            'view_mode': 'form',
            'view_id': self.env.ref('rto_lms.view_lms_quiz_question_form').id,
            'target': 'new',
            'context': {
                'default_question_type': self.question_type,
                'default_course_id': self._context.get('default_course_id'),
                'default_name': 'New Question',
                'dialog_size': 'extra-large',
            },
            'flags': {
                'mode': 'edit',
            },
        }
