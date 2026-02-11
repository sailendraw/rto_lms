# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Migration script for rto_lms version 17.0.2.0.0

This migration renames the question_type 'mcq' to 'mcq_single' for backward
compatibility with the expanded question type selection.
"""


def migrate(cr, version):
    """
    Rename 'mcq' to 'mcq_single' in both lms_quiz_question and lms_quiz_attempt_answer tables.

    Args:
        cr: Database cursor
        version: Current module version being migrated from
    """
    # Update question type in quiz questions
    cr.execute("""
        UPDATE lms_quiz_question
        SET question_type = 'mcq_single'
        WHERE question_type = 'mcq'
    """)

    # Update question type in attempt answers (stored computed field)
    cr.execute("""
        UPDATE lms_quiz_attempt_answer
        SET question_type = 'mcq_single'
        WHERE question_type = 'mcq'
    """)

    # Log the number of records updated
    cr.execute("""
        SELECT COUNT(*) FROM lms_quiz_question WHERE question_type = 'mcq_single'
    """)
    question_count = cr.fetchone()[0]

    cr.execute("""
        SELECT COUNT(*) FROM lms_quiz_attempt_answer WHERE question_type = 'mcq_single'
    """)
    answer_count = cr.fetchone()[0]

    print(f"[rto_lms] Migration 17.0.2.0.0: Renamed question_type from 'mcq' to 'mcq_single'")
    print(f"  - Questions updated: {question_count}")
    print(f"  - Attempt answers updated: {answer_count}")
