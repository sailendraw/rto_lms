# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Unit tests for quiz grading algorithms."""

import json
from odoo.tests.common import TransactionCase


class TestQuizGrading(TransactionCase):
    """Test auto-grading for all question types."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test course (not RTO mode for simple testing)
        cls.course = cls.env['slide.channel'].create({
            'name': 'Test Course',
            'is_rto_course': False,
        })

        # Create test user
        cls.student = cls.env['res.partner'].create({
            'name': 'Test Student',
            'email': 'student@test.com',
        })

    def test_01_grade_mcq_single_correct(self):
        """Test MCQ Single grading - correct answer."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Single',
            'course_id': self.course.id,
            'question_type': 'mcq_single',
            'question_html': '<p>What is 2+2?</p>',
            'max_score': 10.0,
        })

        correct_answer = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })

        wrong_answer = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>5</p>',
            'is_correct': False,
        })

        # Create attempt answer
        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'selected_answer_id': correct_answer.id,
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 10.0)
        self.assertTrue(attempt_answer.is_correct)

    def test_02_grade_mcq_single_incorrect(self):
        """Test MCQ Single grading - incorrect answer."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Single',
            'course_id': self.course.id,
            'question_type': 'mcq_single',
            'question_html': '<p>What is 2+2?</p>',
            'max_score': 10.0,
        })

        correct_answer = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })

        wrong_answer = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>5</p>',
            'is_correct': False,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'selected_answer_id': wrong_answer.id,
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 0.0)
        self.assertFalse(attempt_answer.is_correct)

    def test_03_grade_mcq_multi_all_correct_no_partial(self):
        """Test MCQ Multi grading - all correct, no partial credit."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Multi',
            'course_id': self.course.id,
            'question_type': 'mcq_multi',
            'question_html': '<p>Select all even numbers</p>',
            'max_score': 10.0,
            'allow_partial_credit': False,
        })

        answer2 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>2</p>',
            'is_correct': True,
        })

        answer3 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>3</p>',
            'is_correct': False,
        })

        answer4 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'selected_answer_ids': [(6, 0, [answer2.id, answer4.id])],
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 10.0)
        self.assertTrue(attempt_answer.is_correct)

    def test_04_grade_mcq_multi_partial_correct_no_partial_credit(self):
        """Test MCQ Multi grading - partial selection, no partial credit allowed."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Multi',
            'course_id': self.course.id,
            'question_type': 'mcq_multi',
            'question_html': '<p>Select all even numbers</p>',
            'max_score': 10.0,
            'allow_partial_credit': False,
        })

        answer2 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>2</p>',
            'is_correct': True,
        })

        answer4 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })

        # Only select one correct answer
        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'selected_answer_ids': [(6, 0, [answer2.id])],
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 0.0, 'Should get 0 without partial credit')
        self.assertFalse(attempt_answer.is_correct)

    def test_05_grade_mcq_multi_with_partial_credit(self):
        """Test MCQ Multi grading - partial credit calculation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Multi',
            'course_id': self.course.id,
            'question_type': 'mcq_multi',
            'question_html': '<p>Select all even numbers</p>',
            'max_score': 10.0,
            'allow_partial_credit': True,
        })

        answer2 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>2</p>',
            'is_correct': True,
        })

        answer3 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>3</p>',
            'is_correct': False,
        })

        answer4 = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })

        # Select 1 correct, 0 incorrect (1/2 correct = 50%)
        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'selected_answer_ids': [(6, 0, [answer2.id])],
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 5.0, 'Should get 50% partial credit')

    def test_06_grade_true_false(self):
        """Test True/False grading."""
        question = self.env['lms.quiz.question'].create({
            'name': 'TF',
            'course_id': self.course.id,
            'question_type': 'tf',
            'question_html': '<p>The sky is blue</p>',
            'max_score': 5.0,
        })

        true_answer = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>True</p>',
            'is_correct': True,
        })

        false_answer = self.env['lms.quiz.question.answer'].create({
            'question_id': question.id,
            'answer_html': '<p>False</p>',
            'is_correct': False,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'selected_answer_id': true_answer.id,
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 5.0)

    def test_07_grade_numerical_within_tolerance(self):
        """Test Numerical grading - within tolerance."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Numerical',
            'course_id': self.course.id,
            'question_type': 'numerical',
            'question_html': '<p>What is pi?</p>',
            'max_score': 10.0,
            'expected_answer_numerical': 3.14,
            'numerical_tolerance': 0.01,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'numerical_value': 3.145,  # Within tolerance
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 10.0)
        self.assertTrue(attempt_answer.is_correct)

    def test_08_grade_numerical_outside_tolerance(self):
        """Test Numerical grading - outside tolerance."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Numerical',
            'course_id': self.course.id,
            'question_type': 'numerical',
            'question_html': '<p>What is pi?</p>',
            'max_score': 10.0,
            'expected_answer_numerical': 3.14,
            'numerical_tolerance': 0.01,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'numerical_value': 3.20,  # Outside tolerance
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 0.0)
        self.assertFalse(attempt_answer.is_correct)

    def test_09_grade_matching_all_correct(self):
        """Test Matching grading - all pairs correct."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Matching',
            'course_id': self.course.id,
            'question_type': 'matching',
            'question_html': '<p>Match countries with capitals</p>',
            'max_score': 10.0,
        })

        pair1 = self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>France</p>',
            'response': '<p>Paris</p>',
        })

        pair2 = self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>Germany</p>',
            'response': '<p>Berlin</p>',
        })

        # Cross-match: France -> Berlin, Germany -> Paris
        pair1.correct_match_id = pair2.id
        pair2.correct_match_id = pair1.id

        # Student selects correct matches
        selections = {
            str(pair1.id): pair2.id,  # France -> Berlin (correct)
            str(pair2.id): pair1.id,  # Germany -> Paris (correct)
        }

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'matching_response': json.dumps(selections),
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 10.0)
        self.assertTrue(attempt_answer.is_correct)

    def test_10_grade_matching_partial(self):
        """Test Matching grading - partial correct."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Matching',
            'course_id': self.course.id,
            'question_type': 'matching',
            'question_html': '<p>Match countries with capitals</p>',
            'max_score': 10.0,
        })

        pair1 = self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>France</p>',
            'response': '<p>Paris</p>',
        })

        pair2 = self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>Germany</p>',
            'response': '<p>Berlin</p>',
        })

        pair1.correct_match_id = pair2.id
        pair2.correct_match_id = pair1.id

        # Student gets 1 correct, 1 wrong
        selections = {
            str(pair1.id): pair2.id,  # Correct
            str(pair2.id): pair2.id,  # Wrong
        }

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'matching_response': json.dumps(selections),
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 5.0, 'Should get 50% for 1/2 correct')

    def test_11_grade_short_answer_case_insensitive(self):
        """Test Short Answer grading - case insensitive."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Short Answer',
            'course_id': self.course.id,
            'question_type': 'short',
            'question_html': '<p>Capital of France?</p>',
            'max_score': 10.0,
            'expected_answer_text': '<p>Paris</p>',
            'case_sensitive': False,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'answer_text': '<p>PARIS</p>',  # Different case
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 10.0, 'Should match case-insensitive')

    def test_12_grade_short_answer_case_sensitive(self):
        """Test Short Answer grading - case sensitive."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Short Answer',
            'course_id': self.course.id,
            'question_type': 'short',
            'question_html': '<p>Type "Paris" exactly</p>',
            'max_score': 10.0,
            'expected_answer_text': '<p>Paris</p>',
            'case_sensitive': True,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'answer_text': '<p>PARIS</p>',
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 0.0, 'Should fail case-sensitive match')

    def test_13_essay_requires_manual_grading(self):
        """Test Essay always requires manual grading."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Essay',
            'course_id': self.course.id,
            'question_type': 'essay',
            'question_html': '<p>Discuss climate change</p>',
            'max_score': 20.0,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'answer_text': '<p>Student essay here...</p>',
        })

        attempt_answer.evaluate_auto_score()

        self.assertEqual(attempt_answer.auto_score, 0.0, 'Essay should have 0 auto_score')
        self.assertFalse(attempt_answer.is_correct, 'Essay should not be auto-marked correct')

    def test_14_manual_grading_metadata(self):
        """Test manual grading metadata is recorded."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Essay',
            'course_id': self.course.id,
            'question_type': 'essay',
            'question_html': '<p>Test</p>',
            'max_score': 20.0,
        })

        attempt_answer = self.env['lms.quiz.attempt.answer'].create({
            'attempt_id': self._create_attempt().id,
            'question_id': question.id,
            'answer_text': '<p>Answer</p>',
        })

        # Manually grade
        attempt_answer.write({'manual_score': 18.0})

        self.assertEqual(attempt_answer.manual_score, 18.0)
        self.assertEqual(attempt_answer.graded_by_id, self.env.user)
        self.assertTrue(attempt_answer.graded_at)

    def _create_attempt(self):
        """Helper to create a quiz attempt."""
        # Create a quiz slide first
        quiz_slide = self.env['slide.slide'].create({
            'name': 'Test Quiz Slide',
            'channel_id': self.course.id,
            'slide_category': 'quiz',
        })

        # Create quiz definition
        quiz_def = self.env['lms.quiz.definition'].create({
            'name': 'Test Quiz',
            'slide_id': quiz_slide.id,
        })

        return self.env['lms.quiz.attempt'].create({
            'quiz_id': quiz_def.id,
            'student_id': self.student.id,
        })
