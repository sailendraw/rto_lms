# MASTER AGENT PROMPT
## Build Moodle-like Quiz System for Odoo 19 LMS (Separate Runtime Page)

---

## CONTEXT (MANDATORY)

You are extending **Odoo 19 eLearning (website_slides)**.

Facts (must be respected):
- Odoo 19 already provides course management and basic quizzes.
- Odoo 19 quizzes support auto-graded question types and simple retry/pass logic.
- Odoo 19 DOES NOT provide:
  - Reusable question bank
  - Manual grading workflow
  - Dedicated quiz runtime page
  - Attempt-level audit trail
  - Conditional / dependent questions

You must **extend**, not replace, Odoo core.

You must:
- NOT modify core Odoo models directly
- NOT fork or override `website_slides`
- Use new models + inheritance only
- Remain fully compatible with Odoo 19 upgrades

---

## OBJECTIVE (LOCKED SCOPE)

Implement a **Moodle-like quiz system** inside Odoo 19 with the following capabilities:

### INCLUDED (MUST IMPLEMENT)
- Reusable Question Bank
- Multiple question types:
  - Multiple Choice (MCQ)
  - True / False
  - Short Answer (manual grading)
- Randomized question selection per attempt
- Attempt limits
- Pass marks
- Manual grading for subjective answers
- Attempt history per learner
- Dedicated quiz runtime page (custom URL, custom UI)
- Conditional / dependent questions (question sequencing & answer-based dependencies)

### EXCLUDED (DO NOT IMPLEMENT)
- Assignments
- Course gradebook / aggregation
- SCORM
- LTI
- AI grading
- Rubrics
- Mobile offline support

---

## ARCHITECTURAL PRINCIPLES (NON-NEGOTIABLE)

1. Separate concerns strictly:
   - Quiz authoring → backend (Odoo admin)
   - Quiz runtime (attempt) → custom frontend page
   - Quiz grading → backend dashboard

2. Dedicated runtime URLs only (no default Odoo quiz UI).

3. Audit-safe design:
   - Questions locked at attempt start
   - Attempts immutable after submission
   - Grading actions logged

4. Dependency logic is **assessment logic**, not UI-only logic.

---

## MODULE STRUCTURE (MUST FOLLOW EXACTLY)

Module name:
```
rto_lms_quiz
```

Folder structure:
```
rto_lms_quiz/
├── __manifest__.py
├── models/
│   ├── quiz_question.py
│   ├── quiz_question_answer.py
│   ├── quiz_definition.py
│   ├── quiz_attempt.py
│   └── quiz_attempt_answer.py
├── controllers/
│   └── quiz_controller.py
├── views/
│   ├── quiz_authoring_views.xml
│   ├── quiz_runtime_templates.xml
│   └── quiz_grading_views.xml
├── security/
│   ├── security.xml
│   └── ir.model.access.csv
```

---

## TASK 1: REUSABLE QUESTION BANK

Model: `lms.quiz.question`

Fields:
- course_id (Many2one → slide.channel)
- question_type (mcq, tf, short)
- question_html (Html)
- max_score (Float)
- active (Boolean)

Rules:
- Questions reusable across multiple quizzes
- Short answer questions require manual grading

---

## TASK 2: QUESTION ANSWERS

Model: `lms.quiz.question.answer`

Fields:
- question_id (Many2one → lms.quiz.question)
- answer_html (Html)
- is_correct (Boolean)
- score (Float)

Rules:
- MCQ / TF auto-graded
- Short answer has no predefined correct answer

---

## TASK 3: QUIZ DEFINITION (ATTACHED TO SLIDE)

Model: `lms.quiz.definition`

Fields:
- slide_id (Many2one → slide.slide, domain quiz)
- course_id (related to slide.channel)
- question_ids (Many2many → lms.quiz.question)
- randomize (Boolean)
- question_limit (Integer)
- pass_mark (Float, percentage)
- max_attempts (Integer)

Rules:
- Extends Odoo quiz configuration
- No duplication of core quiz logic

---

## TASK 4: QUESTION DEPENDENCIES (CRITICAL)

Extend `lms.quiz.question` with:

- depends_on_question_id (Many2one → lms.quiz.question)
- depends_on_answer_ids (Many2many → lms.quiz.question.answer)
- dependency_type:
  - sequence (must answer previous question)
  - answer_value (only shown if answer matches)

Rules:
- No circular dependencies
- No self-dependency
- Dependency must exist within same quiz
- Validated at quiz save time

---

## TASK 5: QUIZ ATTEMPT (AUDIT-SAFE)

Model: `lms.quiz.attempt`

Fields:
- quiz_id (Many2one → lms.quiz.definition)
- student_id (Many2one → res.partner)
- attempt_no (Integer)
- started_at (Datetime)
- submitted_at (Datetime)
- auto_score (Float)
- manual_score (Float)
- total_score (Float)
- requires_manual_grading (Boolean)
- graded (Boolean)

Rules:
- Attempt number increments per learner
- Attempts immutable after submission

---

## TASK 6: ATTEMPT ANSWERS

Model: `lms.quiz.attempt.answer`

Fields:
- attempt_id (Many2one → lms.quiz.attempt)
- question_id (Many2one → lms.quiz.question)
- selected_answer_id (Many2one → lms.quiz.question.answer)
- answer_text (Html)
- auto_score (Float)
- manual_score (Float)

Rules:
- One record per question per attempt
- Stored at submission time

---

## TASK 7: QUESTION SELECTION & LOCKING

At attempt creation:
1. Select question pool
2. Apply randomization
3. Apply question limit
4. Preserve dependency order
5. Lock final ordered question list

Rules:
- Dependencies must not be broken by randomization
- Locked questions must never change

---

## TASK 8: FRONTEND RUNTIME ROUTES (MANDATORY)

Routes:
```
/lms/quiz/<quiz_id>/start
/lms/quiz/<quiz_id>/attempt
/lms/quiz/<quiz_id>/result/<attempt_id>
```

Rules:
- auth = user
- Course enrollment required
- One active attempt at a time

---

## TASK 9: RUNTIME UI (CUSTOM QWEB PAGE)

Requirements:
- Custom QWeb templates
- Render questions sequentially
- Hide or disable dependent questions until unlocked
- No reliance on Odoo quiz JS
- Server-side validation only

---

## TASK 10: SUBMISSION & AUTO-GRADING

On submit:
- Save all answers
- Auto-grade MCQ / TF
- Flag manual grading if short answers exist
- Enforce dependency validation
- Reject submission if dependencies unmet

Rules:
- Grades must be stored, not inferred

---

## TASK 11: RESULT PAGE (STUDENT)

Show:
- Auto score (if applicable)
- Pending grading notice
- Final score only after approval
- Pass/fail status

---

## TASK 12: MANUAL GRADING DASHBOARD

Backend view:
- List attempts needing grading
- Show dependency chain
- Inline scoring & feedback
- Finalize grading (locks attempt)

Rules:
- Trainers only
- No silent overrides

---

## TASK 13: SECURITY & ACL

Roles:
- Student: attempt quiz, view own attempts
- Trainer: manage questions, grade attempts
- Admin: full access

Rules:
- Enforce enrollment
- Enforce record rules

---

## TASK 14: AUDIT & TRACEABILITY

Mandatory:
- mail.thread on attempts
- Timestamp all actions
- Log grading changes
- Store dependency evaluation per attempt

---

## HARD CONSTRAINTS (DO NOT VIOLATE)

- Do NOT modify slide.slide
- Do NOT override Odoo quiz controllers
- Do NOT rely on client-side enforcement
- Do NOT guess requirements

If a requirement is unclear, STOP and COMMENT.

---

## ACCEPTANCE CRITERIA

The implementation is valid ONLY IF:
- Question dependencies work with randomization on/off
- Learners cannot bypass sequencing
- Attempts are auditable and reproducible
- Behaviour matches Moodle dependency semantics
- Fully compatible with Odoo 19

---

END OF PROMPT