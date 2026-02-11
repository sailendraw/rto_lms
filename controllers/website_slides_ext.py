# -*- coding: utf-8 -*-
"""
RTO LMS Controller Extensions
Extends website_slides controllers to support enhanced question types
"""

import logging

from odoo import http
from odoo.http import request
from odoo.addons.website_slides.controllers.main import WebsiteSlides
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

_logger.info("="*80)
_logger.info("RTO LMS: Loading website_slides controller extension")
_logger.info("="*80)


class RTOWebsiteSlides(WebsiteSlides):
    """Extend WebsiteSlides to pass enhanced question type data to templates"""
    
    @http.route('/slides/slide/quiz/question_add_or_update', type="jsonrpc", auth="user", website=True)
    def slide_quiz_question_add_or_update(self, slide_id, question, sequence, answer_ids, existing_question_id=None, question_type=None):
        """Override to pass question as dictionary and handle question_type"""
        
        # Prepare new question values
        new_question_values = {
            'sequence': sequence,
            'question': question,
            'slide_id': slide_id,
            'answer_ids': [(0, 0, {
                'sequence': answer['sequence'],
                'text_value': answer['text_value'],
                'is_correct': answer['is_correct'],
                'comment': answer['comment']
            }) for answer in answer_ids]
        }
        
        # Add question_type if provided
        if question_type:
            new_question_values['question_type'] = question_type

        try:
            # Validate the fields
            slide_question = request.env['slide.question'].new(new_question_values)
            slide_question._validate_fields(new_question_values.keys())
        except ValidationError as e:
            return {'error': e.args[0]}

        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']
        
        # Delete existing question if updating
        if existing_question_id:
            request.env['slide.question'].search([
                ('slide_id', '=', slide.id),
                ('id', '=', int(existing_question_id))
            ]).unlink()

        # Mark slide as incomplete for the user
        request.env['slide.slide.partner'].search([
            ('slide_id', '=', slide_id),
            ('partner_id', '=', request.env.user.partner_id.id)
        ]).write({'completed': False})

        # Create the question
        slide_question = request.env['slide.question'].create(new_question_values)
        
        # Convert question to dictionary format
        is_designer = request.env.user.has_group('website.group_website_designer')
        question_data = {
            'answer_ids': [{
                'comment': answer.comment if is_designer else None,
                'id': answer.id,
                'is_correct': answer.is_correct if slide.user_has_completed or is_designer else None,
                'text_value': answer.text_value,
            } for answer in slide_question.sudo().answer_ids],
            'id': slide_question.id,
            'question': slide_question.question,
            'sequence': slide_question.sequence,
        }
        
        # Add RTO-specific fields if they exist
        if hasattr(slide_question, 'question_type') and slide_question.question_type:
            question_data['question_type'] = slide_question.question_type
            
        if hasattr(slide_question, 'question_points'):
            question_data['question_points'] = slide_question.question_points
            
        # True/False specific
        if hasattr(slide_question, 'correct_answer_tf') and slide_question.question_type == 'true_false':
            question_data['correct_answer_tf'] = slide_question.correct_answer_tf
            
        # Short answer specific
        if hasattr(slide_question, 'correct_answer_text') and slide_question.question_type == 'short_answer':
            question_data['correct_answer_text'] = slide_question.correct_answer_text
            
        # Numerical specific
        if hasattr(slide_question, 'correct_answer_numerical') and slide_question.question_type == 'numerical':
            question_data['correct_answer_numerical'] = slide_question.correct_answer_numerical
            if hasattr(slide_question, 'accepted_error'):
                question_data['accepted_error'] = slide_question.accepted_error
            if hasattr(slide_question, 'unit_of_measure'):
                question_data['unit_of_measure'] = slide_question.unit_of_measure
                
        # Matching specific
        if hasattr(slide_question, 'question_type') and slide_question.question_type == 'matching':
            if hasattr(slide_question, 'matching_pair_ids'):
                question_data['matching_pair_ids'] = [{
                    'id': pair.id,
                    'prompt': pair.prompt,
                    'response': pair.response,
                    'correct_match_id': pair.correct_match_id.id if pair.correct_match_id else None,
                } for pair in slide_question.matching_pair_ids]
        
        # Render template with dictionary data
        return request.env['ir.qweb']._render('website_slides.lesson_content_quiz_question', {
            'slide': slide,
            'question': question_data,
        })
    
    @http.route('/slides/slide/quiz/get', type="jsonrpc", auth="public", website=True)
    def slide_quiz_get(self, slide_id):
        """Override to ensure our enhanced _get_slide_quiz_data is called"""
        _logger.info("="*80)
        _logger.info("RTO: slide_quiz_get called for slide_id=%s", slide_id)
        _logger.info("="*80)
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']
        result = self._get_slide_quiz_data(slide)
        _logger.info("RTO: Returning quiz data with %s questions", len(result.get('slide_questions', [])))
        return result
    
    def _get_slide_quiz_data(self, slide):
        """Override to include question_type and other RTO-specific fields"""
        values = super()._get_slide_quiz_data(slide)
        
        # Get stored text answers if quiz is completed
        stored_text_answers = {}
        if slide.user_has_completed:
            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide.id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)
            if slide_partner and slide_partner.quiz_text_answers:
                stored_text_answers = slide_partner.quiz_text_answers
        
        # Enhance slide_questions with RTO-specific fields
        is_designer = request.env.user.has_group('website.group_website_designer')
        enhanced_questions = []
        
        for question in slide.question_ids:
            question_type = getattr(question, 'question_type', None)
            
            question_data = {
                'answer_ids': [{
                    'comment': answer.comment if is_designer else None,
                    'id': answer.id,
                    'is_correct': answer.is_correct if slide.user_has_completed or is_designer else None,
                    'text_value': answer.text_value,
                } for answer in question.sudo().answer_ids],
                'id': question.id,
                'question': question.question,
                'sequence': question.sequence,
            }
            
            # Add RTO-specific fields if they exist
            if question_type:
                question_data['question_type'] = question_type
                
            if hasattr(question, 'question_points'):
                question_data['question_points'] = question.question_points
                
            # True/False specific
            if hasattr(question, 'correct_answer_tf') and question_type == 'true_false':
                question_data['correct_answer_tf'] = question.correct_answer_tf
                
            # Short answer and Numerical - use expected_answer_text for both
            if question_type in ['short_answer', 'numerical'] and hasattr(question, 'expected_answer_text'):
                question_data['expected_answer_text'] = question.expected_answer_text
                if hasattr(question, 'accepted_error'):
                    question_data['accepted_error'] = question.accepted_error
                if hasattr(question, 'unit_of_measure'):
                    question_data['unit_of_measure'] = question.unit_of_measure
                # Include student's submitted answer if available
                if stored_text_answers:
                    str_key = str(question.id)
                    if str_key in stored_text_answers:
                        question_data['student_answer'] = stored_text_answers[str_key]
                    
            # Matching specific
            if question_type == 'matching' and hasattr(question, 'matching_pair_ids'):
                question_data['matching_pairs'] = [{
                    'id': pair.id,
                    'prompt': pair.prompt,
                    'correct_match_id': pair.correct_match_id.id if pair.correct_match_id else None,
                } for pair in question.matching_pair_ids]
                
                # Get all unique response options
                options = set()
                for pair in question.matching_pair_ids:
                    if pair.correct_match_id:
                        options.add((pair.correct_match_id.id, pair.correct_match_id.response))
                question_data['matching_options'] = [
                    {'id': opt_id, 'response': opt_text} 
                    for opt_id, opt_text in options
                ]
            
            enhanced_questions.append(question_data)
        
        # Replace slide_questions with enhanced version
        values['slide_questions'] = enhanced_questions
        
        return values    
    @http.route('/slides/slide/quiz/submit', type="jsonrpc", auth="public", website=True)
    def slide_quiz_submit(self, slide_id, answer_ids, text_answers=None):
        """Override to handle short_answer, numerical, and other non-MCQ question types"""
        if text_answers is None:
            text_answers = {}
            
        fetch_res = self._fetch_slide(slide_id)
        if fetch_res.get('error'):
            return fetch_res
        slide = fetch_res['slide']

        if slide.user_has_completed:
            self._channel_remove_session_answers(slide.channel_id, slide)
            return {'error': 'slide_quiz_done'}

        all_questions = request.env['slide.question'].sudo().search([('slide_id', '=', slide.id)])
        
        # Get questions that require answer_ids (MCQ types) - ONLY validate these
        mcq_questions = all_questions.filtered(
            lambda q: q.question_type in ['multiple_choice_single', 'multiple_choice_multi', 'true_false', False]
        )
        
        # Validate MCQ questions were answered (correctness checked later)
        user_answers = request.env['slide.answer'].sudo().search([('id', 'in', answer_ids)])
        answered_question_ids = set(user_answers.mapped('question_id').ids)
        required_question_ids = set(mcq_questions.ids)
        
        # Only check if MCQ questions are answered, not correctness yet
        if answered_question_ids != required_question_ids:
            return {'error': 'slide_quiz_incomplete'}

        # Get text-based questions that also need validation
        text_questions = all_questions.filtered(
            lambda q: q.question_type in ['short_answer', 'numerical']
        )
        
        # Validate ALL text questions are answered with non-empty values
        text_answers_dict = {int(k): v for k, v in text_answers.items()}
        answered_text_question_ids = set(text_answers_dict.keys())
        required_text_question_ids = set(text_questions.ids)
        
        # Check that ALL text questions have been answered
        missing_text_questions = required_text_question_ids - answered_text_question_ids
        if missing_text_questions:
            return {'error': 'slide_quiz_incomplete'}
        
        # Check for empty text answers
        empty_answers = [qid for qid, ans in text_answers_dict.items() if not str(ans).strip()]
        if empty_answers:
            return {'error': 'slide_quiz_incomplete'}
        
        # Validate text answers against expected answers (if defined)
        text_question_correctness = {}
        for question in text_questions:
            user_answer = text_answers_dict.get(question.id, '').strip()
            expected_answer = (question.expected_answer_text or '').strip()
            
            # If expected answer is defined, validate against it (case-insensitive)
            # If not defined, accept any non-empty answer as correct
            if expected_answer:
                is_correct = user_answer.lower() == expected_answer.lower()
            else:
                is_correct = bool(user_answer)  # Just require non-empty
            
            text_question_correctness[question.id] = {
                'is_correct': is_correct,
                'comment': None
            }
        
        # Check if there are any incorrect answers (MCQ or text)
        user_bad_answers = user_answers.filtered(lambda answer: not answer.is_correct)
        text_bad_answers = [qid for qid, data in text_question_correctness.items() if not data['is_correct']]
        has_wrong_answers = bool(user_bad_answers) or bool(text_bad_answers)

        self._set_viewed_slide(slide, quiz_attempts_inc=True)
        
        # Store text answers in slide.slide.partner for future retrieval
        slide_partner = request.env['slide.slide.partner'].sudo().search([
            ('slide_id', '=', slide.id),
            ('partner_id', '=', request.env.user.partner_id.id)
        ], limit=1)
        if slide_partner:
            slide_partner.write({'quiz_text_answers': text_answers_dict})
        
        quiz_info = self._get_slide_quiz_partner_info(slide, quiz_done=True)

        rank_progress = {}
        # Only mark as completed if ALL answers (MCQ + text) are correct
        if not has_wrong_answers:
            rank_progress['previous_rank'] = self._get_rank_values(request.env.user)
            slide._action_mark_completed()
            rank_progress['new_rank'] = self._get_rank_values(request.env.user)
            rank_progress.update({
                'description': request.env.user.rank_id.description,
                'last_rank': not request.env.user._get_next_rank(),
                'level_up': rank_progress['previous_rank']['lower_bound'] != rank_progress['new_rank']['lower_bound']
            })

        self._channel_remove_session_answers(slide.channel_id, slide)
        
        # Combine MCQ and text question results
        all_answers = {
            answer.question_id.id: {
                'is_correct': answer.is_correct,
                'comment': answer.comment
            } for answer in user_answers
        }
        # Add text question results
        all_answers.update(text_question_correctness)
        
        return {
            'answers': all_answers,
            'completed': slide.user_has_completed,
            'channel_completion': slide.channel_id.completion,
            'quizKarmaWon': quiz_info['quiz_karma_won'],
            'quizKarmaGain': quiz_info['quiz_karma_gain'],
            'quizAttemptsCount': quiz_info['quiz_attempts_count'],
            'rankProgress': rank_progress,
            'text_answers': text_answers_dict,  # Return student's text answers
        }