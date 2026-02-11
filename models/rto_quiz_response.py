# -*- coding: utf-8 -*-
"""
Quiz Response Tracking for RTO LMS

Stores individual question responses within quiz attempts.
Supports multiple question types and provides detailed analytics.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re


class RtoQuizResponse(models.Model):
    """Individual question response within a quiz attempt"""
    
    _name = 'rto.quiz.response'
    _description = 'Quiz Question Response'
    _order = 'attempt_id, question_id'
    
    # Relationships
    attempt_id = fields.Many2one(
        'rto.quiz.attempt',
        string='Quiz Attempt',
        required=True,
        ondelete='cascade',
        index=True)
    
    question_id = fields.Many2one(
        'slide.question',
        string='Question',
        required=True,
        ondelete='cascade',
        index=True)
    
    # Question Info (for display)
    question_text = fields.Char(
        string='Question',
        related='question_id.question',
        readonly=True)
    
    question_type = fields.Selection(
        string='Question Type',
        related='question_id.question_type',
        readonly=True)
    
    question_points = fields.Float(
        string='Max Points',
        related='question_id.question_points',
        readonly=True)
    
    # Multiple Choice Answers
    answer_ids = fields.Many2many(
        'slide.answer',
        string='Selected Answers',
        help='Selected answer(s) for multiple choice questions')
    
    # Text-based Answers
    response_text = fields.Text(
        string='Text Response',
        help='Response for short answer or essay questions')
    
    # Numerical Answers
    response_number = fields.Float(
        string='Numerical Response',
        help='Response for numerical questions')
    
    # Matching Answers (stored as JSON)
    response_matching = fields.Text(
        string='Matching Pairs',
        help='JSON of matched pairs for matching questions')
    
    # Scoring
    points_earned = fields.Float(
        string='Points Earned',
        default=0.0,
        help='Points awarded for this response')
    
    is_correct = fields.Boolean(
        string='Correct',
        compute='_compute_is_correct',
        store=True,
        help='Whether the response is correct')
    
    # Grading
    graded_by_id = fields.Many2one(
        'res.users',
        string='Graded By',
        help='User who manually graded this response')
    
    graded_at = fields.Datetime(
        string='Graded At',
        help='When manual grading was done')
    
    grader_feedback = fields.Text(
        string='Feedback',
        help='Feedback for this specific answer')
    
    # Timing
    response_timestamp = fields.Datetime(
        string='Answered At',
        default=fields.Datetime.now,
        help='When student answered this question')
    
    time_spent_seconds = fields.Integer(
        string='Time Spent (seconds)',
        default=0,
        help='Time spent on this question')
    
    # State
    is_flagged = fields.Boolean(
        string='Flagged for Review',
        default=False,
        help='Student flagged this question for later review')
    
    @api.depends('answer_ids', 'response_text', 'response_number', 'points_earned')
    def _compute_is_correct(self):
        """Determine if response is correct"""
        for response in self:
            if response.question_type in ['multiple_choice_single', 'multiple_choice_multi', 'true_false']:
                # For MC questions, check if selected answers match correct answers
                correct_answers = response.question_id.answer_ids.filtered('is_correct')
                response.is_correct = (
                    set(response.answer_ids.ids) == set(correct_answers.ids) and
                    response.points_earned > 0
                )
            elif response.question_type in ['short_answer', 'essay', 'matching']:
                # For manual grading, correct if points earned > 0
                response.is_correct = response.points_earned > 0
            elif response.question_type == 'numerical':
                # For numerical, check if within tolerance
                if response.question_id.numerical_tolerance > 0:
                    expected = float(response.question_id.expected_answer_text or 0)
                    tolerance = response.question_id.numerical_tolerance
                    response.is_correct = abs(response.response_number - expected) <= tolerance
                else:
                    response.is_correct = response.points_earned > 0
            else:
                response.is_correct = False
    
    def _calculate_score(self):
        """Calculate points earned for this response"""
        self.ensure_one()
        
        question = self.question_id
        
        # Multiple Choice Single/Multi Answer
        if question.question_type in ['multiple_choice_single', 'multiple_choice_multi', 'true_false']:
            return self._score_multiple_choice()
        
        # Numerical
        elif question.question_type == 'numerical':
            return self._score_numerical()
        
        # Short Answer (simple text matching)
        elif question.question_type == 'short_answer':
            return self._score_short_answer()
        
        # Essay and Matching require manual grading
        elif question.question_type in ['essay', 'matching']:
            return 0.0  # Must be manually graded
        
        return 0.0
    
    def _score_multiple_choice(self):
        """Score multiple choice questions"""
        question = self.question_id
        correct_answers = question.answer_ids.filtered('is_correct')
        selected_answers = self.answer_ids
        
        # No selection = no points
        if not selected_answers:
            return 0.0
        
        # Single answer question
        if question.question_type in ['multiple_choice_single', 'true_false']:
            # Check if the single selected answer is correct
            if len(selected_answers) == 1 and selected_answers[0].is_correct:
                points = question.question_points
            else:
                points = 0.0
                
            # Apply negative marking if enabled
            if not selected_answers[0].is_correct and question.negative_marking:
                penalty = question.question_points * (question.negative_marking_penalty / 100.0)
                points = -penalty
        
        # Multiple answer question
        else:
            # Partial credit calculation
            if question.allow_partial_credit:
                total_credit = 0.0
                for answer in selected_answers:
                    if answer.is_correct:
                        total_credit += answer.partial_credit_percentage
                    elif question.negative_marking:
                        penalty = question.negative_marking_penalty
                        total_credit -= penalty
                
                # Cap between 0 and 100%
                total_credit = max(0, min(100, total_credit))
                points = question.question_points * (total_credit / 100.0)
            
            # All-or-nothing scoring
            else:
                if set(selected_answers.ids) == set(correct_answers.ids):
                    points = question.question_points
                else:
                    points = 0.0
                    
                    # Apply negative marking
                    if question.negative_marking:
                        penalty = question.question_points * (question.negative_marking_penalty / 100.0)
                        points = -penalty
        
        self.points_earned = points
        return points
    
    def _score_numerical(self):
        """Score numerical questions"""
        question = self.question_id
        
        if not question.expected_answer_text:
            return 0.0
        
        try:
            expected = float(question.expected_answer_text)
            tolerance = question.numerical_tolerance
            
            if abs(self.response_number - expected) <= tolerance:
                points = question.question_points
            else:
                points = 0.0
                
                # Apply negative marking
                if question.negative_marking:
                    penalty = question.question_points * (question.negative_marking_penalty / 100.0)
                    points = -penalty
            
            self.points_earned = points
            return points
        
        except (ValueError, TypeError):
            self.points_earned = 0.0
            return 0.0
    
    def _score_short_answer(self):
        """Score short answer questions with simple text matching"""
        question = self.question_id
        
        if not question.expected_answer_text or not self.response_text:
            return 0.0
        
        expected = question.expected_answer_text.strip()
        response = self.response_text.strip()
        
        # Case sensitivity check
        if not question.case_sensitive:
            expected = expected.lower()
            response = response.lower()
        
        # Simple exact match (can be enhanced with fuzzy matching)
        if expected == response:
            self.points_earned = question.question_points
            return question.question_points
        
        # Check if response contains expected answer
        elif expected in response:
            # Award partial credit (50%)
            points = question.question_points * 0.5
            self.points_earned = points
            return points
        
        self.points_earned = 0.0
        return 0.0
    
    def action_manual_grade(self, points, feedback=''):
        """Manually grade a response"""
        self.ensure_one()
        
        if points < 0 or points > self.question_id.question_points:
            raise ValidationError(_(
                'Points must be between 0 and %s'
            ) % self.question_id.question_points)
        
        self.write({
            'points_earned': points,
            'grader_feedback': feedback,
            'graded_by_id': self.env.user.id,
            'graded_at': fields.Datetime.now(),
        })
        
        # Recalculate attempt scores
        self.attempt_id.action_auto_grade()
    
    @api.constrains('answer_ids', 'question_id')
    def _check_answer_compatibility(self):
        """Ensure selected answers belong to the question"""
        for response in self:
            if response.answer_ids:
                invalid_answers = response.answer_ids.filtered(
                    lambda a: a.question_id != response.question_id)
                if invalid_answers:
                    raise ValidationError(_(
                        'Selected answers must belong to the question.'
                    ))
