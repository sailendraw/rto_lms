# -*- coding: utf-8 -*-
"""Assignment submission controller"""

import base64
import logging
from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AssignmentController(http.Controller):
    """Controller for assignment file upload and submission"""

    @http.route('/assignment/<int:assignment_id>/submit', type='http', auth='user',
                methods=['POST'], website=True, csrf=True)
    def assignment_submit(self, assignment_id, **post):
        """
        Handle assignment submission with file uploads.

        Args:
            assignment_id: ID of rto.assignment
            **post: Form data including uploaded files
        """
        # Allow only portal users (students)
        if not request.env.user.has_group('base.group_portal'):
            return request.render('rto_lms.assignment_error', {
                'assignment': request.env['rto.assignment'].browse(assignment_id),
                'error_message': _('Only students can submit assignments.'),
            })

        assignment = request.env['rto.assignment'].browse(assignment_id)

        if not assignment.exists():
            return request.not_found()

        # Check availability
        if not assignment.is_available:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'error_message': _('This assignment is not currently available for submission.')
            })

        if assignment.is_past_cutoff:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'error_message': _('The cut-off date has passed. Submissions are no longer accepted.')
            })

        # Get or create draft submission
        user_partner = request.env.user.partner_id

        # Block uploads if a submission is pending grading
        pending_submission = request.env['rto.assignment.submission'].search([
            ('assignment_id', '=', assignment_id),
            ('user_id', '=', user_partner.id),
            ('state', '=', 'submitted'),
        ], limit=1)
        if pending_submission:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': pending_submission,
                'error_message': _('Your submission is pending grading. You cannot upload again.'),
            })

        # Block resubmission if not allowed
        latest_non_draft = request.env['rto.assignment.submission'].search([
            ('assignment_id', '=', assignment_id),
            ('user_id', '=', user_partner.id),
            ('state', '!=', 'draft'),
        ], order='create_date desc', limit=1)
        if latest_non_draft and not assignment.allow_resubmission:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': latest_non_draft,
                'error_message': _('Resubmission is not allowed for this assignment.'),
            })

        submission = request.env['rto.assignment.submission'].search([
            ('assignment_id', '=', assignment_id),
            ('user_id', '=', user_partner.id),
            ('state', '=', 'draft'),
        ], limit=1)

        if not submission:
            if latest_non_draft:
                return request.render('rto_lms.assignment_error', {
                    'assignment': assignment,
                    'submission': latest_non_draft,
                    'error_message': _('Resubmission is not yet enabled. Please wait for your trainer.'),
                })
            # Check max attempts
            attempt_count = request.env['rto.assignment.submission'].search_count([
                ('assignment_id', '=', assignment_id),
                ('user_id', '=', user_partner.id),
            ])

            if assignment.max_attempts > 0 and attempt_count >= assignment.max_attempts:
                return request.render('rto_lms.assignment_error', {
                    'assignment': assignment,
                    'error_message': _('Maximum attempts (%d) reached.') % assignment.max_attempts,
                })

            submission = request.env['rto.assignment.submission'].sudo().create({
                'assignment_id': assignment_id,
                'user_id': user_partner.id,
            })

        # Process uploaded files
        uploaded_files = request.httprequest.files.getlist('files')

        if uploaded_files:
            for uploaded_file in uploaded_files:
                if uploaded_file.filename:
                    # Read file content
                    file_content = uploaded_file.read()
                    file_size = len(file_content)

                    # Validate file
                    validation = assignment.validate_file_upload(
                        uploaded_file.filename,
                        file_size
                    )

                    if not validation['valid']:
                        return request.render('rto_lms.assignment_error', {
                            'assignment': assignment,
                            'submission': submission,
                            'error_message': validation['error'],
                        })

                    # Create attachment
                    attachment = request.env['ir.attachment'].sudo().create({
                        'name': uploaded_file.filename,
                        'type': 'binary',
                        'datas': base64.b64encode(file_content),
                        'res_model': 'rto.assignment.submission',
                        'res_id': submission.id,
                        'mimetype': uploaded_file.content_type,
                    })

                    # Link to submission
                    submission.sudo().write({
                        'attachment_ids': [(4, attachment.id)]
                    })

        # Check file count limit
        if assignment.max_files > 0 and len(submission.attachment_ids) > assignment.max_files:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': submission,
                'error_message': _('Maximum %d files allowed. You have uploaded %d files.') % (
                    assignment.max_files, len(submission.attachment_ids)
                ),
            })

        # Submit if required
        action = post.get('action', 'save_draft')
        if action == 'submit' or (action == 'save_draft' and not assignment.require_submit_button):
            try:
                submission.action_submit()
                return request.redirect(f'/slides/slide/{assignment.slide_id.id}?message=submitted')
            except UserError as e:
                return request.render('rto_lms.assignment_error', {
                    'assignment': assignment,
                    'submission': submission,
                    'error_message': str(e),
                })
        else:
            # Draft saved
            return request.redirect(f'/slides/slide/{assignment.slide_id.id}?message=draft_saved')

    @http.route('/assignment/<int:assignment_id>/grade', type='http', auth='user',
                methods=['POST'], website=True, csrf=True)
    def assignment_grade(self, assignment_id, **post):
        """Handle trainer grading from website"""
        is_trainer = request.env.user.has_group('website_slides.group_website_slides_officer') or \
            request.env.user.has_group('website_slides.group_website_slides_manager')
        if not is_trainer:
            return request.render('rto_lms.assignment_error', {
                'assignment': request.env['rto.assignment'].browse(assignment_id),
                'error_message': _('Only trainers can grade submissions.'),
            })

        assignment = request.env['rto.assignment'].browse(assignment_id)
        if not assignment.exists():
            return request.not_found()

        submission_id = int(post.get('submission_id') or 0)
        submission = request.env['rto.assignment.submission'].sudo().browse(submission_id)
        if not submission.exists() or submission.assignment_id.id != assignment_id:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'error_message': _('Invalid submission.'),
            })

        if submission.state != 'submitted':
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': submission,
                'error_message': _('Only submitted assignments can be graded.'),
            })

        try:
            grade = float(post.get('grade') or 0)
        except (TypeError, ValueError):
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': submission,
                'error_message': _('Invalid grade value.'),
            })

        feedback = post.get('feedback') or False

        feedback_attachments = request.env['ir.attachment']
        uploaded_files = request.httprequest.files.getlist('feedback_files')
        for uploaded_file in uploaded_files:
            if uploaded_file.filename:
                file_content = uploaded_file.read()
                attachment = request.env['ir.attachment'].sudo().create({
                    'name': uploaded_file.filename,
                    'type': 'binary',
                    'datas': base64.b64encode(file_content),
                    'res_model': 'rto.assignment.submission',
                    'res_id': submission.id,
                    'mimetype': uploaded_file.content_type,
                })
                feedback_attachments |= attachment

        try:
            submission.sudo().action_grade(grade, feedback=feedback, feedback_attachments=feedback_attachments)
        except (UserError, ValidationError) as e:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': submission,
                'error_message': str(e),
            })

        return request.redirect(f'/slides/slide/{assignment.slide_id.id}?message=graded')

    @http.route('/assignment/<int:assignment_id>/reopen', type='http', auth='user',
                methods=['POST'], website=True, csrf=True)
    def assignment_reopen(self, assignment_id, **post):
        """Allow trainer to reopen a graded submission for resubmission"""
        is_trainer = request.env.user.has_group('website_slides.group_website_slides_officer') or \
            request.env.user.has_group('website_slides.group_website_slides_manager')
        if not is_trainer:
            return request.render('rto_lms.assignment_error', {
                'assignment': request.env['rto.assignment'].browse(assignment_id),
                'error_message': _('Only trainers can allow resubmission.'),
            })

        assignment = request.env['rto.assignment'].browse(assignment_id)
        if not assignment.exists():
            return request.not_found()

        submission_id = int(post.get('submission_id') or 0)
        submission = request.env['rto.assignment.submission'].sudo().browse(submission_id)
        if not submission.exists() or submission.assignment_id.id != assignment_id:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'error_message': _('Invalid submission.'),
            })

        try:
            submission.sudo().action_reopen()
        except (UserError, ValidationError) as e:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'submission': submission,
                'error_message': str(e),
            })

        return request.redirect(f'/slides/slide/{assignment.slide_id.id}?message=reopened')

    @http.route('/assignment/<int:assignment_id>/annotate', type='http', auth='user', website=True)
    def assignment_annotate(self, assignment_id, submission_id=None, attachment_id=None, **kw):
        """Render PDF annotation viewer for trainers"""
        is_trainer = request.env.user.has_group('website_slides.group_website_slides_officer') or \
            request.env.user.has_group('website_slides.group_website_slides_manager')
        if not is_trainer:
            return request.render('rto_lms.assignment_error', {
                'assignment': request.env['rto.assignment'].browse(assignment_id),
                'error_message': _('Only trainers can annotate submissions.'),
            })

        assignment = request.env['rto.assignment'].browse(assignment_id)
        if not assignment.exists():
            return request.not_found()

        submission = request.env['rto.assignment.submission'].sudo().browse(int(submission_id or 0))
        if not submission.exists() or submission.assignment_id.id != assignment_id:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'error_message': _('Invalid submission.'),
            })

        attachment = request.env['ir.attachment'].sudo().browse(int(attachment_id or 0))
        if not attachment.exists() or attachment.res_model != 'rto.assignment.submission' or attachment.res_id != submission.id:
            return request.render('rto_lms.assignment_error', {
                'assignment': assignment,
                'error_message': _('Invalid attachment.'),
            })

        file_url = f"/assignment/download/{attachment.id}"
        return request.render('rto_lms.assignment_pdf_annotate', {
            'assignment': assignment,
            'submission': submission,
            'attachment': attachment,
            'file_url': file_url,
        })

    @http.route('/assignment/download/<int:attachment_id>', type='http', auth='user')
    def download_file(self, attachment_id, **kw):
        """Download a submission file"""
        attachment = request.env['ir.attachment'].browse(attachment_id)

        if not attachment.exists():
            return request.not_found()

        # Security check - verify user has access to this attachment
        if attachment.res_model == 'rto.assignment.submission':
            submission = request.env['rto.assignment.submission'].browse(attachment.res_id)
            if not submission.exists():
                return request.not_found()

            # Check if user is the student or a trainer
            is_owner = submission.user_id == request.env.user.partner_id
            is_trainer = request.env.user.has_group('website_slides.group_website_slides_officer')

            if not (is_owner or is_trainer):
                return request.forbidden()

        # Return file
        return request.make_response(
            base64.b64decode(attachment.datas),
            headers=[
                ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{attachment.name}"'),
                ('Content-Length', len(base64.b64decode(attachment.datas))),
            ]
        )
