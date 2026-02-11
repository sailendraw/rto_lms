# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Individual question answer records captured per quiz attempt."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext


class LMSQuizAttemptAnswer(models.Model):
    """Answer record that stores learner responses and grading details."""

    _name = 'lms.quiz.attempt.answer'
    _description = 'Quiz Attempt Answer'
    _order = 'sequence, id'

    attempt_id = fields.Many2one(
        'lms.quiz.attempt',
        string='Attempt',
        required=True,
        ondelete='cascade',
        index=True,
    )
    question_id = fields.Many2one(
        'lms.quiz.question',
        string='Question',
        required=True,
        ondelete='restrict',
        index=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Locked order of the question inside this attempt.',
    )
    question_type = fields.Selection(
        related='question_id.question_type',
        string='Question Type',
        store=True,
    )
    selected_answer_id = fields.Many2one(
        'lms.quiz.question.answer',
        string='Selected Answer',
        domain="[('question_id', '=', question_id)]",
        help='Selected response for MCQ Single and True/False questions.',
    )
    selected_answer_ids = fields.Many2many(
        'lms.quiz.question.answer',
        'lms_attempt_answer_selected_rel',
        'attempt_answer_id',
        'question_answer_id',
        string='Selected Answers',
        domain="[('question_id', '=', question_id)]",
        help='Multiple selections for MCQ Multi questions.',
    )
    answer_text = fields.Html(
        string='Learner Response',
        sanitize=True,
        help='Stored text for short answer and essay questions.',
    )
    numerical_value = fields.Float(
        string='Numerical Response',
        help='Learner response for numerical questions.',
    )
    matching_response = fields.Text(
        string='Matching Selections',
        help='JSON storage for matching question responses: {prompt_pair_id: selected_response_pair_id}.',
    )
    auto_score = fields.Float(
        string='Auto Score',
        default=0.0,
        help='Score awarded by the auto-grader.',
    )
    manual_score = fields.Float(
        string='Manual Score',
        default=0.0,
        help='Score supplied by a trainer for subjective questions.',
    )
    graded_by_id = fields.Many2one(
        'res.users',
        string='Graded By',
        readonly=True,
        help='Trainer who supplied the manual score.',
    )
    graded_at = fields.Datetime(
        string='Graded At',
        readonly=True,
    )
    total_score = fields.Float(
        string='Total Score',
        compute='_compute_total_score',
        store=True,
    )
    is_correct = fields.Boolean(
        string='Is Correct',
        compute='_compute_is_correct',
        store=True,
    )
    dependency_state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('unlocked', 'Unlocked'),
            ('blocked', 'Blocked'),
        ],
        string='Dependency State',
        default='pending',
        help='Tracks dependency evaluation for auditability.',
    )
    dependency_log = fields.Text(
        string='Dependency Notes',
        help='Optional narrative describing dependency evaluation results.',
    )

    _sql_constraints = [
        ('attempt_question_unique', 'unique(attempt_id, question_id)', 'Each question can only appear once per attempt.'),
    ]

    @api.depends('auto_score', 'manual_score')
    def _compute_total_score(self):
        for answer in self:
            answer.total_score = answer.auto_score + answer.manual_score

    @api.depends('question_type', 'selected_answer_id', 'selected_answer_ids', 'auto_score', 'manual_score')
    def _compute_is_correct(self):
        for answer in self:
            if answer.question_type in ('mcq_single', 'tf'):
                answer.is_correct = bool(answer.selected_answer_id and answer.selected_answer_id.is_correct and answer.auto_score > 0)
            elif answer.question_type == 'mcq_multi':
                correct_answers = answer.question_id.answer_ids.filtered('is_correct')
                if correct_answers and answer.selected_answer_ids:
                    answer.is_correct = set(answer.selected_answer_ids.ids) == set(correct_answers.ids)
                else:
                    answer.is_correct = False
            elif answer.question_type in ('numerical', 'matching'):
                answer.is_correct = answer.auto_score >= answer.question_id.max_score
            elif answer.question_type in ('short', 'essay'):
                answer.is_correct = answer.manual_score >= answer.question_id.max_score
            else:
                answer.is_correct = False

    @api.constrains('selected_answer_id', 'question_id')
    def _check_answer_belongs_to_question(self):
        for answer in self:
            if answer.selected_answer_id and answer.selected_answer_id.question_id != answer.question_id:
                raise ValidationError(_('Selected answer must belong to the same question.'))

    def has_response(self):
        """Return True when the learner has provided a response."""
        self.ensure_one()
        if self.question_type in ('mcq_single', 'tf'):
            return bool(self.selected_answer_id)
        elif self.question_type == 'mcq_multi':
            return bool(self.selected_answer_ids)
        elif self.question_type == 'numerical':
            return self.numerical_value is not False
        elif self.question_type == 'matching':
            return bool(self.matching_response)
        elif self.question_type in ('short', 'essay'):
            text_value = html2plaintext(self.answer_text or '').strip()
            return bool(text_value)
        return False

    def evaluate_auto_score(self):
        """Recalculate auto score for all auto-gradable question types."""
        for answer in self:
            if answer.question_type == 'mcq_single':
                answer._grade_mcq_single()
            elif answer.question_type == 'mcq_multi':
                answer._grade_mcq_multi()
            elif answer.question_type == 'tf':
                answer._grade_true_false()
            elif answer.question_type == 'numerical':
                answer._grade_numerical()
            elif answer.question_type == 'matching':
                answer._grade_matching()
            elif answer.question_type == 'short':
                answer._grade_short_answer()
            elif answer.question_type == 'essay':
                # Essay always requires manual grading
                answer.auto_score = 0.0
            else:
                answer.auto_score = 0.0

    def _grade_mcq_single(self):
        """Grade single-select MCQ question."""
        self.ensure_one()
        if not self.selected_answer_id:
            self.auto_score = 0.0
            return

        if self.selected_answer_id.is_correct:
            self.auto_score = self.selected_answer_id.score or self.question_id.max_score
        else:
            self.auto_score = 0.0

    def _grade_true_false(self):
        """Grade true/false question (same logic as MCQ single)."""
        self._grade_mcq_single()

    def _grade_mcq_multi(self):
        """Grade multi-select MCQ with partial credit support."""
        self.ensure_one()
        if not self.selected_answer_ids:
            self.auto_score = 0.0
            return

        correct_answers = self.question_id.answer_ids.filtered('is_correct')
        if not correct_answers:
            self.auto_score = 0.0
            return

        selected_correct = self.selected_answer_ids.filtered('is_correct')
        selected_incorrect = self.selected_answer_ids - selected_correct

        if not self.question_id.allow_partial_credit:
            # All-or-nothing: must select exactly the correct answers
            if set(self.selected_answer_ids.ids) == set(correct_answers.ids):
                self.auto_score = self.question_id.max_score
            else:
                self.auto_score = 0.0
        else:
            # Partial credit with penalty for wrong selections
            total_correct = len(correct_answers)
            total_incorrect = len(self.question_id.answer_ids) - total_correct

            correct_ratio = len(selected_correct) / total_correct if total_correct else 0

            # Penalize incorrect selections (if there are incorrect options available)
            if total_incorrect > 0:
                incorrect_penalty = len(selected_incorrect) / total_incorrect
                score_ratio = max(0, correct_ratio - incorrect_penalty)
            else:
                score_ratio = correct_ratio

            self.auto_score = score_ratio * self.question_id.max_score

    def _grade_numerical(self):
        """Grade numerical answer with tolerance checking."""
        self.ensure_one()
        if self.numerical_value is False:
            self.auto_score = 0.0
            return

        expected = self.question_id.expected_answer_numerical
        tolerance = self.question_id.numerical_tolerance

        if abs(self.numerical_value - expected) <= tolerance:
            self.auto_score = self.question_id.max_score
        else:
            self.auto_score = 0.0

    def _grade_matching(self):
        """Grade matching question with proportional scoring."""
        self.ensure_one()
        if not self.matching_response:
            self.auto_score = 0.0
            return

        import json
        try:
            selections = json.loads(self.matching_response)
        except (json.JSONDecodeError, TypeError):
            self.auto_score = 0.0
            return

        total_pairs = len(self.question_id.matching_pair_ids)
        if total_pairs == 0:
            self.auto_score = 0.0
            return

        correct_count = 0
        for pair in self.question_id.matching_pair_ids:
            selected_match_id = selections.get(str(pair.id))
            if selected_match_id and pair.correct_match_id:
                if int(selected_match_id) == pair.correct_match_id.id:
                    correct_count += 1

        # Proportional scoring: (correct matches / total pairs) * max_score
        self.auto_score = (correct_count / total_pairs) * self.question_id.max_score

    def _grade_short_answer(self):
        """Auto-grade short answer if expected answer is provided."""
        self.ensure_one()
        if not self.question_id.expected_answer_text:
            # No expected answer, requires manual grading
            self.auto_score = 0.0
            return

        if not self.answer_text:
            self.auto_score = 0.0
            return

        student_text = html2plaintext(self.answer_text).strip()
        expected_text = html2plaintext(self.question_id.expected_answer_text).strip()

        if not student_text:
            self.auto_score = 0.0
            return

        if self.question_id.case_sensitive:
            match = student_text == expected_text
        else:
            match = student_text.lower() == expected_text.lower()

        if match:
            self.auto_score = self.question_id.max_score
        else:
            self.auto_score = 0.0

    def reset_dependency_tracking(self):
        """Reset dependency metadata when the attempt restarts."""
        for answer in self:
            answer.dependency_state = 'pending'
            answer.dependency_log = False

    def write(self, vals):
        if 'manual_score' in vals:
            manual_records = self.filtered(lambda ans: ans.question_id.is_manual_grading)
            other_records = self - manual_records
            if manual_records:
                manual_vals = vals.copy()
                manual_vals.setdefault('graded_by_id', self.env.user.id)
                manual_vals.setdefault('graded_at', fields.Datetime.now())
                super(LMSQuizAttemptAnswer, manual_records).write(manual_vals)
            if other_records:
                super(LMSQuizAttemptAnswer, other_records).write(vals)
            return True
        return super().write(vals)
