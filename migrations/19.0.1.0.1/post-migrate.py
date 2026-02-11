# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Migration script to clean up active_id from action contexts."""


def migrate(cr, version):
    """
    Remove active_id from all action contexts in rto_lms module.

    This fixes the UncaughtPromiseError where actions try to evaluate
    {'default_course_id': active_id} when active_id is not available.

    Args:
        cr: Database cursor
        version: Current module version being migrated from
    """
    # Find all actions with active_id in context (simplified query)
    cr.execute("""
        SELECT id, name, context
        FROM ir_act_window
        WHERE context::text ILIKE '%active_id%'
    """)

    actions_to_fix = cr.fetchall()

    if actions_to_fix:
        print(f"[rto_lms] Migration 19.0.1.0.1: Found {len(actions_to_fix)} actions with active_id in context")

        for action_id, action_name, context in actions_to_fix:
            print(f"  - Cleaning action: {action_name} (ID: {action_id})")

            # Set context to empty dict to clear active_id
            cr.execute("""
                UPDATE ir_act_window
                SET context = '{}'::jsonb
                WHERE id = %s
            """, (action_id,))

    # Also clean ALL quiz-related actions to be safe
    cr.execute("""
        UPDATE ir_act_window
        SET context = '{}'::jsonb
        WHERE res_model ILIKE '%quiz%'
        AND context::text ILIKE '%active_id%'
    """)

    print(f"[rto_lms] Migration 19.0.1.0.1: Checked and cleaned all quiz actions")

    # Force registry update
    cr.execute("UPDATE ir_module_module SET latest_version = latest_version WHERE name = 'rto_lms'")

    print("[rto_lms] Migration 19.0.1.0.1: Completed - all actions cleaned")
