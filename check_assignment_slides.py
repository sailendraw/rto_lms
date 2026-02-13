#!/usr/bin/env python3
"""
Quick script to check assignment slides in the database.
Run with: python3 check_assignment_slides.py
"""

import os
import sys

# Add odoo to path if needed
# sys.path.insert(0, '/path/to/odoo')

print("""
To check your assignment slides in Odoo shell, run:

    odoo-bin shell -d YOUR_DATABASE_NAME

Then paste this code:
""")

print("""
# Check all assignment slides
assignment_slides = env['slide.slide'].search([('slide_category', '=', 'assignment')])
print(f"Found {len(assignment_slides)} assignment slides:")
for slide in assignment_slides:
    print(f"  ID: {slide.id}, Name: {slide.name}, Has Assignment: {bool(slide.assignment_id)}")

# Check if any slides have assignment_id but wrong category
wrong_category = env['slide.slide'].search([('assignment_id', '!=', False), ('slide_category', '!=', 'assignment')])
if wrong_category:
    print(f"\\nWARNING: {len(wrong_category)} slides have assignment_id but wrong category:")
    for slide in wrong_category:
        print(f"  ID: {slide.id}, Name: {slide.name}, Category: {slide.slide_category}")
""")

print("\n" + "="*80)
print("Or run this SQL query directly:")
print("="*80)
print("""
SELECT
    id,
    name,
    slide_category,
    assignment_id,
    channel_id
FROM slide_slide
WHERE slide_category = 'assignment'
   OR assignment_id IS NOT NULL;
""")
