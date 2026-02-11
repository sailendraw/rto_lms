# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Answer options for LMS quiz questions."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LMSQuizQuestionAnswer(models.Model):
    """Question answer option supporting MCQ / True-False scoring."""

    _name = 'lms.quiz.question.answer'
    _description = 'Quiz Question Answer'
    _order = 'sequence, id'

    question_id = fields.Many2one(
        'lms.quiz.question',
        string='Question',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    answer_html = fields.Html(
        string='Answer Text',
        sanitize=True,
        required=True,
    )
    is_correct = fields.Boolean(
        string='Correct',
        help='Mark true answers for auto-grading.',
    )
    score = fields.Float(
        string='Score Weight',
        default=0.0,
        help='Optional score override when partial credit is needed.',
    )
    partial_credit_percentage = fields.Float(
        string='Partial Credit (%)',
        default=0.0,
        help='For multi-select questions: percentage of max_score awarded if this answer is selected (auto-calculated).',
    )

    @api.constrains('question_id', 'is_correct')
    def _check_text_question_no_answers(self):
        for answer in self:
            if answer.question_id.question_type in ('short', 'essay', 'numerical', 'matching'):
                raise ValidationError(_('%s questions cannot have predefined answer options.') % answer.question_id.question_type.title())

    @api.constrains('score')
    def _check_score_non_negative(self):
        for answer in self:
            if answer.score < 0:
                raise ValidationError(_('Answer score weight cannot be negative.'))
