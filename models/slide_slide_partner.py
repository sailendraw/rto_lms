from odoo import fields, models


class SlideSlidePartner(models.Model):
    _inherit = 'slide.slide.partner'
    
    quiz_text_answers = fields.Json(
        string='Quiz Text Answers',
        help='Stores student answers for text-based questions (short_answer, numerical)',
        default=dict
    )
