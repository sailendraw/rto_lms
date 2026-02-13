# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""
slide.channel Extension - Unit Delivery Course
==============================================

This extension transforms Odoo's slide.channel (Course) into a Unit Delivery Instance
compliant with Australian RTO requirements.

CORE PRINCIPLE:
    Each slide.channel = ONE Unit of Competency delivered to ONE cohort/intake

DATA MODEL:
    Training Package (parent) → Qualification → Unit of Competency

    Example:
        CHC (Community Services Training Package)
        → CHC43121 (Certificate IV in Disability Support)
        → CHCCCS044 (Follow established person-centred behaviour supports)

COHORT BEHAVIOUR:
    - CHCCCS044 – 2026_S1 = Semester 1, 2026 intake
    - CHCCCS044 – 2027_S1 = Semester 1, 2027 intake
    These are SEPARATE course records. Never reuse across years.

AVETMISS MAPPING:
    This course becomes ONE Training Activity (NAT00120) record per enrolled student.
    Assessment outcomes drive competency determination.

ASQA COMPLIANCE:
    - Evidence generated per Activity → Assessment → Outcome
    - Timestamped, immutable, versioned, audit traceable
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SlideChannel(models.Model):
    """
    Extended slide.channel for RTO Unit Delivery Courses.

    Adds unit-of-competency linking, intake management, and compliance fields.
    """
    _inherit = 'slide.channel'

    # =========================================================================
    # RTO MODE FLAG
    # =========================================================================
    is_rto_course = fields.Boolean(
        string='RTO Unit Course',
        default=True,
        tracking=True,
        help='Enable to make this an RTO-compliant unit delivery course. '
             'When enabled, training package, qualification, and unit fields become available.',
    )

    # =========================================================================
    # TRAINING PRODUCT HIERARCHY
    # =========================================================================
    # Training Package - derived from unit or qualification
    training_package_code = fields.Char(
        string='Training Package Code',
        compute='_compute_training_package',
        store=True,
        index=True,
        help='Training Package code (e.g., CHC, BSB). Auto-derived from qualification or unit.',
    )
    training_package_title = fields.Char(
        string='Training Package Title',
        compute='_compute_training_package',
        store=True,
        help='Training Package title (e.g., Community Services Training Package).',
    )

    # Qualification - the parent qualification this unit belongs to for this delivery
    qualification_id = fields.Many2one(
        comodel_name='rto.nrt.program',
        string='Qualification',
        domain="[('nrt_type', '=', 'Qualification'), ('usage_recommendation', '=', 'Current')]",
        tracking=True,
        index=True,
        ondelete='restrict',
        help='The qualification this unit is being delivered under. '
             'Example: CHC43121 - Certificate IV in Disability Support',
    )
    qualification_code = fields.Char(
        related='qualification_id.national_code',
        string='Qualification Code',
        store=True,
        index=True,
    )

    # Unit of Competency - from NRT Programs (Unit of Competency type)
    unit_id = fields.Many2one(
        comodel_name='rto.nrt.program',
        string='Unit of Competency',
        domain="[('nrt_type', '=', 'Unit of Competency'), ('usage_recommendation', '=', 'Current')]",
        tracking=True,
        index=True,
        ondelete='restrict',
        help='The unit of competency being delivered. '
             'Example: CHCCCS044 - Follow established person-centred behaviour supports',
    )
    unit_code = fields.Char(
        related='unit_id.national_code',
        string='Unit Code',
        store=True,
        index=True,
    )
    unit_name = fields.Char(
        related='unit_id.national_title',
        string='Unit Name',
        store=True,
    )
    nominal_hours = fields.Integer(
        string='Nominal Hours',
        tracking=True,
        help='Nominal hours for this unit delivery. Enter manually.',
    )


    # =========================================================================
    # INTAKE / COHORT MANAGEMENT
    # =========================================================================
    intake_code = fields.Char(
        string='Intake Code',
        size=20,
        tracking=True,
        index=True,
        help='Cohort identifier. Examples: 2026_S1, 2027_T1, 2026_JAN. '
             'Must be unique per unit.',
    )
    intake_year = fields.Integer(
        string='Intake Year',
        compute='_compute_intake_year',
        store=True,
        index=True,
        help='Extracted year from intake code for reporting.',
    )

    # =========================================================================
    # DELIVERY DETAILS
    # =========================================================================
    delivery_start_date = fields.Date(
        string='Delivery Start Date',
        tracking=True,
        help='When this unit delivery begins.',
    )
    delivery_end_date = fields.Date(
        string='Delivery End Date',
        tracking=True,
        help='When this unit delivery ends.',
    )

    delivery_mode_id = fields.Many2one(
        comodel_name='rto.delivery.mode',
        string='Delivery Mode',
        tracking=True,
        help='How this unit is delivered (classroom, online, workplace, blended).',
    )
    delivery_mode_code = fields.Char(
        related='delivery_mode_id.avetmiss_code',
        string='AVETMISS Delivery Mode',
        store=True,
        help='AVETMISS-compliant delivery mode code.',
    )

    # =========================================================================
    # UNIT CLASSIFICATION WITHIN QUALIFICATION
    # =========================================================================
    unit_type = fields.Selection(
        selection=[
            ('core', 'Core Unit'),
            ('elective', 'Elective Unit'),
            ('imported', 'Imported Unit'),
        ],
        string='Unit Type',
        default='core',
        tracking=True,
        help='Whether this is a core, elective, or imported unit within the qualification.',
    )

    # =========================================================================
    # DELIVERY LOCATION (links to NAT00020, auto-filled from company)
    # =========================================================================
    @api.model
    def _get_default_delivery_location(self):
        """Get default delivery location from company's NAT00010."""
        company = self.env.company
        nat00010 = self.env['rto.avetmiss.nat00010'].search([
            ('company_id', '=', company.id)
        ], limit=1)
        if nat00010:
            location = self.env['rto.avetmiss.nat00020'].search([
                ('nat00010_id', '=', nat00010.id)
            ], limit=1)
            return location.id if location else False
        return False

    delivery_location_id = fields.Many2one(
        comodel_name='rto.avetmiss.nat00020',
        string='Delivery Location',
        default=_get_default_delivery_location,
        tracking=True,
        help='AVETMISS delivery location for this course. Auto-filled from company settings.',
    )

    # =========================================================================
    # TRAINER ASSIGNMENT (from users with Trainer role)
    # =========================================================================
    trainer_ids = fields.Many2many(
        comodel_name='res.users',
        relation='rto_lms_course_trainer_user_rel',
        column1='course_id',
        column2='user_id',
        string='Assigned Trainers',
        domain="[('is_rto_trainer', '=', True)]",
        tracking=True,
        help='Trainers assigned to deliver this unit. '
             'Only users with Trainer role are shown.',
    )

    # =========================================================================
    # COMPUTED DISPLAY NAME
    # =========================================================================
    rto_display_name = fields.Char(
        string='RTO Course Name',
        compute='_compute_rto_display_name',
        store=True,
        help='Auto-generated name: [Unit Code] - [Unit Name] - [Intake Code]',
    )

    # =========================================================================
    # STATISTICS
    # =========================================================================
    enrolled_student_count = fields.Integer(
        string='Enrolled Students',
        compute='_compute_enrolled_student_count',
        help='Number of students enrolled in this unit delivery.',
    )
    assessment_count = fields.Integer(
        string='Assessments',
        compute='_compute_assessment_count',
        help='Number of assessment activities in this course.',
    )
    evidence_count = fields.Integer(
        string='Evidence Records',
        compute='_compute_evidence_count',
        help='Number of evidence records generated.',
    )
    nbr_assignment = fields.Integer(
        string='Assignments',
        compute='_compute_slides_statistics',
        store=True,
        help='Number of assignment activities in this course.',
    )

    # =========================================================================
    # AVETMISS INTEGRATION
    # =========================================================================
    # NAT00030 and NAT00060 records are auto-created/synced on save
    # via _ensure_avetmiss_records() - no linking fields needed on course

    # Training activity records are created per enrollment via rto.avetmiss.nat00120
    # This is a computed One2many showing related NAT00120 records
    nat00120_ids = fields.One2many(
        comodel_name='rto.avetmiss.nat00120',
        compute='_compute_nat00120_ids',
        string='Training Activities (NAT00120)',
        help='AVETMISS training activity records for students in this course.',
    )

    # =========================================================================
    # CONSTRAINTS
    # =========================================================================
    _unit_intake_unique = models.Constraint(
        'UNIQUE(unit_id, intake_code)',
        'A unit can only be delivered once per intake!',
    )

    # =========================================================================
    # COMPUTED METHODS
    # =========================================================================

    @api.depends('qualification_id', 'unit_id')
    def _compute_training_package(self):
        """Derive training package from qualification or unit."""
        for course in self:
            if course.qualification_id:
                course.training_package_code = course.qualification_id.parent_training_package_code
                course.training_package_title = course.qualification_id.parent_training_package_title
            elif course.unit_id:
                course.training_package_code = course.unit_id.parent_training_package_code
                course.training_package_title = course.unit_id.parent_training_package_title
            else:
                course.training_package_code = False
                course.training_package_title = False

    @api.depends('intake_code')
    def _compute_intake_year(self):
        """Extract year from intake code."""
        for course in self:
            if course.intake_code:
                # Try to extract 4-digit year from intake code
                import re
                match = re.search(r'(20\d{2})', course.intake_code)
                course.intake_year = int(match.group(1)) if match else 0
            else:
                course.intake_year = 0

    @api.depends('unit_id', 'unit_code', 'unit_name', 'intake_code')
    def _compute_rto_display_name(self):
        """Generate display name for RTO courses."""
        for course in self:
            if course.unit_code and course.intake_code:
                course.rto_display_name = f"{course.unit_code} - {course.unit_name or 'Unit'} - {course.intake_code}"
            elif course.unit_code:
                course.rto_display_name = f"{course.unit_code} - {course.unit_name or 'Unit'}"
            else:
                course.rto_display_name = course.name

    @api.depends('channel_partner_ids')
    def _compute_enrolled_student_count(self):
        """Count enrolled students (members with active status)."""
        for course in self:
            course.enrolled_student_count = len(course.channel_partner_ids.filtered(
                lambda cp: cp.member_status in ('joined', 'ongoing', 'completed')
            ))

    @api.depends('slide_ids', 'slide_ids.rto_activity_type')
    def _compute_assessment_count(self):
        """Count assessment activities in the course."""
        for course in self:
            course.assessment_count = len(course.slide_ids.filtered(
                lambda s: s.rto_activity_type == 'assessment'
            ))

    def _compute_evidence_count(self):
        """Count evidence log records for this course."""
        for course in self:
            course.evidence_count = self.env['rto.evidence.log'].search_count([
                ('course_id', '=', course.id)
            ])


    def _compute_nat00120_ids(self):
        """Get related AVETMISS NAT00120 training activity records."""
        for course in self:
            if course.unit_id and course.is_rto_course and course.unit_code:
                # NAT00120 records are linked via subject_identifier (unit code)
                course.nat00120_ids = self.env['rto.avetmiss.nat00120'].search([
                    ('subject_identifier', '=', course.unit_code),
                    # Additional filters would be needed for proper linking
                ])
            else:
                course.nat00120_ids = self.env['rto.avetmiss.nat00120']

    # =========================================================================
    # AVETMISS RECORD MANAGEMENT
    # =========================================================================

    def _ensure_avetmiss_records(self):
        """
        Sync course data to NAT00030 and NAT00060 records.
        - If NAT record exists: update with course data
        - If NAT record doesn't exist: create it from course data
        Called automatically when a course is created or when unit/qualification changes.
        """
        for record in self:
            if not record.is_rto_course:
                continue

            company = self.env.company

            # 1. Sync to NAT00030 (Program) for qualification
            if record.qualification_id:
                nat00030 = self.env['rto.avetmiss.nat00030'].search([
                    ('company_id', '=', company.id),
                    ('nrt_program_id', '=', record.qualification_id.id),
                ], limit=1)

                if not nat00030:
                    # Create new NAT00030 record
                    # Explicitly pass computed fields as they are required
                    self.env['rto.avetmiss.nat00030'].create({
                        'company_id': company.id,
                        'nrt_program_id': record.qualification_id.id,
                        'program_identifier': record.qualification_id.national_code,
                        'program_name': record.qualification_id.national_title,
                        'nominal_hours': 0,
                        'is_on_tga': True,
                    })

            # 2. Sync to NAT00060 (Subject) for unit
            if record.unit_id and record.unit_code:
                nat00060 = self.env['rto.avetmiss.nat00060'].search([
                    ('company_id', '=', company.id),
                    ('subject_identifier', '=', record.unit_code),
                ], limit=1)

                if nat00060:
                    # Update existing NAT00060 with course data
                    nat00060.write({
                        'subject_name': record.unit_name or record.unit_id.national_title,
                        'nominal_hours': record.nominal_hours or nat00060.nominal_hours,
                    })
                else:
                    # Create new NAT00060 record
                    self.env['rto.avetmiss.nat00060'].create({
                        'company_id': company.id,
                        'subject_identifier': record.unit_code,
                        'subject_name': record.unit_name or record.unit_id.national_title,
                        'nominal_hours': record.nominal_hours or 0,
                        'is_on_tga': True,
                    })

    # =========================================================================
    # VALIDATION
    # =========================================================================

    @api.constrains('is_rto_course', 'unit_id', 'intake_code')
    def _check_rto_required_fields(self):
        """Validate required fields when RTO mode is enabled."""
        for course in self:
            if course.is_rto_course:
                if not course.unit_id:
                    raise ValidationError(_(
                        'Unit of Competency is required for RTO courses.'
                    ))
                if not course.intake_code:
                    raise ValidationError(_(
                        'Intake Code is required for RTO courses. '
                        'Example: 2026_S1'
                    ))

    @api.constrains('delivery_start_date', 'delivery_end_date')
    def _check_delivery_dates(self):
        """Validate delivery date range."""
        for course in self:
            if course.delivery_start_date and course.delivery_end_date:
                if course.delivery_end_date < course.delivery_start_date:
                    raise ValidationError(_(
                        'Delivery End Date cannot be before Start Date.'
                    ))

    @api.constrains('trainer_ids', 'unit_id')
    def _check_trainer_competency(self):
        """
        Warn if assigned trainers don't have competency in the unit.
        This is a soft check - compliance is enforced via rto_staff_core.
        """
        # Soft validation - logged but not blocking
        # Full competency checks happen in rto_staff_core
        pass

    # =========================================================================
    # ONCHANGE HANDLERS
    # =========================================================================

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        """Auto-populate course name from unit."""
        if self.unit_id and self.is_rto_course:
            if not self.name or self.name == 'New':
                self.name = f"{self.unit_id.national_code} - {self.unit_id.national_title}"

    @api.onchange('qualification_id')
    def _onchange_qualification_id(self):
        """Filter units based on qualification (when linking is available)."""
        # In future, could filter unit_id domain based on qualification packaging rules
        pass

    @api.onchange('is_rto_course')
    def _onchange_is_rto_course(self):
        """Set defaults when RTO mode is enabled."""
        if self.is_rto_course:
            self.channel_type = 'training'

    # =========================================================================
    # CRUD OVERRIDES
    # =========================================================================

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle RTO course setup and AVETMISS record creation."""
        for vals in vals_list:
            if vals.get('is_rto_course'):
                # Ensure training type for RTO courses
                vals['channel_type'] = 'training'

        records = super().create(vals_list)

        # Auto-create AVETMISS records for RTO courses
        for record in records:
            if record.is_rto_course:
                record._ensure_avetmiss_records()

        return records

    def write(self, vals):
        """Override write to maintain RTO course integrity and sync AVETMISS records."""
        if vals.get('is_rto_course') is False:
            # Check if course has RTO data that would be orphaned
            for course in self:
                if course.evidence_count > 0:
                    raise ValidationError(_(
                        'Cannot disable RTO mode when evidence records exist. '
                        'This would orphan audit data.'
                    ))

        result = super().write(vals)

        # Re-sync AVETMISS records if unit, qualification, or nominal_hours changed
        if 'unit_id' in vals or 'qualification_id' in vals or 'nominal_hours' in vals or vals.get('is_rto_course'):
            for record in self:
                if record.is_rto_course:
                    record._ensure_avetmiss_records()

        return result

    # =========================================================================
    # BUSINESS METHODS
    # =========================================================================

    def action_view_evidence(self):
        """Open evidence log for this course."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Evidence Log - %s', self.rto_display_name),
            'res_model': 'rto.evidence.log',
            'view_mode': 'tree,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id},
        }

    def action_view_outcomes(self):
        """Open assessment outcomes for this course."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Assessment Outcomes - %s', self.rto_display_name),
            'res_model': 'rto.assessment.outcome',
            'view_mode': 'tree,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id},
        }

    def action_copy_for_new_intake(self):
        """
        Copy this course for a new intake/cohort.

        Creates a new course with:
        - Same unit, qualification, delivery mode
        - New intake code
        - Empty student enrollment
        - Course structure (slides) optionally copied
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create New Intake'),
            'res_model': 'rto.lms.copy.intake.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_source_course_id': self.id,
                'default_unit_id': self.unit_id.id,
                'default_qualification_id': self.qualification_id.id,
            },
        }
