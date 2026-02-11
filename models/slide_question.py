# -*- coding: utf-8 -*-
"""
Enhanced Quiz Question Models for RTO LMS

Extends base Odoo slide.question and slide.answer models to support:
- Multiple question types (MCQ single/multi, True/False, Short Answer, Essay, Matching, Numerical)
- Question weighting and points
- Partial credit support
- Answer randomization
- Negative marking
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SlideQuestion(models.Model):
    """Extended quiz question with RTO-specific enhancements"""
    
    _inherit = 'slide.question'
    
    # Override base constraint - we have more flexible validation
    @api.constrains('answer_ids')
    def _check_answers_integrity(self):
        """Override base module's strict validation with RTO quiz logic"""
        # Skip the base module's requirement for both correct and incorrect answers
        # Our _check_answer_requirements provides better validation per question type
        return True
    
    # Question Type
    question_type = fields.Selection([
        ('multiple_choice_single', 'Multiple Choice (Single Answer)'),
        ('multiple_choice_multi', 'Multiple Choice (Multiple Answers)'),
        ('true_false', 'True/False'),
        ('short_answer', 'Short Answer (Text)'),
        ('essay', 'Essay (Long Text)'),
        ('matching', 'Matching'),
        ('numerical', 'Numerical'),
    ], string='Question Type', default='multiple_choice_single', required=True,
        help='Type of question determines how answers are collected and graded')
    
    # Scoring
    question_points = fields.Float(
        string='Points', 
        default=1.0, 
        required=True,
        help='Points awarded for correct answer')
    
    allow_partial_credit = fields.Boolean(
        string='Allow Partial Credit',
        default=False,
        help='For multiple answer questions, award points proportionally')
    
    negative_marking = fields.Boolean(
        string='Negative Marking',
        default=False,
        help='Deduct points for incorrect answers')
    
    negative_marking_penalty = fields.Float(
        string='Penalty (%)',
        default=25.0,
        help='Percentage of question points to deduct for wrong answer')
    
    # Display Options
    randomize_answers = fields.Boolean(
        string='Randomize Answer Order',
        default=False,
        help='Shuffle answer options for each student')
    
    # Text-based Questions
    case_sensitive = fields.Boolean(
        string='Case Sensitive',
        default=False,
        help='For short answer questions - require exact case match')
    
    expected_answer_text = fields.Text(
        string='Expected Answer',
        help='For short answer/essay questions - model answer for manual grading')
    
    # Numerical Questions
    numerical_tolerance = fields.Float(
        string='Tolerance',
        default=0.0,
        help='Acceptable range for numerical answers (±)')
    
    numerical_unit = fields.Char(
        string='Unit',
        help='Expected unit for numerical answer (e.g., "kg", "m/s")')
    
    # Grading
    requires_manual_grading = fields.Boolean(
        string='Requires Manual Grading',
        compute='_compute_requires_manual_grading',
        store=True,
        help='Question type requires trainer to manually grade')
    
    # Statistics
    total_attempts = fields.Integer(
        string='Total Attempts',
        compute='_compute_statistics',
        help='Number of times this question has been attempted')
    
    correct_attempts = fields.Integer(
        string='Correct Attempts',
        compute='_compute_statistics',
        help='Number of times answered correctly')
    
    difficulty_rate = fields.Float(
        string='Difficulty (%)',
        compute='_compute_statistics',
        help='Percentage of students who answered incorrectly')
    
    @api.depends('question_type')
    def _compute_requires_manual_grading(self):
        """Determine if question needs manual grading"""
        manual_types = ['essay', 'short_answer']
        for question in self:
            question.requires_manual_grading = question.question_type in manual_types
    
    def _compute_statistics(self):
        """Calculate question statistics from quiz attempts"""
        # TODO: Implement statistics when quiz attempt tracking is ready
        for question in self:
            question.total_attempts = 0
            question.correct_attempts = 0
            question.difficulty_rate = 0.0
    
    @api.constrains('question_type', 'answer_ids', 'expected_answer_text')
    def _check_answer_requirements(self):
        """Validate answers based on question type"""
        # Skip validation if context flag is set (during sync operations)
        if self.env.context.get('skip_constraint_check'):
            return
            
        for question in self:
            if question.question_type in ['multiple_choice_single', 'multiple_choice_multi']:
                if not question.answer_ids:
                    raise ValidationError(_(
                        'Question "%s" (Multiple Choice) must have at least one answer option defined.'
                    ) % question.question)
                
                correct_answers = question.answer_ids.filtered('is_correct')
                if not correct_answers:
                    raise ValidationError(_(
                        'Question "%s" (Multiple Choice) must have at least one correct answer marked.'
                    ) % question.question)
                
                if question.question_type == 'multiple_choice_single' and len(correct_answers) > 1:
                    raise ValidationError(_(
                        'Question "%s" (Single Answer) can only have ONE correct answer marked.'
                    ) % question.question)
                
            elif question.question_type == 'true_false':
                if len(question.answer_ids) != 2:
                    raise ValidationError(_(
                        'Question "%s" (True/False) must have exactly 2 answer options (True and False).'
                    ) % question.question)
                
                if len(question.answer_ids.filtered('is_correct')) != 1:
                    raise ValidationError(_(
                        'Question "%s" (True/False) must have exactly ONE correct answer marked.'
                    ) % question.question)
            
            elif question.question_type in ['short_answer', 'numerical']:
                # Require expected answer for auto-grading
                if not question.expected_answer_text or not question.expected_answer_text.strip():
                    raise ValidationError(_(
                        'Question "%s" (%s) must have an Expected Answer defined for automatic validation. '
                        'Students\' answers will be checked against this value.'
                    ) % (question.question, question.question_type.replace('_', ' ').title()))
            
            elif question.question_type == 'matching':
                if not question.answer_ids:
                    raise ValidationError(_(
                        'Question "%s" (Matching) must have matching pairs defined.'
                    ) % question.question)
                
                if len(question.answer_ids) < 2:
                    raise ValidationError(_(
                        'Question "%s" (Matching) must have at least 2 matching pairs defined.'
                    ) % question.question)
    
    @api.constrains('question_points')
    def _check_positive_points(self):
        """Ensure points are positive"""
        for question in self:
            if question.question_points <= 0:
                raise ValidationError(_('Question points must be greater than zero.'))
    
    @api.constrains('negative_marking_penalty')
    def _check_penalty_range(self):
        """Ensure penalty is valid percentage"""
        for question in self:
            if question.negative_marking and not (0 <= question.negative_marking_penalty <= 100):
                raise ValidationError(_('Negative marking penalty must be between 0 and 100%.'))


class SlideAnswer(models.Model):
    """Extended quiz answer with RTO-specific enhancements"""
    
    _inherit = 'slide.answer'
    
    # Partial Credit
    partial_credit_percentage = fields.Float(
        string='Partial Credit (%)',
        default=0.0,
        help='Percentage of question points to award if this answer is selected')
    
    # Matching Questions
    match_text = fields.Char(
        string='Match With',
        help='For matching questions - the text to pair with')
    
    match_order = fields.Integer(
        string='Match Order',
        default=10,
        help='Display order for matching pairs')
    
    @api.constrains('partial_credit_percentage')
    def _check_partial_credit_range(self):
        """Validate partial credit percentage"""
        for answer in self:
            if not (0 <= answer.partial_credit_percentage <= 100):
                raise ValidationError(_(
                    'Partial credit must be between 0 and 100%.'
                ))
    
    @api.constrains('is_correct', 'partial_credit_percentage')
    def _check_correct_answer_credit(self):
        """Ensure correct answers have appropriate credit"""
        for answer in self:
            if answer.is_correct and answer.question_id.allow_partial_credit:
                if answer.partial_credit_percentage < 100:
                    raise ValidationError(_(
                        'Correct answers must have 100% partial credit when partial credit is enabled.'
                    ))
