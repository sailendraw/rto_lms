# -*- coding: utf-8 -*-
# Part of RTO LMS. See LICENSE file for full copyright and licensing details.

"""Unit tests for quiz question type creation and validation."""

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestQuizQuestionTypes(TransactionCase):
    """Test creation and validation of all 7 question types."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test course (not RTO mode for simple testing)
        cls.course = cls.env['slide.channel'].create({
            'name': 'Test Course',
            'is_rto_course': False,
        })

    def test_01_create_mcq_single(self):
        """Test MCQ Single question creation and validation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Single Test',
            'course_id': self.course.id,
            'question_type': 'mcq_single',
            'question_html': '<p>What is 2+2?</p>',
            'max_score': 10.0,
        })

        # Add answers
        question.answer_ids = [(0, 0, {
            'answer_html': '<p>3</p>',
            'is_correct': False,
        }), (0, 0, {
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })]

        self.assertEqual(question.question_type, 'mcq_single')
        self.assertEqual(len(question.answer_ids), 2)
        self.assertEqual(len(question.answer_ids.filtered('is_correct')), 1)

    def test_02_mcq_single_constraint_only_one_correct(self):
        """Test MCQ Single can only have one correct answer."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Single Constraint Test',
            'course_id': self.course.id,
            'question_type': 'mcq_single',
            'question_html': '<p>Test</p>',
            'max_score': 10.0,
        })

        with self.assertRaises(ValidationError, msg='Should not allow multiple correct answers'):
            question.answer_ids = [(0, 0, {
                'answer_html': '<p>Answer 1</p>',
                'is_correct': True,
            }), (0, 0, {
                'answer_html': '<p>Answer 2</p>',
                'is_correct': True,
            })]

    def test_03_create_mcq_multi(self):
        """Test MCQ Multi question creation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'MCQ Multi Test',
            'course_id': self.course.id,
            'question_type': 'mcq_multi',
            'question_html': '<p>Select all even numbers</p>',
            'max_score': 10.0,
            'allow_partial_credit': True,
        })

        question.answer_ids = [(0, 0, {
            'answer_html': '<p>2</p>',
            'is_correct': True,
        }), (0, 0, {
            'answer_html': '<p>3</p>',
            'is_correct': False,
        }), (0, 0, {
            'answer_html': '<p>4</p>',
            'is_correct': True,
        })]

        self.assertEqual(question.question_type, 'mcq_multi')
        self.assertTrue(question.allow_partial_credit)
        self.assertEqual(len(question.answer_ids.filtered('is_correct')), 2)

    def test_04_create_true_false(self):
        """Test True/False question creation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'TF Test',
            'course_id': self.course.id,
            'question_type': 'tf',
            'question_html': '<p>The sky is blue</p>',
            'max_score': 5.0,
        })

        question.answer_ids = [(0, 0, {
            'answer_html': '<p>True</p>',
            'is_correct': True,
        }), (0, 0, {
            'answer_html': '<p>False</p>',
            'is_correct': False,
        })]

        self.assertEqual(len(question.answer_ids), 2)

    def test_05_tf_constraint_exactly_two_answers(self):
        """Test TF must have exactly 2 answers."""
        question = self.env['lms.quiz.question'].create({
            'name': 'TF Constraint Test',
            'course_id': self.course.id,
            'question_type': 'tf',
            'question_html': '<p>Test</p>',
            'max_score': 5.0,
        })

        with self.assertRaises(ValidationError, msg='Should require exactly 2 answers'):
            question.answer_ids = [(0, 0, {
                'answer_html': '<p>True</p>',
                'is_correct': True,
            }), (0, 0, {
                'answer_html': '<p>False</p>',
                'is_correct': False,
            }), (0, 0, {
                'answer_html': '<p>Maybe</p>',
                'is_correct': False,
            })]

    def test_06_create_short_answer(self):
        """Test Short Answer question creation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Short Answer Test',
            'course_id': self.course.id,
            'question_type': 'short',
            'question_html': '<p>What is the capital of France?</p>',
            'max_score': 10.0,
            'expected_answer_text': '<p>Paris</p>',
            'case_sensitive': False,
        })

        self.assertEqual(question.question_type, 'short')
        self.assertTrue(question.is_manual_grading)
        self.assertFalse(question.case_sensitive)

    def test_07_create_essay(self):
        """Test Essay question creation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Essay Test',
            'course_id': self.course.id,
            'question_type': 'essay',
            'question_html': '<p>Discuss the impact of climate change</p>',
            'max_score': 20.0,
            'expected_answer_text': '<p>Model answer for grading reference</p>',
        })

        self.assertEqual(question.question_type, 'essay')
        self.assertTrue(question.is_manual_grading)

    def test_08_create_numerical(self):
        """Test Numerical question creation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Numerical Test',
            'course_id': self.course.id,
            'question_type': 'numerical',
            'question_html': '<p>What is the value of pi (2 decimal places)?</p>',
            'max_score': 5.0,
            'expected_answer_numerical': 3.14,
            'numerical_tolerance': 0.01,
            'numerical_unit': '',
        })

        self.assertEqual(question.question_type, 'numerical')
        self.assertEqual(question.expected_answer_numerical, 3.14)
        self.assertFalse(question.is_manual_grading)

    def test_09_numerical_negative_tolerance(self):
        """Test numerical question cannot have negative tolerance."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Numerical Tolerance Test',
            'course_id': self.course.id,
            'question_type': 'numerical',
            'question_html': '<p>Test</p>',
            'max_score': 5.0,
            'expected_answer_numerical': 3.14,
        })

        with self.assertRaises(ValidationError, msg='Should not allow negative tolerance'):
            question.numerical_tolerance = -0.5

    def test_10_create_matching(self):
        """Test Matching question creation."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Matching Test',
            'course_id': self.course.id,
            'question_type': 'matching',
            'question_html': '<p>Match countries with capitals</p>',
            'max_score': 10.0,
        })

        # Create pairs
        pair1 = self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>France</p>',
            'response': '<p>Paris</p>',
            'sequence': 1,
        })

        pair2 = self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>Germany</p>',
            'response': '<p>Berlin</p>',
            'sequence': 2,
        })

        # Set correct matches
        pair1.correct_match_id = pair2.id
        pair2.correct_match_id = pair1.id

        self.assertEqual(question.question_type, 'matching')
        self.assertEqual(len(question.matching_pair_ids), 2)

    def test_11_matching_constraint_minimum_pairs(self):
        """Test matching requires at least 2 pairs."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Matching Constraint Test',
            'course_id': self.course.id,
            'question_type': 'matching',
            'question_html': '<p>Test</p>',
            'max_score': 10.0,
        })

        self.env['lms.quiz.question.matching.pair'].create({
            'question_id': question.id,
            'prompt': '<p>A</p>',
            'response': '<p>B</p>',
        })

        with self.assertRaises(ValidationError, msg='Should require at least 2 pairs'):
            question._check_matching_pairs()

    def test_12_text_questions_cannot_have_answers(self):
        """Test essay/short/numerical/matching cannot have answer options."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Essay No Answers Test',
            'course_id': self.course.id,
            'question_type': 'essay',
            'question_html': '<p>Test</p>',
            'max_score': 10.0,
        })

        with self.assertRaises(ValidationError, msg='Should not allow predefined answers'):
            question.answer_ids = [(0, 0, {
                'answer_html': '<p>Wrong</p>',
                'is_correct': False,
            })]

    def test_13_max_score_positive(self):
        """Test max_score must be positive."""
        with self.assertRaises(ValidationError, msg='Should require positive max_score'):
            self.env['lms.quiz.question'].create({
                'name': 'Score Test',
                'course_id': self.course.id,
                'question_type': 'mcq_single',
                'question_html': '<p>Test</p>',
                'max_score': -5.0,
            })

    def test_14_question_type_selector_action(self):
        """Test action_open_question_form method."""
        question = self.env['lms.quiz.question'].create({
            'name': 'Action Test',
            'course_id': self.course.id,
            'question_type': 'essay',
            'question_html': '<p>Test</p>',
            'max_score': 10.0,
        })

        action = question.action_open_question_form()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'lms.quiz.question')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_question_type'], 'essay')
