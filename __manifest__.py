# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.
{
    'name': 'RTO LMS - Unit Delivery Courses',
    'version': '19.0.1.0.1',
    'category': 'Website/eLearning',
    'summary': 'ASQA/AVETMISS compliant LMS for Australian RTOs',
    'description': """
RTO LMS - Unit Delivery Course Management
==========================================

Extends Odoo eLearning (website_slides) into a compliance-grade LMS
for Australian Registered Training Organisations.

Core Principle:
- Each Odoo Course (slide.channel) = ONE Unit of Competency delivered to ONE cohort/intake
- A course is NOT a whole qualification
- Same unit creates new course each year for new students
- Old cohorts are never overwritten or reused

Key Features:
- Unit-based course structure (training_package → qualification → unit)
- Intake/cohort management (2026_S1, 2027_S1, etc.)
- Delivery mode tracking (classroom, online, workplace, blended)
- Core/elective unit designation per qualification
- Activity extensions for assessments, evidence uploads
- Immutable evidence logging (ASQA Standard 2.2)
- Assessment outcomes mapping to AVETMISS NAT00120

Compliance:
- ASQA Standards for RTOs 2015
- AVETMISS VET Provider Collection Release 8.0

Dependencies:
- website_slides (Odoo core LMS)
- rto_avetmiss_core (AVETMISS engine)
- rto_staff_core (trainer competency)
    """,
    'author': 'RTO Solutions',
    'website': 'https://www.rtosolutions.com.au',
    'license': 'LGPL-3',
    'depends': [
        'website_slides',
        'rto_avetmiss_core',
        'rto_staff_core',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'security/lms_quiz_security.xml',
        # Data
        'data/rto_quiz_sequence.xml',
        'data/rto_delivery_mode_data.xml',
        # Views
        'views/slide_channel_views.xml',
        'views/slide_slide_views.xml',
        'views/slide_question_views.xml',
        'views/rto_evidence_log_views.xml',
        'views/rto_assessment_outcome_views.xml',
        'views/lms_quiz_views.xml',
        'views/rto_lms_menus.xml',
        # Website / Runtime templates
        'views/portal_quiz_templates.xml',
        'views/website_slides_quiz_templates.xml',
        'views/rto_quiz_question_form_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'rto_lms/static/src/js/rto_quiz_question_form.js',
            'rto_lms/static/src/js/slides_course_quiz_patch.js',
            'rto_lms/static/src/xml/slide_quiz_override.xml',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 4,
}
