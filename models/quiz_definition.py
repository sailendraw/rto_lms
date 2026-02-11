# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Quiz definition model binding reusable question bank to LMS slides."""

from collections import defaultdict
import random

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class LMSQuizDefinition(models.Model):
    """Reusable quiz configuration attached to a quiz slide."""

    _name = 'lms.quiz.definition'
    _description = 'Quiz Definition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Quiz Name',
        required=True,
        tracking=True,
    )
    slide_id = fields.Many2one(
        'slide.slide',
        string='Quiz Slide',
        required=True,
        ondelete='cascade',
        index=True,
        domain="[('slide_category', '=', 'quiz')]",
        tracking=True,
    )
    course_id = fields.Many2one(
        related='slide_id.channel_id',
        string='Course',
        store=True,
        index=True,
    )
    question_ids = fields.Many2many(
        'lms.quiz.question',
        'lms_quiz_definition_question_rel',
        'definition_id',
        'question_id',
        string='Question Pool',
        help='Select questions that can be drawn for this quiz.',
    )
    question_count = fields.Integer(
        string='Questions Configured',
        compute='_compute_question_count',
        store=True,
    )
    randomize = fields.Boolean(
        string='Randomize Question Order',
        default=True,
        help='Shuffle question order per attempt while respecting dependencies.',
    )
    question_limit = fields.Integer(
        string='Question Limit',
        default=0,
        help='Optional limit on how many questions are delivered per attempt.',
    )
    pass_mark = fields.Float(
        string='Pass Mark (%)',
        default=70.0,
        help='Percentage score required to achieve a pass result.',
    )
    max_attempts = fields.Integer(
        string='Maximum Attempts',
        default=0,
        help='0 means unlimited attempts for learners.',
    )
    attempt_ids = fields.One2many(
        'lms.quiz.attempt',
        'quiz_id',
        string='Attempts',
    )
    attempt_count = fields.Integer(
        string='Attempt Count',
        compute='_compute_attempt_count',
        store=True,
    )

    _sql_constraints = [
        ('slide_unique', 'unique(slide_id)', 'Each quiz slide can only have one quiz definition.'),
    ]

    @api.depends('question_ids')
    def _compute_question_count(self):
        for quiz in self:
            quiz.question_count = len(quiz.question_ids)

    @api.depends('attempt_ids')
    def _compute_attempt_count(self):
        for quiz in self:
            quiz.attempt_count = len(quiz.attempt_ids)

    @api.constrains('question_ids')
    def _check_question_course_alignment(self):
        for quiz in self:
            invalid = quiz.question_ids.filtered(lambda q: q.course_id != quiz.course_id)
            if invalid:
                raise ValidationError(_('All questions must belong to the same course as the quiz slide.'))

    @api.constrains('question_ids')
    def _check_dependency_membership(self):
        for quiz in self:
            missing = quiz.question_ids.filtered(
                lambda q: q.depends_on_question_id and q.depends_on_question_id not in quiz.question_ids
            )
            if missing:
                first = missing[0]
                raise ValidationError(
                    _('Question "%(question)s" depends on "%(dependency)s" which is not part of this quiz.')
                    % {
                        'question': first.name,
                        'dependency': first.depends_on_question_id.name,
                    }
                )

    @api.constrains('question_limit', 'question_ids')
    def _check_question_limit(self):
        for quiz in self:
            if quiz.question_limit is not None and quiz.question_limit < 0:
                raise ValidationError(_('Question limit cannot be negative.'))
            if quiz.question_limit and quiz.question_limit > len(quiz.question_ids):
                raise ValidationError(_('Question limit cannot exceed the total number of configured questions.'))

    @api.constrains('pass_mark')
    def _check_pass_mark_range(self):
        for quiz in self:
            if quiz.pass_mark < 0 or quiz.pass_mark > 100:
                raise ValidationError(_('Pass mark must be between 0 and 100.'))

    @api.constrains('max_attempts')
    def _check_max_attempts(self):
        for quiz in self:
            if quiz.max_attempts < 0:
                raise ValidationError(_('Maximum attempts cannot be negative.'))

    def _prepare_locked_questions(self, seed=None):
        """Return question recordset ordered for an attempt respecting dependencies."""
        self.ensure_one()
        questions = self._topological_sort(seed=seed)
        if not questions:
            raise UserError(_('Configure at least one question before delivering the quiz.'))
        if self.question_limit:
            questions = questions[: self.question_limit]
        if not questions:
            raise UserError(_('No questions available after applying the question limit.'))
        return questions

    def _topological_sort(self, seed=None):
        """Topologically order questions so dependencies are always satisfied."""
        self.ensure_one()
        if not self.question_ids:
            return self.question_ids

        adjacency = defaultdict(list)
        indegree = {question.id: 0 for question in self.question_ids}
        for question in self.question_ids:
            dependency = question.depends_on_question_id
            if dependency and dependency.id in indegree:
                adjacency[dependency.id].append(question.id)
                indegree[question.id] += 1

        queue = [question_id for question_id, degree in indegree.items() if degree == 0]
        queue.sort()  # deterministic baseline before randomization
        rng = random.Random(seed)
        ordered_ids = []

        while queue:
            if self.randomize and len(queue) > 1:
                idx = rng.randrange(len(queue))
            else:
                idx = 0
            current = queue.pop(idx)
            ordered_ids.append(current)

            children = list(adjacency[current])
            if self.randomize and len(children) > 1:
                rng.shuffle(children)
            else:
                children.sort()

            for child in children:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if len(ordered_ids) != len(indegree):
            raise UserError(_('Question dependency graph is invalid; please review dependencies.'))

        return self.env['lms.quiz.question'].browse(ordered_ids)

    def write(self, vals):
        """Trigger sync on related quiz slides when definition changes."""
        result = super().write(vals)
        # Sync if questions are added/removed from definition
        if 'question_ids' in vals:
            slides = self.env['slide.slide'].search([
                ('quiz_definition_id', 'in', self.ids),
                ('slide_category', '=', 'quiz')
            ])
            for slide in slides:
                slide.action_sync_quiz_questions()
        return result
