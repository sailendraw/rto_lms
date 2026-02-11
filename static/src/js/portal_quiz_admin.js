/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { jsonrpc } from "@web/core/network/rpc_service";

/**
 * Admin Quiz Management Widget
 * Handles question creation and quiz configuration for trainers
 */
publicWidget.registry.RTOQuizAdmin = publicWidget.Widget.extend({
    selector: '#addQuestionModal',
    events: {
        'change input[name="question_type"]': '_onQuestionTypeChange',
        'click #add_answer_btn': '_onAddAnswer',
        'click #save_question_btn': '_onSaveQuestion',
        'click .remove-answer': '_onRemoveAnswer',
    },

    /**
     * @override
     */
    start: function () {
        this.slideId = $('#rto_quiz_start_btn').data('slide-id') || 
                       parseInt(window.location.pathname.split('/')[2]);
        this.answerIndex = 0;
        this._initializeAnswers();
        return this._super.apply(this, arguments);
    },

    /**
     * Initialize with two default answers
     */
    _initializeAnswers: function () {
        this._addAnswerField();
        this._addAnswerField();
    },

    /**
     * Handle question type change
     */
    _onQuestionTypeChange: function (ev) {
        const questionType = ev.target.value;
        const answersSection = this.$('#answers_section');
        const helpText = this.$('#question_type_help');
        
        // Update help text
        const helpTexts = {
            'multiple_choice_single': '<strong>Single Choice:</strong> Student selects ONE correct answer from multiple options.',
            'multiple_choice_multi': '<strong>Multiple Choice:</strong> Student can select MULTIPLE correct answers (checkboxes will be shown).',
            'true_false': '<strong>True/False:</strong> Student selects either True or False. Answers will be auto-generated.',
            'short_answer': '<strong>Short Answer:</strong> Student types a short text response. You can specify multiple acceptable answers.',
            'essay': '<strong>Essay:</strong> Student writes a detailed text response. Requires manual grading.',
            'numerical': '<strong>Numerical:</strong> Student enters a number. You can specify the correct answer and tolerance.',
            'matching': '<strong>Matching:</strong> Student matches items from two lists. Specify pairs in the answers section.',
        };
        helpText.html(helpTexts[questionType] || '');
        
        // Show/hide answers section based on question type
        if (['essay'].includes(questionType)) {
            answersSection.hide();
        } else {
            answersSection.show();
            
            // Clear and reinitialize answers
            this.$('#answers_container').empty();
            this.answerIndex = 0;
            
            if (questionType === 'true_false') {
                // Add True/False options
                this._addAnswerField('True', true);
                this._addAnswerField('False', false);
                this.$('#add_answer_btn').hide();
            } else {
                // Add two empty answers
                this._addAnswerField();
                this._addAnswerField();
                this.$('#add_answer_btn').show();
            }
        }
    },

    /**
     * Add answer button clicked
     */
    _onAddAnswer: function (ev) {
        ev.preventDefault();
        this._addAnswerField();
    },

    /**
     * Add an answer input field
     */
    _addAnswerField: function (text = '', isCorrect = false) {
        const index = this.answerIndex++;
        const questionType = this.$('input[name="question_type"]:checked').val();
        const isMultiChoice = questionType === 'multiple_choice_multi';
        const inputType = isMultiChoice ? 'checkbox' : 'radio';
        
        const answerHtml = `
            <div class="answer-field mb-2 border rounded p-2" data-answer-index="${index}">
                <div class="row g-2">
                    <div class="col-auto">
                        <div class="form-check mt-2">
                            <input class="form-check-input answer-correct" type="${inputType}" 
                                   name="answer_correct${isMultiChoice ? '_' + index : ''}" 
                                   id="answer_correct_${index}" ${isCorrect ? 'checked' : ''}/>
                            <label class="form-check-label" for="answer_correct_${index}">
                                <small class="text-muted">Correct</small>
                            </label>
                        </div>
                    </div>
                    <div class="col">
                        <input type="text" class="form-control answer-text" 
                               placeholder="Answer text" value="${text}" required/>
                    </div>
                    ${questionType === 'matching' ? `
                        <div class="col-md-4">
                            <input type="text" class="form-control answer-match" 
                                   placeholder="Match with..." />
                        </div>
                    ` : ''}
                    <div class="col-auto">
                        <button type="button" class="btn btn-sm btn-outline-danger remove-answer">
                            <i class="fa fa-trash"/>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        this.$('#answers_container').append(answerHtml);
    },

    /**
     * Remove an answer field
     */
    _onRemoveAnswer: function (ev) {
        ev.preventDefault();
        const answersContainer = this.$('#answers_container');
        
        // Keep at least 2 answers for choice questions
        if (answersContainer.find('.answer-field').length > 2) {
            $(ev.currentTarget).closest('.answer-field').remove();
        } else {
            alert('At least 2 answers are required for choice questions.');
        }
    },

    /**
     * Save the question
     */
    _onSaveQuestion: function (ev) {
        ev.preventDefault();
        
        const questionText = this.$('#question_text').val().trim();
        if (!questionText) {
            alert('Please enter a question.');
            return;
        }
        
        const questionType = this.$('input[name="question_type"]:checked').val();
        const questionPoints = parseFloat(this.$('#question_points').val()) || 1.0;
        
        // Collect answers
        const answers = [];
        const isMultiChoice = questionType === 'multiple_choice_multi';
        
        if (!['essay'].includes(questionType)) {
            this.$('.answer-field').each(function () {
                const $field = $(this);
                const text = $field.find('.answer-text').val().trim();
                const isCorrect = $field.find('.answer-correct').is(':checked');
                const matchText = $field.find('.answer-match').val() || '';
                
                if (text) {
                    answers.push({
                        text: text,
                        is_correct: isCorrect,
                        match_text: matchText,
                        sequence: answers.length * 10,
                    });
                }
            });
            
            // Validation: At least one correct answer for choice questions
            if (['multiple_choice_single', 'multiple_choice_multi', 'true_false'].includes(questionType)) {
                const hasCorrect = answers.some(a => a.is_correct);
                if (!hasCorrect) {
                    alert('Please mark at least one answer as correct.');
                    return;
                }
            }
        }
        
        // Prepare question data
        const questionData = {
            question: questionText,
            question_type: questionType,
            points: questionPoints,
            allow_partial_credit: this.$('#allow_partial_credit').is(':checked'),
            negative_marking: this.$('#negative_marking').is(':checked'),
            answers: answers,
            sequence: (new Date()).getTime() / 1000, // Use timestamp for sequence
        };
        
        // Show loading
        const $saveBtn = this.$('#save_question_btn');
        $saveBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"/> Saving...');
        
        // Send to server
        jsonrpc('/slides/' + this.slideId + '/rto_quiz/add_question', {
            slide_id: this.slideId,
            question_data: questionData,
        }).then((result) => {
            if (result.error) {
                alert('Error: ' + result.error);
                $saveBtn.prop('disabled', false).html('Save Question');
            } else {
                // Success - reload page to show new question
                location.reload();
            }
        }).catch((error) => {
            console.error('Error saving question:', error);
            alert('Failed to save question. Please try again.');
            $saveBtn.prop('disabled', false).html('Save Question');
        });
    },
});

export default publicWidget.registry.RTOQuizAdmin;
