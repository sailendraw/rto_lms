# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Audit-safe quiz attempt model with dependency enforcement and outcome sync."""

import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html2plaintext


class LMSQuizAttempt(models.Model):
    """Learner attempt record bridging LMS quizzes to assessment outcomes."""

    _name = 'lms.quiz.attempt'
    _description = 'Quiz Attempt'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    display_name = fields.Char(
        string='Reference',
        compute='_compute_display_name',
        store=True,
    )
    reference = fields.Char(
        string='Attempt Reference',
        readonly=True,
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True,
    )
    quiz_id = fields.Many2one(
        'lms.quiz.definition',
        string='Quiz Definition',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    slide_id = fields.Many2one(
        related='quiz_id.slide_id',
        string='Slide',
        store=True,
        index=True,
    )
    course_id = fields.Many2one(
        related='quiz_id.course_id',
        string='Course',
        store=True,
        index=True,
    )
    student_id = fields.Many2one(
        'res.partner',
        string='Student',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
    )
    attempt_no = fields.Integer(
        string='Attempt Number',
        default=1,
        readonly=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('submitted', 'Submitted'),
            ('graded', 'Graded'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    started_at = fields.Datetime(
        string='Started At',
        tracking=True,
    )
    submitted_at = fields.Datetime(
        string='Submitted At',
        tracking=True,
    )
    graded_at = fields.Datetime(
        string='Graded At',
        tracking=True,
    )
    auto_score = fields.Float(
        string='Auto Score',
        compute='_compute_auto_score',
        store=True,
    )
    manual_score = fields.Float(
        string='Manual Score',
        compute='_compute_manual_score',
        store=True,
    )
    total_score = fields.Float(
        string='Total Score',
        compute='_compute_total_score',
        store=True,
    )
    max_score = fields.Float(
        string='Maximum Score',
        compute='_compute_max_score',
        store=True,
    )
    score_percentage = fields.Float(
        string='Score Percentage',
        compute='_compute_score_percentage',
        store=True,
    )
    passed = fields.Boolean(
        string='Passed',
        compute='_compute_passed',
        store=True,
    )
    requires_manual_grading = fields.Boolean(
        string='Requires Manual Grading',
        compute='_compute_requires_manual_grading',
        store=True,
    )
    question_order_json = fields.Text(
        string='Locked Question Order',
        readonly=True,
        help='JSON array representing the question order delivered to the learner.',
    )
    dependency_audit_log = fields.Text(
        string='Dependency Audit Log',
        help='Readable log describing the last dependency evaluation.',
    )
    answer_ids = fields.One2many(
        'lms.quiz.attempt.answer',
        'attempt_id',
        string='Answers',
    )
    outcome_id = fields.Many2one(
        'rto.assessment.outcome',
        string='Assessment Outcome',
        readonly=True,
        ondelete='set null',
    )
    grader_id = fields.Many2one(
        'res.users',
        string='Graded By',
        readonly=True,
    )
    manual_feedback = fields.Html(
        string='Grader Feedback',
        help='Optional summary feedback provided during grading.',
    )

    _sql_constraints = [
        (
            'unique_attempt_number',
            'unique(quiz_id, student_id, attempt_no)',
            'Attempt numbers must be unique per student and quiz.',
        ),
    ]

    @api.depends('reference', 'quiz_id.name', 'student_id.name', 'attempt_no')
    def _compute_display_name(self):
        for attempt in self:
            if attempt.reference and attempt.reference != _('New'):
                attempt.display_name = attempt.reference
            else:
                quiz_name = attempt.quiz_id.name or _('Quiz')
                student_name = attempt.student_id.name or _('Student')
                attempt.display_name = f"{quiz_name} - {student_name} (Attempt {attempt.attempt_no})"

    @api.depends('answer_ids.auto_score')
    def _compute_auto_score(self):
        for attempt in self:
            attempt.auto_score = sum(attempt.answer_ids.mapped('auto_score'))

    @api.depends('answer_ids.manual_score')
    def _compute_manual_score(self):
        for attempt in self:
            attempt.manual_score = sum(attempt.answer_ids.mapped('manual_score'))

    @api.depends('auto_score', 'manual_score')
    def _compute_total_score(self):
        for attempt in self:
            attempt.total_score = attempt.auto_score + attempt.manual_score

    @api.depends('answer_ids.question_id.max_score')
    def _compute_max_score(self):
        for attempt in self:
            attempt.max_score = sum(attempt.answer_ids.mapped('question_id.max_score'))

    @api.depends('total_score', 'max_score')
    def _compute_score_percentage(self):
        for attempt in self:
            if attempt.max_score > 0:
                attempt.score_percentage = (attempt.total_score / attempt.max_score) * 100.0
            else:
                attempt.score_percentage = 0.0

    @api.depends('answer_ids.question_id.is_manual_grading')
    def _compute_requires_manual_grading(self):
        for attempt in self:
            questions = attempt.answer_ids.mapped('question_id') or attempt.quiz_id.question_ids
            attempt.requires_manual_grading = any(questions.mapped('is_manual_grading'))

    @api.depends('score_percentage', 'quiz_id.pass_mark', 'state')
    def _compute_passed(self):
        for attempt in self:
            attempt.passed = bool(
                attempt.state == 'graded'
                and attempt.quiz_id.pass_mark
                and attempt.score_percentage >= attempt.quiz_id.pass_mark
            )

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._inject_attempt_numbers(vals_list)
        for vals in vals_list:
            if vals.get('reference', _('New')) == _('New'):
                vals['reference'] = self.env['ir.sequence'].next_by_code('lms.quiz.attempt') or _('New')
        records = super().create(vals_list)
        return records

    def _inject_attempt_numbers(self, vals_list):
        for vals in vals_list:
            if not vals.get('quiz_id') or not vals.get('student_id'):
                continue
            if vals.get('attempt_no'):
                continue
            domain = [
                ('quiz_id', '=', vals['quiz_id']),
                ('student_id', '=', vals['student_id']),
            ]
            existing = self.search_count(domain)
            vals['attempt_no'] = existing + 1
        return vals_list

    def action_start_attempt(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft attempts can be started.'))
        self._check_attempt_limits()
        locked_questions = self.quiz_id._prepare_locked_questions()
        command_list = [(5, 0, 0)]
        sequence = 1
        for question in locked_questions:
            command_list.append(
                (
                    0,
                    0,
                    {
                        'question_id': question.id,
                        'sequence': sequence,
                        'dependency_state': 'pending',
                        'dependency_log': False,
                    },
                )
            )
            sequence += 1
        self.write({
            'state': 'in_progress',
            'started_at': fields.Datetime.now(),
            'question_order_json': json.dumps(locked_questions.ids),
            'answer_ids': command_list,
            'dependency_audit_log': False,
        })
        self._evaluate_dependencies()
        start_log = _('Attempt started with %s locked questions.') % len(locked_questions)
        existing_log = self.dependency_audit_log or ''
        combined = '\n'.join(line for line in [start_log, existing_log] if line)
        self.dependency_audit_log = combined or start_log
        return True

    def action_submit_attempt(self):
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress attempts can be submitted.'))
        self._ensure_dependencies_met()
        self.answer_ids.evaluate_auto_score()
        self.write({
            'state': 'submitted',
            'submitted_at': fields.Datetime.now(),
        })
        if not self.requires_manual_grading:
            self.action_finalize_grading()
        return True

    def action_finalize_grading(self):
        self.ensure_one()
        if self.state not in ('submitted', 'in_progress'):
            raise UserError(_('Only submitted attempts can be graded.'))
        if self.requires_manual_grading and not self._all_manual_answers_graded():
            raise UserError(_('Grade every short answer question before finalising.'))
        self.write({
            'state': 'graded',
            'graded_at': fields.Datetime.now(),
            'grader_id': self.env.user.id,
        })
        self._ensure_outcome_record()
        return True

    def _all_manual_answers_graded(self):
        self.ensure_one()
        manual_answers = self.answer_ids.filtered(lambda ans: ans.question_id.is_manual_grading)
        if not manual_answers:
            return True
        return all(bool(ans.graded_at) for ans in manual_answers)

    def _check_attempt_limits(self):
        self.ensure_one()
        max_attempts = self.quiz_id.max_attempts
        if not max_attempts:
            return
        domain = [
            ('quiz_id', '=', self.quiz_id.id),
            ('student_id', '=', self.student_id.id),
            ('state', '!=', 'draft'),
        ]
        completed_attempts = self.search_count(domain)
        if completed_attempts >= max_attempts:
            raise UserError(_('Maximum attempts (%s) reached for this quiz.') % max_attempts)

    def _evaluate_dependencies(self):
        """Evaluate dependency graph and update per-question status."""
        self.ensure_one()
        answers_by_question = {answer.question_id.id: answer for answer in self.answer_ids}
        status_map = {}
        audit_lines = []
        for answer in self.answer_ids.sorted(key=lambda ans: ans.sequence):
            question = answer.question_id
            dependency = question.depends_on_question_id
            state = 'unlocked'
            message = _('No dependency')
            if dependency:
                dependency_answer = answers_by_question.get(dependency.id)
                if not dependency_answer:
                    state = 'blocked'
                    message = _('Dependency question is not part of this attempt.')
                elif question.dependency_type == 'sequence':
                    if dependency_answer.has_response():
                        state = 'unlocked'
                        message = _('Dependency satisfied')
                    else:
                        state = 'blocked'
                        message = _(
                            'Answer "%(dependency)s" before attempting "%(question)s".'
                        ) % {
                            'dependency': dependency.name,
                            'question': question.name,
                        }
                elif question.dependency_type == 'answer_value':
                    allowed_ids = set(question.depends_on_answer_ids.ids)
                    selected_id = dependency_answer.selected_answer_id.id if dependency_answer.selected_answer_id else False
                    if selected_id in allowed_ids:
                        state = 'unlocked'
                        message = _('Dependency satisfied')
                    else:
                        state = 'blocked'
                        message = _(
                            'Select an unlocking answer in "%(dependency)s" before "%(question)s".'
                        ) % {
                            'dependency': dependency.name,
                            'question': question.name,
                        }
                else:
                    state = 'blocked'
                    message = _('Unsupported dependency type.')
            answer.write({
                'dependency_state': state,
                'dependency_log': message,
            })
            status_map[answer.id] = {
                'state': state,
                'message': message,
            }
            if state == 'unlocked':
                audit_lines.append(_('Dependency satisfied for question "%s".') % question.name)
        self.dependency_audit_log = '\n'.join(audit_lines) if audit_lines else False
        return status_map

    def _ensure_dependencies_met(self):
        self.ensure_one()
        status_map = self._evaluate_dependencies()
        violations = [info['message'] for info in status_map.values() if info['state'] == 'blocked']
        if violations:
            unique_messages = list(dict.fromkeys(violations))
            raise UserError('\n'.join(unique_messages))

    def get_runtime_payload(self, current_sequence=None):
        """Return ordered question data for the runtime UI."""
        self.ensure_one()
        status_map = self._evaluate_dependencies()
        answers = self.answer_ids.sorted(key=lambda ans: ans.sequence)
        questions = []
        answered_count = 0
        for answer in answers:
            info = status_map.get(answer.id, {'state': 'pending', 'message': _('Pending dependency evaluation')})
            is_unlocked = info['state'] == 'unlocked'
            has_response = answer.has_response()
            if has_response:
                answered_count += 1
            answer_text_plain = html2plaintext(answer.answer_text or '').strip()
            options = []
            if answer.question_type in ('mcq', 'tf'):
                options = [
                    {
                        'id': option.id,
                        'answer_html': option.answer_html,
                    }
                    for option in answer.question_id.answer_ids
                ]
            questions.append({
                'sequence': answer.sequence,
                'question_id': answer.question_id.id,
                'title': answer.question_id.name,
                'question_html': answer.question_id.question_html,
                'question_type': answer.question_id.question_type,
                'max_score': answer.question_id.max_score,
                'options': options,
                'selected_answer_id': answer.selected_answer_id.id,
                'answer_text': answer.answer_text,
                'answer_text_plain': answer_text_plain,
                'is_unlocked': is_unlocked,
                'status_message': info['message'],
                'has_response': has_response,
                'is_manual': answer.question_id.is_manual_grading,
            })
        unlocked_unanswered = [item['sequence'] for item in questions if item['is_unlocked'] and not item['has_response']]
        next_sequence = None
        if unlocked_unanswered:
            if current_sequence:
                later = [seq for seq in unlocked_unanswered if seq > current_sequence]
                next_sequence = later[0] if later else unlocked_unanswered[0]
            else:
                next_sequence = unlocked_unanswered[0]
        elif questions:
            next_sequence = questions[-1]['sequence']
        total = len(questions)
        percent = (answered_count / total * 100.0) if total else 0.0
        return {
            'questions': questions,
            'progress': {
                'answered': answered_count,
                'total': total,
                'percent': percent,
            },
            'next_sequence': next_sequence,
        }

    def record_response(self, question_id, selected_answer_id=None, answer_text=None):
        """Persist a learner response after checking dependencies."""
        self.ensure_one()
        answer = self.answer_ids.filtered(lambda ans: ans.question_id.id == question_id)
        if not answer:
            raise UserError(_('Question is not part of this attempt.'))
        status_map = self._evaluate_dependencies()
        info = status_map.get(answer.id)
        if info and info['state'] != 'unlocked':
            raise UserError(info['message'])
        values = {}
        if answer.question_type in ('mcq', 'tf'):
            if selected_answer_id:
                option = self.env['lms.quiz.question.answer'].browse(selected_answer_id)
                if not option or option.question_id != answer.question_id:
                    raise UserError(_('Selected answer is not valid for this question.'))
                values['selected_answer_id'] = option.id
            else:
                values['selected_answer_id'] = False
            values['answer_text'] = False
        elif answer.question_type == 'short':
            values['selected_answer_id'] = False
            values['answer_text'] = (answer_text or '').strip()
        else:
            raise UserError(_('Unsupported question type: %s') % (answer.question_type,))
        answer.write(values)
        answer.evaluate_auto_score()
        self._evaluate_dependencies()
        return True

    def _ensure_outcome_record(self):
        self.ensure_one()
        assessor = self._resolve_assessor_employee()
        outcome_vals = {
            'course_id': self.course_id.id,
            'activity_id': self.slide_id.id,
            'student_id': self.student_id.id,
            'outcome_level': 'activity',
            'outcome_code': '20' if self.passed else '30',
            'assessor_id': assessor.id,
            'assessor_comments': self.manual_feedback,
            'attempt_number': self.attempt_no,
            'score': self.total_score,
            'max_score': self.max_score,
        }
        if self.outcome_id:
            self.outcome_id.write(outcome_vals)
        else:
            self.outcome_id = self.env['rto.assessment.outcome'].create(outcome_vals)

    def _resolve_assessor_employee(self):
        self.ensure_one()
        employee = self.env.user.employee_ids[:1]
        if not employee:
            raise ValidationError(_('Configure an employee record for the current user before grading.'))
        return employee
