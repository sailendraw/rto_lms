# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""
RTO Evidence Log - Immutable Audit Trail
========================================

This model provides an append-only, immutable evidence trail for all
assessment and training activities.

ASQA COMPLIANCE:
    Standard 2.2:
    - Evidence gathered is valid, sufficient, authentic, current
    - Assessment judgements are documented

    Standard 3.2:
    - Trainers and assessors have current vocational competencies

DESIGN PRINCIPLES:
    1. APPEND-ONLY: Records can only be created, never modified or deleted
    2. TIMESTAMPED: All records have precise creation timestamps
    3. VERSIONED: Superseding records create new versions, not updates
    4. AUDIT TRACEABLE: Full chain of custody for all evidence

EVIDENCE TYPES:
    - submission: Student work submission
    - attachment: Document/file evidence
    - observation: Trainer observation notes
    - third_party: Third party verification
    - outcome: Assessment outcome recording
    - signature: Digital signature/acknowledgment
    - system: System-generated audit entries

IMMUTABILITY:
    - No write() method (raises error)
    - No unlink() method (raises error)
    - Supersede only via supersede() method which creates new record
"""

import hashlib
import json
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RtoEvidenceLog(models.Model):
    """
    Immutable evidence log for RTO compliance.

    Every assessment activity, outcome, and evidence item is logged here
    with full audit trail.
    """
    _name = 'rto.evidence.log'
    _description = 'RTO Evidence Log'
    _order = 'create_date desc, id desc'
    _rec_name = 'display_name'

    # =========================================================================
    # IMMUTABILITY - Disable modification/deletion
    # =========================================================================
    # These constraints are enforced via Python overrides below

    # =========================================================================
    # IDENTIFICATION
    # =========================================================================
    display_name = fields.Char(
        string='Reference',
        compute='_compute_display_name',
        store=True,
    )
    evidence_reference = fields.Char(
        string='Evidence Reference',
        compute='_compute_evidence_reference',
        store=True,
        index=True,
        help='Unique reference for this evidence record.',
    )

    # =========================================================================
    # RELATIONSHIPS
    # =========================================================================
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    course_id = fields.Many2one(
        comodel_name='slide.channel',
        string='Course',
        required=True,
        index=True,
        ondelete='restrict',
        help='The unit delivery course this evidence relates to.',
    )
    activity_id = fields.Many2one(
        comodel_name='slide.slide',
        string='Activity',
        index=True,
        ondelete='restrict',
        help='The specific activity (assessment, observation, etc.).',
    )
    student_id = fields.Many2one(
        comodel_name='res.partner',
        string='Student',
        required=True,
        index=True,
        ondelete='restrict',
        help='The student this evidence relates to.',
    )

    # =========================================================================
    # EVIDENCE CLASSIFICATION
    # =========================================================================
    evidence_type = fields.Selection(
        selection=[
            ('submission', 'Student Submission'),
            ('attachment', 'Document/File Evidence'),
            ('observation', 'Trainer Observation'),
            ('third_party', 'Third Party Verification'),
            ('outcome', 'Assessment Outcome'),
            ('signature', 'Digital Signature'),
            ('rpl', 'RPL Evidence'),
            ('ct', 'Credit Transfer Evidence'),
            ('system', 'System Audit Entry'),
        ],
        string='Evidence Type',
        required=True,
        index=True,
        help='Classification of the evidence record.',
    )

    # =========================================================================
    # TIMESTAMPS (Immutable)
    # =========================================================================
    create_date = fields.Datetime(
        string='Created On',
        readonly=True,
        index=True,
    )
    create_uid = fields.Many2one(
        comodel_name='res.users',
        string='Created By',
        readonly=True,
    )

    # =========================================================================
    # EVIDENCE DATA
    # =========================================================================
    summary = fields.Char(
        string='Summary',
        required=True,
        help='Brief description of the evidence.',
    )
    evidence_data = fields.Text(
        string='Evidence Data (JSON)',
        help='Structured evidence data in JSON format.',
    )
    evidence_text = fields.Text(
        string='Evidence Notes',
        help='Free-text evidence notes or observations.',
    )

    # =========================================================================
    # ATTACHMENTS
    # =========================================================================
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='rto_evidence_log_attachment_rel',
        column1='evidence_log_id',
        column2='attachment_id',
        string='Attachments',
        help='File attachments as evidence.',
    )
    attachment_count = fields.Integer(
        string='Attachment Count',
        compute='_compute_attachment_count',
    )

    # =========================================================================
    # INTEGRITY
    # =========================================================================
    content_hash = fields.Char(
        string='Content Hash',
        size=64,
        readonly=True,
        help='SHA-256 hash of evidence content for integrity verification.',
    )
    is_verified = fields.Boolean(
        string='Hash Verified',
        compute='_compute_is_verified',
        help='Whether the content hash matches current data.',
    )

    # =========================================================================
    # VERSIONING
    # =========================================================================
    version = fields.Integer(
        string='Version',
        default=1,
        readonly=True,
        help='Version number. Starts at 1, increments on supersede.',
    )
    supersedes_id = fields.Many2one(
        comodel_name='rto.evidence.log',
        string='Supersedes',
        readonly=True,
        ondelete='restrict',
        help='Previous version that this record supersedes.',
    )
    superseded_by_id = fields.Many2one(
        comodel_name='rto.evidence.log',
        string='Superseded By',
        readonly=True,
        ondelete='restrict',
        help='Newer version that supersedes this record.',
    )
    is_current = fields.Boolean(
        string='Is Current Version',
        default=True,
        readonly=True,
        index=True,
        help='Whether this is the current (non-superseded) version.',
    )

    # =========================================================================
    # ACTOR TRACKING
    # =========================================================================
    actor_type = fields.Selection(
        selection=[
            ('student', 'Student'),
            ('trainer', 'Trainer'),
            ('assessor', 'Assessor'),
            ('system', 'System'),
            ('third_party', 'Third Party'),
        ],
        string='Actor Type',
        required=True,
        default='system',
        help='Who created this evidence record.',
    )
    actor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Actor',
        help='The person who created/submitted this evidence.',
    )
    actor_name = fields.Char(
        string='Actor Name (Snapshot)',
        help='Snapshot of actor name at time of recording.',
    )
    actor_email = fields.Char(
        string='Actor Email (Snapshot)',
        help='Snapshot of actor email at time of recording.',
    )

    # =========================================================================
    # IP & SESSION TRACKING (for audit)
    # =========================================================================
    ip_address = fields.Char(
        string='IP Address',
        size=45,
        readonly=True,
        help='IP address from which the evidence was submitted.',
    )
    user_agent = fields.Char(
        string='User Agent',
        readonly=True,
        help='Browser/client user agent string.',
    )

    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================

    @api.depends('evidence_type', 'create_date', 'student_id')
    def _compute_display_name(self):
        for record in self:
            if record.evidence_reference:
                record.display_name = f"{record.evidence_reference} - {record.summary or 'Evidence'}"
            else:
                record.display_name = record.summary or 'New Evidence'

    @api.depends('company_id', 'create_date')
    def _compute_evidence_reference(self):
        """Generate unique evidence reference."""
        for record in self:
            if record.id and record.create_date:
                date_str = record.create_date.strftime('%Y%m%d')
                record.evidence_reference = f"EV-{date_str}-{record.id:06d}"
            else:
                record.evidence_reference = False

    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    @api.depends('content_hash', 'summary', 'evidence_data', 'evidence_text')
    def _compute_is_verified(self):
        """Verify content hash matches current data."""
        for record in self:
            if record.content_hash:
                current_hash = record._compute_content_hash()
                record.is_verified = (record.content_hash == current_hash)
            else:
                record.is_verified = False

    # =========================================================================
    # HASH COMPUTATION
    # =========================================================================

    def _compute_content_hash(self):
        """Compute SHA-256 hash of evidence content."""
        self.ensure_one()
        content = {
            'summary': self.summary or '',
            'evidence_data': self.evidence_data or '',
            'evidence_text': self.evidence_text or '',
            'student_id': self.student_id.id,
            'activity_id': self.activity_id.id if self.activity_id else None,
            'course_id': self.course_id.id,
            'evidence_type': self.evidence_type,
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    # =========================================================================
    # IMMUTABILITY ENFORCEMENT
    # =========================================================================

    def write(self, vals):
        """
        BLOCKED: Evidence records are immutable.

        Only the superseded_by_id field can be updated (when creating
        a new version).
        """
        allowed_fields = {'superseded_by_id', 'is_current'}
        if not set(vals.keys()).issubset(allowed_fields):
            raise UserError(_(
                'Evidence records are immutable and cannot be modified. '
                'Use the supersede() method to create a new version instead.'
            ))
        return super().write(vals)

    def unlink(self):
        """BLOCKED: Evidence records cannot be deleted."""
        raise UserError(_(
            'Evidence records are immutable and cannot be deleted. '
            'They form a permanent audit trail for compliance purposes.'
        ))

    # =========================================================================
    # CRUD OVERRIDES
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set immutable fields and compute hash."""
        for vals in vals_list:
            # Capture actor snapshot
            if vals.get('actor_id'):
                actor = self.env['res.partner'].browse(vals['actor_id'])
                vals['actor_name'] = actor.name
                vals['actor_email'] = actor.email

            # Try to capture IP address from request context
            try:
                from odoo.http import request
                if request:
                    vals['ip_address'] = request.httprequest.remote_addr
                    vals['user_agent'] = request.httprequest.user_agent.string[:255] if request.httprequest.user_agent else None
            except Exception:
                pass

        records = super().create(vals_list)

        # Compute content hash after creation
        for record in records:
            # Use SQL to bypass write() restriction for initial hash
            content_hash = record._compute_content_hash()
            self.env.cr.execute(
                "UPDATE rto_evidence_log SET content_hash = %s WHERE id = %s",
                (content_hash, record.id)
            )

        return records

    # =========================================================================
    # VERSIONING METHODS
    # =========================================================================

    def supersede(self, new_summary=None, new_evidence_data=None, new_evidence_text=None, reason=None):
        """
        Create a new version that supersedes this record.

        This is the ONLY way to "update" an evidence record - by creating
        a new version that references the old one.

        Args:
            new_summary: New summary (optional, copies from original if not provided)
            new_evidence_data: New evidence data (optional)
            new_evidence_text: New evidence text (optional)
            reason: Reason for superseding (required)

        Returns:
            The new evidence record
        """
        self.ensure_one()

        if not reason:
            raise UserError(_(
                'A reason must be provided when superseding an evidence record.'
            ))

        if not self.is_current:
            raise UserError(_(
                'Cannot supersede a record that has already been superseded. '
                'Supersede the current version instead.'
            ))

        # Create new version
        new_record = self.create({
            'company_id': self.company_id.id,
            'course_id': self.course_id.id,
            'activity_id': self.activity_id.id if self.activity_id else False,
            'student_id': self.student_id.id,
            'evidence_type': self.evidence_type,
            'summary': new_summary or self.summary,
            'evidence_data': new_evidence_data or self.evidence_data,
            'evidence_text': f"SUPERSEDES: {self.evidence_reference}\nREASON: {reason}\n\n{new_evidence_text or self.evidence_text or ''}",
            'actor_type': self.env.user.partner_id and 'trainer' or 'system',
            'actor_id': self.env.user.partner_id.id if self.env.user.partner_id else False,
            'version': self.version + 1,
            'supersedes_id': self.id,
        })

        # Mark old record as superseded (using SQL to bypass write restriction)
        self.env.cr.execute(
            "UPDATE rto_evidence_log SET superseded_by_id = %s, is_current = FALSE WHERE id = %s",
            (new_record.id, self.id)
        )

        return new_record

    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================

    def action_view_attachments(self):
        """Open attachments for this evidence record."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Evidence Attachments'),
            'res_model': 'ir.attachment',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.attachment_ids.ids)],
        }

    def action_view_version_history(self):
        """Open version history for this evidence chain."""
        self.ensure_one()
        # Find all versions in the chain
        version_ids = [self.id]
        current = self

        # Walk back through supersedes chain
        while current.supersedes_id:
            version_ids.append(current.supersedes_id.id)
            current = current.supersedes_id

        # Walk forward through superseded_by chain
        current = self
        while current.superseded_by_id:
            version_ids.append(current.superseded_by_id.id)
            current = current.superseded_by_id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Version History'),
            'res_model': 'rto.evidence.log',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', version_ids)],
            'context': {'search_default_group_by_version': 1},
        }

    def verify_integrity(self):
        """Verify the integrity of this evidence record."""
        self.ensure_one()
        if self.is_verified:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Integrity Verified'),
                    'message': _('The evidence record integrity is verified. Hash matches.'),
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Integrity Warning'),
                    'message': _('ALERT: The evidence record hash does not match! Data may have been tampered with.'),
                    'type': 'danger',
                    'sticky': True,
                },
            }
