# -*- coding: utf-8 -*-
"""
Quiz Attempt Tracking for RTO LMS

Tracks individual student quiz attempts with full audit trail.
Integrates with evidence logging and assessment outcomes for ASQA compliance.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json


class RtoQuizAttempt(models.Model):
    """Track individual quiz attempts by students"""
    
    _name = 'rto.quiz.attempt'
    _description = 'Quiz Attempt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'started_at desc'
    _rec_name = 'reference'
    
    # Reference
    reference = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'))
    
    # Relationships
    activity_id = fields.Many2one(
        'slide.slide',
        string='Quiz Activity',
        required=True,
        ondelete='cascade',
        index=True,
        domain=[('slide_category', '=', 'quiz')])
    
    course_id = fields.Many2one(
        'slide.channel',
        string='Course',
        related='activity_id.channel_id',
        store=True,
        index=True)
    
    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True)
    
    # Attempt Info
    attempt_number = fields.Integer(
        string='Attempt Number',
        required=True,
        default=1,
        help='Sequential attempt number for this student')
    
    state = fields.Selection([
        ('draft', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('auto_graded', 'Auto-Graded'),
        ('manually_graded', 'Manually Graded'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', required=True, index=True)
    
    # Timing
    started_at = fields.Datetime(
        string='Started At',
        help='When student started the quiz')
    
    submitted_at = fields.Datetime(
        string='Submitted At',
        help='When student submitted the quiz')
    
    time_taken_seconds = fields.Integer(
        string='Time Taken (seconds)',
        compute='_compute_time_taken',
        store=True,
        help='Total time spent on quiz')
    
    time_taken_display = fields.Char(
        string='Time Taken',
        compute='_compute_time_taken_display',
        help='Human-readable time taken')
    
    # Scoring
    auto_score = fields.Float(
        string='Auto Score',
        default=0.0,
        help='Score from automatically graded questions')
    
    manual_score = fields.Float(
        string='Manual Score',
        default=0.0,
        help='Score from manually graded questions')
    
    final_score = fields.Float(
        string='Final Score',
        compute='_compute_final_score',
        store=True,
        help='Total score (auto + manual)')
    
    max_score = fields.Float(
        string='Maximum Score',
        related='activity_id.quiz_total_points',
        help='Maximum possible score')
    
    score_percentage = fields.Float(
        string='Score %',
        compute='_compute_score_percentage',
        store=True,
        help='Score as percentage')
    
    passed = fields.Boolean(
        string='Passed',
        compute='_compute_passed',
        store=True,
        help='Whether student passed based on pass threshold')
    
    # Grading
    grading_status = fields.Selection([
        ('pending', 'Pending Grading'),
        ('auto_graded', 'Auto-Graded'),
        ('partially_graded', 'Partially Graded'),
        ('fully_graded', 'Fully Graded'),
    ], string='Grading Status', default='pending', compute='_compute_grading_status', store=True)
    
    graded_by_id = fields.Many2one(
        'res.users',
        string='Graded By',
        help='Trainer who performed manual grading')
    
    graded_at = fields.Datetime(
        string='Graded At',
        help='When manual grading was completed')
    
    grader_feedback = fields.Html(
        string='Overall Feedback',
        help='General feedback from trainer')
    
    # Responses
    response_ids = fields.One2many(
        'rto.quiz.response',
        'attempt_id',
        string='Responses')
    
    response_count = fields.Integer(
        string='Responses',
        compute='_compute_response_count')
    
    # Response Data (JSON backup)
    response_data = fields.Text(
        string='Response Data (JSON)',
        help='JSON backup of all responses for audit trail')
    
    # Questions
    question_count = fields.Integer(
        string='Total Questions',
        related='activity_id.question_ids.id',
        help='Number of questions in quiz')
    
    questions_answered = fields.Integer(
        string='Questions Answered',
        compute='_compute_questions_answered',
        store=True)
    
    questions_correct = fields.Integer(
        string='Correct Answers',
        compute='_compute_questions_correct',
        store=True)
    
    requires_manual_grading = fields.Boolean(
        string='Requires Manual Grading',
        compute='_compute_requires_manual_grading',
        store=True,
        help='Has questions requiring manual grading')
    
    # Integration
    evidence_log_id = fields.Many2one(
        'rto.evidence.log',
        string='Evidence Log',
        readonly=True,
        help='Immutable evidence record for this attempt')
    
    outcome_id = fields.Many2one(
        'rto.assessment.outcome',
        string='Assessment Outcome',
        readonly=True,
        help='Assessment outcome record if quiz is graded')
    
    # Audit
    ip_address = fields.Char(
        string='IP Address',
        help='Student IP address during attempt')
    
    user_agent = fields.Char(
        string='User Agent',
        help='Browser information')
    
    @api.model
    def create(self, vals):
        """Generate reference number on create"""
        if vals.get('reference', _('New')) == _('New'):
            vals['reference'] = self.env['ir.sequence'].sudo().next_by_code(
                'rto.quiz.attempt') or _('New')
        
        # Capture IP and user agent
        request = self.env.context.get('request')
        if request:
            vals['ip_address'] = request.httprequest.remote_addr
            vals['user_agent'] = request.httprequest.user_agent.string
        
        return super().create(vals)
    
    @api.depends('started_at', 'submitted_at')
    def _compute_time_taken(self):
        """Calculate time taken in seconds"""
        for attempt in self:
            if attempt.started_at and attempt.submitted_at:
                delta = attempt.submitted_at - attempt.started_at
                attempt.time_taken_seconds = int(delta.total_seconds())
            else:
                attempt.time_taken_seconds = 0
    
    @api.depends('time_taken_seconds')
    def _compute_time_taken_display(self):
        """Convert seconds to readable format"""
        for attempt in self:
            seconds = attempt.time_taken_seconds
            if seconds == 0:
                attempt.time_taken_display = '-'
            else:
                hours = seconds // 3600
                minutes = (seconds % 3600) // 60
                secs = seconds % 60
                
                parts = []
                if hours > 0:
                    parts.append(f'{hours}h')
                if minutes > 0:
                    parts.append(f'{minutes}m')
                if secs > 0 or not parts:
                    parts.append(f'{secs}s')
                
                attempt.time_taken_display = ' '.join(parts)
    
    @api.depends('auto_score', 'manual_score')
    def _compute_final_score(self):
        """Calculate total score"""
        for attempt in self:
            attempt.final_score = attempt.auto_score + attempt.manual_score
    
    @api.depends('final_score', 'max_score')
    def _compute_score_percentage(self):
        """Calculate percentage score"""
        for attempt in self:
            if attempt.max_score > 0:
                attempt.score_percentage = (attempt.final_score / attempt.max_score) * 100
            else:
                attempt.score_percentage = 0.0
    
    @api.depends('score_percentage', 'activity_id.quiz_pass_percentage')
    def _compute_passed(self):
        """Determine if attempt passed"""
        for attempt in self:
            if attempt.activity_id.quiz_pass_percentage:
                attempt.passed = attempt.score_percentage >= attempt.activity_id.quiz_pass_percentage
            else:
                attempt.passed = False
    
    @api.depends('response_ids')
    def _compute_response_count(self):
        """Count responses"""
        for attempt in self:
            attempt.response_count = len(attempt.response_ids)
    
    @api.depends('response_ids')
    def _compute_questions_answered(self):
        """Count answered questions"""
        for attempt in self:
            attempt.questions_answered = len(attempt.response_ids.filtered(
                lambda r: r.answer_ids or r.response_text or r.response_number))
    
    @api.depends('response_ids.is_correct')
    def _compute_questions_correct(self):
        """Count correct answers"""
        for attempt in self:
            attempt.questions_correct = len(attempt.response_ids.filtered('is_correct'))
    
    @api.depends('response_ids.question_id.requires_manual_grading')
    def _compute_requires_manual_grading(self):
        """Check if any question needs manual grading"""
        for attempt in self:
            attempt.requires_manual_grading = any(
                attempt.response_ids.mapped('question_id.requires_manual_grading'))
    
    @api.depends('state', 'requires_manual_grading', 'response_ids.graded_by_id')
    def _compute_grading_status(self):
        """Determine overall grading status"""
        for attempt in self:
            if attempt.state in ['draft', 'in_progress']:
                attempt.grading_status = 'pending'
            elif not attempt.requires_manual_grading:
                attempt.grading_status = 'auto_graded'
            else:
                manual_questions = attempt.response_ids.filtered(
                    lambda r: r.question_id.requires_manual_grading)
                graded_questions = manual_questions.filtered('graded_by_id')
                
                if len(graded_questions) == len(manual_questions):
                    attempt.grading_status = 'fully_graded'
                elif len(graded_questions) > 0:
                    attempt.grading_status = 'partially_graded'
                else:
                    attempt.grading_status = 'pending'
    
    def action_start_attempt(self):
        """Start the quiz attempt"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_('This attempt has already been started.'))
        
        # Check attempt limits
        previous_attempts = self.search_count([
            ('activity_id', '=', self.activity_id.id),
            ('student_id', '=', self.student_id.id),
            ('state', '!=', 'draft'),
        ])
        
        if self.activity_id.max_attempts > 0 and previous_attempts >= self.activity_id.max_attempts:
            raise UserError(_(
                'You have reached the maximum number of attempts (%s) for this quiz.'
            ) % self.activity_id.max_attempts)
        
        self.write({
            'state': 'in_progress',
            'started_at': fields.Datetime.now(),
            'attempt_number': previous_attempts + 1,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/quiz/{self.id}/take',
            'target': 'self',
        }
    
    def action_submit_attempt(self):
        """Submit the quiz attempt"""
        self.ensure_one()
        
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress attempts can be submitted.'))
        
        self.write({
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        })
        
        # Auto-grade what we can
        self.action_auto_grade()
        
        # Create evidence log
        self._create_evidence_log()
        
        # Create outcome if appropriate
        if self.grading_status == 'fully_graded':
            self._create_assessment_outcome()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Quiz Submitted'),
                'message': _('Your quiz has been submitted successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_auto_grade(self):
        """Automatically grade objective questions"""
        self.ensure_one()
        
        auto_score = 0.0
        
        for response in self.response_ids:
            if not response.question_id.requires_manual_grading:
                score = response._calculate_score()
                auto_score += score
        
        self.write({
            'auto_score': auto_score,
            'state': 'auto_graded' if not self.requires_manual_grading else self.state,
        })
        
        # Backup responses to JSON
        self._backup_responses_to_json()
    
    def action_manual_grade(self):
        """Open manual grading wizard"""
        self.ensure_one()
        
        return {
            'name': _('Manual Grading'),
            'type': 'ir.actions.act_window',
            'res_model': 'rto.quiz.attempt',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('rto_lms.view_rto_quiz_attempt_grading_form').id,
            'target': 'new',
        }
    
    def action_complete_grading(self):
        """Mark grading as complete"""
        self.ensure_one()
        
        if self.grading_status != 'fully_graded':
            raise UserError(_('All questions must be graded before completing.'))
        
        self.write({
            'state': 'completed',
            'graded_by_id': self.env.user.id,
            'graded_at': fields.Datetime.now(),
        })
        
        # Create/update outcome
        self._create_assessment_outcome()
    
    def _backup_responses_to_json(self):
        """Backup all responses to JSON for audit trail"""
        self.ensure_one()
        
        responses_data = []
        for response in self.response_ids:
            responses_data.append({
                'question_id': response.question_id.id,
                'question_text': response.question_id.question,
                'question_type': response.question_id.question_type,
                'answer_ids': response.answer_ids.ids,
                'answer_texts': response.answer_ids.mapped('text_value'),
                'response_text': response.response_text,
                'response_number': response.response_number,
                'points_earned': response.points_earned,
                'is_correct': response.is_correct,
                'timestamp': response.response_timestamp.isoformat() if response.response_timestamp else None,
            })
        
        self.response_data = json.dumps(responses_data, ensure_ascii=False, indent=2)
    
    def _create_evidence_log(self):
        """Create immutable evidence log for quiz attempt"""
        self.ensure_one()
        
        if self.evidence_log_id:
            return self.evidence_log_id
        
        content_data = {
            'attempt_id': self.id,
            'attempt_reference': self.reference,
            'attempt_number': self.attempt_number,
            'quiz_name': self.activity_id.name,
            'student_name': self.student_id.name,
            'score_achieved': self.final_score,
            'max_score': self.max_score,
            'score_percentage': self.score_percentage,
            'passed': self.passed,
            'questions_answered': self.questions_answered,
            'questions_correct': self.questions_correct,
            'time_taken': self.time_taken_display,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'responses': json.loads(self.response_data) if self.response_data else [],
        }
        
        evidence = self.env['rto.evidence.log'].create({
            'activity_id': self.activity_id.id,
            'student_id': self.student_id.id,
            'evidence_type': 'quiz_result',
            'title': f'Quiz Attempt: {self.activity_id.name} - Attempt {self.attempt_number}',
            'content_data': json.dumps(content_data, ensure_ascii=False, indent=2),
            'notes': f'Quiz submitted. Score: {self.final_score}/{self.max_score} ({self.score_percentage:.1f}%)',
        })
        
        self.evidence_log_id = evidence.id
        return evidence
    
    def _create_assessment_outcome(self):
        """Create or update assessment outcome"""
        self.ensure_one()
        
        if not self.activity_id.rto_activity_type == 'assessment':
            return
        
        # Determine outcome code based on pass/fail
        outcome_code = '20' if self.passed else '30'
        
        outcome_vals = {
            'activity_id': self.activity_id.id,
            'student_id': self.student_id.id,
            'outcome_level': 'activity',
            'outcome_code': outcome_code,
            'outcome_date': fields.Date.today(),
            'assessor_id': self.graded_by_id.employee_id.id if self.graded_by_id else False,
            'assessor_comments': self.grader_feedback or f'Quiz score: {self.final_score}/{self.max_score} ({self.score_percentage:.1f}%)',
            'actual_score': self.final_score,
            'max_score': self.max_score,
            'score_percentage': self.score_percentage,
        }
        
        if self.outcome_id:
            # Update existing outcome
            self.outcome_id.action_create_new_version(outcome_vals)
        else:
            # Create new outcome
            outcome = self.env['rto.assessment.outcome'].create(outcome_vals)
            self.outcome_id = outcome.id
