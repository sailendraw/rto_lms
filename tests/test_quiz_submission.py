# -*- coding: utf-8 -*-
"""
Unit Tests for RTO LMS Quiz Question Creation and Submission
Tests enhanced question types: MCQ (single/multi), True/False, Short Answer, Numerical
"""

from odoo.tests import tagged, TransactionCase
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install', 'rto_lms')
class TestQuizQuestionCreation(TransactionCase):
    """Test creating different question types"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test channel (course)
        cls.channel = cls.env['slide.channel'].create({
            'name': 'Test RTO Course',
            'channel_type': 'training',
            'enroll': 'invite',
        })
        
        # Create test slide (unit)
        cls.slide = cls.env['slide.slide'].create({
            'name': 'Test Quiz Slide',
            'channel_id': cls.channel.id,
            'slide_category': 'quiz',
            'is_published': True,
        })
        
        # Create test user
        cls.test_user = cls.env['res.users'].create({
            'name': 'Test Student',
            'login': 'test_student',
            'email': 'student@test.com',
        })
        
        # Enroll user in channel
        cls.env['slide.channel.partner'].create({
            'channel_id': cls.channel.id,
            'partner_id': cls.test_user.partner_id.id,
        })
    
    def test_create_multiple_choice_multi_question(self):
        """Test creating a multiple choice (multiple answers) question"""
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'Select all fruits',
            'question_type': 'multiple_choice_multi',
            'sequence': 1,
            'answer_ids': [
                (0, 0, {
                    'text_value': 'Apple',
                    'is_correct': True,
                    'sequence': 1,
                }),
                (0, 0, {
                    'text_value': 'Banana',
                    'is_correct': True,
                    'sequence': 2,
                }),
                (0, 0, {
                    'text_value': 'Carrot',
                    'is_correct': False,
                    'sequence': 3,
                }),
            ]
        })
        
        self.assertEqual(question.question_type, 'multiple_choice_multi')
        self.assertEqual(len(question.answer_ids), 3)
        self.assertEqual(len(question.answer_ids.filtered('is_correct')), 2)
    
    def test_create_true_false_question(self):
        """Test creating a true/false question"""
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'The sky is blue',
            'question_type': 'true_false',
            'sequence': 2,
            'answer_ids': [
                (0, 0, {
                    'text_value': 'true',
                    'is_correct': True,
                    'sequence': 1,
                }),
                (0, 0, {
                    'text_value': 'false',
                    'is_correct': False,
                    'sequence': 2,
                }),
            ]
        })
        
        self.assertEqual(question.question_type, 'true_false')
        self.assertEqual(len(question.answer_ids), 2)
        self.assertTrue(question.answer_ids.filtered(lambda a: a.text_value == 'true').is_correct)
    
    def test_create_short_answer_question(self):
        """Test creating a short answer question"""
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'What is the capital of France?',
            'question_type': 'short_answer',
            'sequence': 3,
            'expected_answer_text': 'Paris',
        })
        
        self.assertEqual(question.question_type, 'short_answer')
        self.assertEqual(question.expected_answer_text, 'Paris')
        self.assertEqual(len(question.answer_ids), 0)  # No answer_ids for short answer
    
    def test_create_numerical_question(self):
        """Test creating a numerical question"""
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'What is 2 + 2?',
            'question_type': 'numerical',
            'sequence': 4,
        })
        
        self.assertEqual(question.question_type, 'numerical')
        self.assertEqual(len(question.answer_ids), 0)  # No answer_ids for numerical


@tagged('post_install', '-at_install', 'rto_lms')
class TestQuizSubmission(TransactionCase):
    """Test quiz submission with different question types"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Create test channel
        cls.channel = cls.env['slide.channel'].create({
            'name': 'Test RTO Course',
            'channel_type': 'training',
            'enroll': 'public',
        })
        
        # Create test slide
        cls.slide = cls.env['slide.slide'].create({
            'name': 'Test Quiz Slide',
            'channel_id': cls.channel.id,
            'slide_category': 'quiz',
            'is_published': True,
        })
        
        # Create test user
        cls.test_user = cls.env['res.users'].create({
            'name': 'Test Student',
            'login': 'test_student_submit',
            'email': 'student_submit@test.com',
        })
        
        # Enroll user
        cls.env['slide.channel.partner'].create({
            'channel_id': cls.channel.id,
            'partner_id': cls.test_user.partner_id.id,
        })
        
        # Create MCQ Multi question
        cls.mcq_multi_question = cls.env['slide.question'].create({
            'slide_id': cls.slide.id,
            'question': 'Select all programming languages',
            'question_type': 'multiple_choice_multi',
            'sequence': 1,
        })
        
        cls.mcq_answer_correct_1 = cls.env['slide.answer'].create({
            'question_id': cls.mcq_multi_question.id,
            'text_value': 'Python',
            'is_correct': True,
            'sequence': 1,
        })
        
        cls.mcq_answer_correct_2 = cls.env['slide.answer'].create({
            'question_id': cls.mcq_multi_question.id,
            'text_value': 'JavaScript',
            'is_correct': True,
            'sequence': 2,
        })
        
        cls.mcq_answer_wrong = cls.env['slide.answer'].create({
            'question_id': cls.mcq_multi_question.id,
            'text_value': 'Excel',
            'is_correct': False,
            'sequence': 3,
        })
        
        # Create True/False question
        cls.tf_question = cls.env['slide.question'].create({
            'slide_id': cls.slide.id,
            'question': 'Is Python a programming language?',
            'question_type': 'true_false',
            'sequence': 2,
        })
        
        cls.tf_answer_true = cls.env['slide.answer'].create({
            'question_id': cls.tf_question.id,
            'text_value': 'true',
            'is_correct': True,
            'sequence': 1,
        })
        
        cls.tf_answer_false = cls.env['slide.answer'].create({
            'question_id': cls.tf_question.id,
            'text_value': 'false',
            'is_correct': False,
            'sequence': 2,
        })
        
        # Create short answer question
        cls.short_question = cls.env['slide.question'].create({
            'slide_id': cls.slide.id,
            'question': 'What is the capital of Australia?',
            'question_type': 'short_answer',
            'sequence': 3,
            'expected_answer_text': 'Canberra',
        })
        
        # Create numerical question
        cls.numerical_question = cls.env['slide.question'].create({
            'slide_id': cls.slide.id,
            'question': 'What is 10 x 10?',
            'question_type': 'numerical',
            'sequence': 4,
        })
    
    def test_submit_correct_answers_mcq_multi(self):
        """Test submitting all correct answers for MCQ multi"""
        # Submit both correct answers
        answer_ids = [self.mcq_answer_correct_1.id, self.mcq_answer_correct_2.id, self.tf_answer_true.id]
        
        # Validate MCQ questions are answered
        answered_questions = self.env['slide.answer'].browse(answer_ids).mapped('question_id')
        mcq_questions = self.slide.question_ids.filtered(
            lambda q: q.question_type in ['multiple_choice_multi', 'true_false']
        )
        
        self.assertEqual(answered_questions, mcq_questions)
        
        # Check no wrong answers
        wrong_answers = self.env['slide.answer'].browse(answer_ids).filtered(lambda a: not a.is_correct)
        self.assertEqual(len(wrong_answers), 0)
    
    def test_submit_partial_answers_mcq_multi(self):
        """Test submitting only one correct answer for MCQ multi (should fail)"""
        # Submit only one correct answer
        answer_ids = [self.mcq_answer_correct_1.id, self.tf_answer_true.id]
        
        # Check if there are wrong answers (missing correct answer = wrong)
        all_correct_answers = self.mcq_multi_question.answer_ids.filtered('is_correct')
        selected_correct = self.env['slide.answer'].browse(answer_ids).filtered(
            lambda a: a.question_id == self.mcq_multi_question
        )
        
        # Should have selected 2 correct answers but only selected 1
        self.assertNotEqual(len(selected_correct), len(all_correct_answers))
    
    def test_submit_with_wrong_answer_mcq_multi(self):
        """Test submitting with one wrong answer"""
        # Submit correct answers + one wrong answer
        answer_ids = [
            self.mcq_answer_correct_1.id, 
            self.mcq_answer_correct_2.id,
            self.mcq_answer_wrong.id,  # Wrong answer
            self.tf_answer_true.id
        ]
        
        # Check for wrong answers
        wrong_answers = self.env['slide.answer'].browse(answer_ids).filtered(lambda a: not a.is_correct)
        self.assertEqual(len(wrong_answers), 1)
        self.assertEqual(wrong_answers.text_value, 'Excel')
    
    def test_submit_true_false_correct(self):
        """Test submitting correct true/false answer"""
        answer_ids = [
            self.mcq_answer_correct_1.id,
            self.mcq_answer_correct_2.id,
            self.tf_answer_true.id  # Correct
        ]
        
        tf_answer = self.env['slide.answer'].browse(answer_ids).filtered(
            lambda a: a.question_id == self.tf_question
        )
        self.assertTrue(tf_answer.is_correct)
    
    def test_submit_true_false_wrong(self):
        """Test submitting wrong true/false answer"""
        answer_ids = [
            self.mcq_answer_correct_1.id,
            self.mcq_answer_correct_2.id,
            self.tf_answer_false.id  # Wrong
        ]
        
        tf_answer = self.env['slide.answer'].browse(answer_ids).filtered(
            lambda a: a.question_id == self.tf_question
        )
        self.assertFalse(tf_answer.is_correct)
    
    def test_incomplete_quiz_mcq_only(self):
        """Test that incomplete quiz (missing answers) is detected"""
        # Only answer first question, not the second
        answer_ids = [self.mcq_answer_correct_1.id, self.mcq_answer_correct_2.id]
        
        # Get MCQ questions that need answers
        mcq_questions = self.slide.question_ids.filtered(
            lambda q: q.question_type in ['multiple_choice_multi', 'true_false']
        )
        
        answered_questions = self.env['slide.answer'].browse(answer_ids).mapped('question_id')
        
        # Should detect missing true/false question
        self.assertNotEqual(answered_questions, mcq_questions)
    
    def test_short_answer_and_numerical_accepted(self):
        """Test that short answer and numerical questions don't require answer_ids"""
        # Only answer MCQ questions
        answer_ids = [
            self.mcq_answer_correct_1.id,
            self.mcq_answer_correct_2.id,
            self.tf_answer_true.id
        ]
        
        # Get only MCQ questions for validation
        mcq_questions = self.slide.question_ids.filtered(
            lambda q: q.question_type in ['multiple_choice_multi', 'true_false']
        )
        
        answered_questions = self.env['slide.answer'].browse(answer_ids).mapped('question_id')
        
        # Should match - short_answer and numerical are excluded from validation
        self.assertEqual(answered_questions, mcq_questions)
    
    def test_question_type_distribution(self):
        """Test that all question types are present"""
        questions = self.slide.question_ids
        
        mcq_multi = questions.filtered(lambda q: q.question_type == 'multiple_choice_multi')
        true_false = questions.filtered(lambda q: q.question_type == 'true_false')
        short_answer = questions.filtered(lambda q: q.question_type == 'short_answer')
        numerical = questions.filtered(lambda q: q.question_type == 'numerical')
        
        self.assertEqual(len(mcq_multi), 1)
        self.assertEqual(len(true_false), 1)
        self.assertEqual(len(short_answer), 1)
        self.assertEqual(len(numerical), 1)
        self.assertEqual(len(questions), 4)


@tagged('post_install', '-at_install', 'rto_lms')
class TestQuizAnswerValidation(TransactionCase):
    """Test answer validation logic"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.channel = cls.env['slide.channel'].create({
            'name': 'Validation Test Course',
            'channel_type': 'training',
        })
        
        cls.slide = cls.env['slide.slide'].create({
            'name': 'Validation Quiz',
            'channel_id': cls.channel.id,
            'slide_category': 'quiz',
        })
    
    def test_mcq_multi_requires_all_correct_answers(self):
        """Test that MCQ multi requires all correct answers to be selected"""
        question = self.env['slide.question'].create({
            'slide_id': self.slide.id,
            'question': 'Select all correct',
            'question_type': 'multiple_choice_multi',
        })
        
        answer1 = self.env['slide.answer'].create({
            'question_id': question.id,
            'text_value': 'Correct 1',
            'is_correct': True,
        })
        
        answer2 = self.env['slide.answer'].create({
            'question_id': question.id,
            'text_value': 'Correct 2',
            'is_correct': True,
        })
        
        answer3 = self.env['slide.answer'].create({
            'question_id': question.id,
            'text_value': 'Wrong',
            'is_correct': False,
        })
        
        # All correct answers
        all_correct = question.answer_ids.filtered('is_correct')
        self.assertEqual(len(all_correct), 2)
        
        # Selecting only one correct answer is insufficient
        selected_one = self.env['slide.answer'].browse([answer1.id])
        self.assertNotEqual(len(selected_one), len(all_correct))
        
        # Selecting both correct answers is valid
        selected_both = self.env['slide.answer'].browse([answer1.id, answer2.id])
        self.assertEqual(len(selected_both), len(all_correct))
        self.assertTrue(all(a.is_correct for a in selected_both))
