# -*- coding: utf-8 -*-
"""Dedicated LMS quiz runtime with Moodle-style sequencing."""

from odoo import http, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request


class LMSQuizController(http.Controller):
    """Custom runtime for the LMS quiz experience."""

    ACTIVE_STATES = ('draft', 'in_progress', 'submitted')

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_quiz_or_404(self, quiz_id):
        quiz = request.env['lms.quiz.definition'].sudo().browse(quiz_id)
        if not quiz or not quiz.exists():
            raise http.NotFound()
        return quiz

    def _is_training_staff(self):
        user = request.env.user
        return bool(
            user.has_group('website_slides.group_website_slides_officer')
            or user.has_group('website_slides.group_website_slides_manager')
        )

    def _require_enrollment(self, quiz):
        """Check whether the current user is allowed to sit this quiz."""
        if self._is_training_staff():
            return True
        partner = request.env.user.partner_id
        if not partner:
            return False
        enrollment = request.env['slide.channel.partner'].sudo().search_count([
            ('channel_id', '=', quiz.course_id.id),
            ('partner_id', '=', partner.id),
        ])
        return bool(enrollment)

    def _get_active_attempt(self, quiz, student):
        Attempt = request.env['lms.quiz.attempt']
        return Attempt.search([
            ('quiz_id', '=', quiz.id),
            ('student_id', '=', student.id),
            ('state', 'in', self.ACTIVE_STATES),
        ], order='create_date desc', limit=1)

    def _bind_session_attempt(self, quiz_id, attempt_id):
        session_attempts = request.session.get('lms_quiz_attempts') or {}
        session_attempts[str(quiz_id)] = attempt_id
        request.session['lms_quiz_attempts'] = session_attempts
        request.session.modified = True

    def _get_session_attempt_id(self, quiz_id):
        session_attempts = request.session.get('lms_quiz_attempts') or {}
        return session_attempts.get(str(quiz_id))

    def _clear_session_attempt(self, quiz_id):
        session_attempts = request.session.get('lms_quiz_attempts') or {}
        key = str(quiz_id)
        if key in session_attempts:
            session_attempts.pop(key)
            request.session['lms_quiz_attempts'] = session_attempts
            request.session.modified = True

    def _attempt_url(self, quiz_id, sequence=None):
        url = f'/lms/quiz/{quiz_id}/attempt'
        if sequence:
            url = f'{url}?sequence={sequence}'
        return url

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @http.route('/lms/quiz/<int:quiz_id>/start', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def quiz_start(self, quiz_id, **post):
        quiz = self._get_quiz_or_404(quiz_id)
        if not self._require_enrollment(quiz):
            return request.render('rto_lms.quiz_access_denied', {'quiz': quiz, 'course': quiz.course_id})

        student = request.env.user.partner_id
        Attempt = request.env['lms.quiz.attempt']
        active_attempt = self._get_active_attempt(quiz, student)

        # Keep session attempt aligned with current state
        session_attempt_id = self._get_session_attempt_id(quiz.id)
        if active_attempt and (not session_attempt_id or session_attempt_id != active_attempt.id):
            self._bind_session_attempt(quiz.id, active_attempt.id)
        elif not active_attempt and session_attempt_id:
            self._clear_session_attempt(quiz.id)

        history_domain = [
            ('quiz_id', '=', quiz.id),
            ('student_id', '=', student.id),
            ('state', '=', 'graded'),
        ]
        attempt_history = Attempt.search(history_domain, order='graded_at desc, create_date desc', limit=10)
        total_attempts = Attempt.search_count([('quiz_id', '=', quiz.id), ('student_id', '=', student.id)])
        attempts_remaining = None
        if quiz.max_attempts:
            attempts_remaining = max(0, quiz.max_attempts - total_attempts)
        error = None

        if request.httprequest.method == 'POST':
            action = post.get('action') or 'start'
            if action == 'resume' and active_attempt:
                self._bind_session_attempt(quiz.id, active_attempt.id)
                return request.redirect(self._attempt_url(quiz.id))
            if quiz.max_attempts and total_attempts >= quiz.max_attempts:
                error = _('You have reached the maximum number of attempts for this quiz.')
            elif active_attempt:
                error = _('You already have an active attempt in progress.')
            else:
                try:
                    new_attempt = Attempt.create({
                        'quiz_id': quiz.id,
                        'student_id': student.id,
                    })
                    new_attempt.action_start_attempt()
                except UserError as exc:
                    error = exc.name
                else:
                    self._bind_session_attempt(quiz.id, new_attempt.id)
                    return request.redirect(self._attempt_url(quiz.id))

        values = {
            'quiz': quiz,
            'course': quiz.course_id,
            'slide': quiz.slide_id,
            'active_attempt': active_attempt,
            'attempt_history': attempt_history,
            'attempts_remaining': attempts_remaining,
            'attempt_limit': quiz.max_attempts,
            'question_count': quiz.question_count,
            'pass_mark': quiz.pass_mark,
            'error': error,
            'can_resume': bool(active_attempt),
        }
        return request.render('rto_lms.quiz_start', values)

    @http.route('/lms/quiz/<int:quiz_id>/attempt', type='http', auth='user', website=True, methods=['GET', 'POST'])
    def quiz_attempt(self, quiz_id, **post):
        quiz = self._get_quiz_or_404(quiz_id)
        student = request.env.user.partner_id
        Attempt = request.env['lms.quiz.attempt']
        session_attempt_id = self._get_session_attempt_id(quiz.id)
        attempt = Attempt.browse(session_attempt_id) if session_attempt_id else Attempt.browse(False)
        if not attempt or not attempt.exists():
            attempt = self._get_active_attempt(quiz, student)
            if attempt:
                self._bind_session_attempt(quiz.id, attempt.id)
        if not attempt:
            return request.redirect(f'/lms/quiz/{quiz.id}/start')
        if attempt.student_id.id != student.id and not self._is_training_staff():
            raise AccessError(_('You do not have permission to view this attempt.'))
        if attempt.state == 'graded':
            self._clear_session_attempt(quiz.id)
            return request.redirect(f'/lms/quiz/{quiz.id}/result/{attempt.id}')
        if attempt.state == 'draft':
            attempt.action_start_attempt()

        error = None
        if request.httprequest.method == 'POST':
            action = post.get('action')
            try:
                if action == 'save':
                    question_id = int(post.get('question_id'))
                    selected_answer_id = post.get('selected_answer_id')
                    selected_answer_id = int(selected_answer_id) if selected_answer_id else False
                    answer_text = post.get('answer_text')
                    attempt.record_response(question_id, selected_answer_id, answer_text)
                    payload_after = attempt.get_runtime_payload(current_sequence=int(post.get('sequence') or 0))
                    next_sequence = payload_after['next_sequence'] or int(post.get('sequence') or 0)
                    return request.redirect(self._attempt_url(quiz.id, next_sequence))
                if action == 'submit':
                    attempt.action_submit_attempt()
                    self._clear_session_attempt(quiz.id)
                    return request.redirect(f'/lms/quiz/{quiz.id}/result/{attempt.id}')
            except UserError as exc:
                error = exc.name

        sequence_param = request.params.get('sequence') or post.get('sequence')
        current_sequence = int(sequence_param) if sequence_param else 0
        payload = attempt.get_runtime_payload(current_sequence=current_sequence)
        questions = payload['questions']
        current_question = None
        if questions:
            target_sequence = current_sequence or payload['next_sequence'] or questions[0]['sequence']
            current_question = next((q for q in questions if q['sequence'] == target_sequence), questions[0])
            if not current_question['is_unlocked']:
                unlocked = [q for q in questions if q['is_unlocked']]
                current_question = unlocked[0] if unlocked else current_question

        nav_items = [
            {
                'sequence': q['sequence'],
                'label': _('#%s') % q['sequence'],
                'is_unlocked': q['is_unlocked'],
                'has_response': q['has_response'],
                'is_active': current_question and q['sequence'] == current_question['sequence'],
            }
            for q in questions
        ]
        can_submit = bool(
            attempt.state == 'in_progress'
            and payload['progress']['total']
            and payload['progress']['answered'] == payload['progress']['total']
        )
        values = {
            'quiz': quiz,
            'attempt': attempt,
            'current_question': current_question,
            'nav_items': nav_items,
            'progress': payload['progress'],
            'can_submit': can_submit,
            'error': error,
        }
        return request.render('rto_lms.quiz_attempt', values)

    @http.route('/lms/quiz/<int:quiz_id>/result/<int:attempt_id>', type='http', auth='user', website=True)
    def quiz_result(self, quiz_id, attempt_id, **kwargs):
        quiz = self._get_quiz_or_404(quiz_id)
        Attempt = request.env['lms.quiz.attempt']
        attempt = Attempt.browse(attempt_id)
        if not attempt or not attempt.exists() or attempt.quiz_id.id != quiz.id:
            raise http.NotFound()
        student = request.env.user.partner_id
        if attempt.student_id.id != student.id and not self._is_training_staff():
            raise AccessError(_('You do not have permission to view this result.'))
        if attempt.state in ('draft', 'in_progress'):
            self._bind_session_attempt(quiz.id, attempt.id)
            return request.redirect(self._attempt_url(quiz.id))
        self._clear_session_attempt(quiz.id)

        answer_rows = []
        for answer in attempt.answer_ids.sorted(key=lambda ans: ans.sequence):
            response_summary = answer.selected_answer_id.answer_html if answer.selected_answer_id else answer.answer_text
            answer_rows.append({
                'sequence': answer.sequence,
                'title': answer.question_id.name,
                'question_type': answer.question_type,
                'response': response_summary,
                'auto_score': answer.auto_score,
                'manual_score': answer.manual_score,
                'total_score': answer.total_score,
                'is_correct': answer.is_correct,
            })

        AttemptModel = request.env['lms.quiz.attempt']
        total_attempts = AttemptModel.search_count([('quiz_id', '=', quiz.id), ('student_id', '=', attempt.student_id.id)])
        attempts_remaining = None
        if quiz.max_attempts:
            attempts_remaining = max(0, quiz.max_attempts - total_attempts)
        can_retry = bool(
            attempt.student_id.id == student.id
            and (not quiz.max_attempts or total_attempts < quiz.max_attempts)
        )

        values = {
            'quiz': quiz,
            'attempt': attempt,
            'answer_rows': answer_rows,
            'attempts_remaining': attempts_remaining,
            'can_retry': can_retry,
            'manual_pending': attempt.state != 'graded' and attempt.requires_manual_grading,
        }
        return request.render('rto_lms.quiz_result', values)
