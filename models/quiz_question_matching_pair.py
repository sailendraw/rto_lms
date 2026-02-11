# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Matching question pairs for matching-type quiz questions."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LMSQuizQuestionMatchingPair(models.Model):
    """Matching question pair record for prompt-response matching."""

    _name = 'lms.quiz.question.matching.pair'
    _description = 'Quiz Question Matching Pair'
    _order = 'sequence, id'

    question_id = fields.Many2one(
        'lms.quiz.question',
        string='Question',
        required=True,
        ondelete='cascade',
        index=True,
        help='Parent matching question.',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order of this pair.',
    )
    prompt = fields.Html(
        string='Prompt',
        required=True,
        sanitize=True,
        help='The prompt text that learners will match (left side).',
    )
    response = fields.Html(
        string='Response',
        required=True,
        sanitize=True,
        help='The response text that can be matched (right side).',
    )
    correct_match_id = fields.Many2one(
        'lms.quiz.question.matching.pair',
        string='Correct Match',
        domain="[('question_id', '=', question_id), ('id', '!=', id)]",
        help='The response pair that correctly matches this prompt.',
    )

    @api.constrains('correct_match_id', 'question_id')
    def _check_correct_match_same_question(self):
        """Ensure correct match belongs to the same question."""
        for pair in self:
            if pair.correct_match_id and pair.correct_match_id.question_id != pair.question_id:
                raise ValidationError(_(
                    'Correct match must belong to the same question. '
                    'Pair "%(prompt)s" references a match from a different question.',
                    prompt=pair.prompt
                ))

    @api.constrains('correct_match_id')
    def _check_no_self_reference(self):
        """Prevent a pair from matching to itself."""
        for pair in self:
            if pair.correct_match_id == pair:
                raise ValidationError(_(
                    'A matching pair cannot match to itself. '
                    'Please select a different response for "%(prompt)s".',
                    prompt=pair.prompt
                ))
