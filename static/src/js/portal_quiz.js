/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import publicWidget from "@web/legacy/js/public/public_widget";

/**
 * RTO Quiz Portal Widget
 * Handles student quiz-taking interface with multi-choice support
 */
publicWidget.registry.RTOQuizPortal = publicWidget.Widget.extend({
    selector: '#rto_quiz_start_btn',
    events: {
        'click #rto_quiz_start_btn': '_onStartQuiz',
        'click #rto_quiz_prev_btn': '_onPrevQuestion',
        'click #rto_quiz_next_btn': '_onNextQuestion',
        'click #rto_quiz_submit_btn': '_onSubmitQuiz',
    },

    /**
     * Initialize quiz widget
     */
    start() {
        this._super(...arguments);
        this.quizData = null;
        this.currentQuestionIndex = 0;
        this.attemptId = null;
        this.responses = {};
        this.autoSaveTimeout = null;
    },

    /**
     * Start quiz - fetch data and render first question
     */
    async _onStartQuiz(ev) {
        ev.preventDefault();
        const slideId = parseInt(window.location.pathname.split('/')[2]);
        
        try {
            const result = await rpc('/slides/' + slideId + '/rto_quiz/start', {});
            
            if (result.error) {
                this._showError(result.error);
                return;
            }
            
            this.quizData = result.quiz;
            this.attemptId = result.attempt_id;
            this.responses = result.saved_responses || {};
            
            // Hide intro, show quiz interface
            $('#rto_quiz_start_btn').closest('.card').slideUp();
            $('#rto_quiz_interface').slideDown();
            
            // Setup navigation
            $('#total_questions').text(this.quizData.questions.length);
            
            // Render first question
            this._renderQuestion(0);
        } catch (error) {
            console.error('Failed to start quiz:', error);
            this._showError('Failed to start quiz. Please try again.');
        }
    },

    /**
     * Render question by index
     */
    _renderQuestion(index) {
        if (!this.quizData || index < 0 || index >= this.quizData.questions.length) {
            return;
        }
        
        this.currentQuestionIndex = index;
        const question = this.quizData.questions[index];
        
        // Update navigation
        $('#current_question_num').text(index + 1);
        $('#rto_quiz_prev_btn').prop('disabled', index === 0);
        $('#rto_quiz_next_btn').prop('disabled', index === this.quizData.questions.length - 1);
        
        // Render question based on type
        let questionHtml = '';
        
        switch (question.type) {
            case 'multiple_choice_single':
                questionHtml = this._renderMultipleChoiceSingle(question);
                break;
            case 'multiple_choice_multi':
                questionHtml = this._renderMultipleChoiceMulti(question);
                break;
            case 'true_false':
                questionHtml = this._renderTrueFalse(question);
                break;
            case 'short_answer':
                questionHtml = this._renderShortAnswer(question);
                break;
            case 'essay':
                questionHtml = this._renderEssay(question);
                break;
            case 'numerical':
                questionHtml = this._renderNumerical(question);
                break;
            default:
                questionHtml = '<p class="text-muted">Question type not supported</p>';
        }
        
        $('#rto_quiz_question_container').html(questionHtml);
        
        // Restore saved responses
        this._restoreResponse(question);
        
        // Bind change events for auto-save
        this._bindAutoSave();
    },

    /**
     * Render single-choice question (radio buttons)
     */
    _renderMultipleChoiceSingle(question) {
        let html = `
            <h3 class="mb-4">${question.question}</h3>
            <p class="text-muted small mb-3">Select one answer (${question.points} points)</p>
            <div class="list-group" data-question-id="${question.id}" data-question-type="single">
        `;
        
        question.answers.forEach(answer => {
            html += `
                <label class="list-group-item list-group-item-action cursor-pointer">
                    <div class="d-flex align-items-center">
                        <input type="radio" name="question_${question.id}" value="${answer.id}" 
                               class="form-check-input me-3" data-answer-id="${answer.id}">
                        <span>${answer.text}</span>
                    </div>
                </label>
            `;
        });
        
        html += '</div>';
        return html;
    },

    /**
     * Render multi-choice question (checkboxes)
     */
    _renderMultipleChoiceMulti(question) {
        let html = `
            <h3 class="mb-4">${question.question}</h3>
            <p class="text-muted small mb-3">Select all correct answers (${question.points} points)</p>
            <div class="list-group" data-question-id="${question.id}" data-question-type="multi">
        `;
        
        question.answers.forEach(answer => {
            html += `
                <label class="list-group-item list-group-item-action cursor-pointer">
                    <div class="d-flex align-items-center">
                        <input type="checkbox" name="question_${question.id}[]" value="${answer.id}" 
                               class="form-check-input me-3" data-answer-id="${answer.id}">
                        <span>${answer.text}</span>
                    </div>
                </label>
            `;
        });
        
        html += '</div>';
        return html;
    },

    /**
     * Render true/false question
     */
    _renderTrueFalse(question) {
        return `
            <h3 class="mb-4">${question.question}</h3>
            <p class="text-muted small mb-3">Select True or False (${question.points} points)</p>
            <div class="list-group" data-question-id="${question.id}" data-question-type="single">
                <label class="list-group-item list-group-item-action cursor-pointer">
                    <div class="d-flex align-items-center">
                        <input type="radio" name="question_${question.id}" value="${question.answers[0].id}" 
                               class="form-check-input me-3" data-answer-id="${question.answers[0].id}">
                        <span>${question.answers[0].text}</span>
                    </div>
                </label>
                <label class="list-group-item list-group-item-action cursor-pointer">
                    <div class="d-flex align-items-center">
                        <input type="radio" name="question_${question.id}" value="${question.answers[1].id}" 
                               class="form-check-input me-3" data-answer-id="${question.answers[1].id}">
                        <span>${question.answers[1].text}</span>
                    </div>
                </label>
            </div>
        `;
    },

    /**
     * Render short answer question
     */
    _renderShortAnswer(question) {
        return `
            <h3 class="mb-4">${question.question}</h3>
            <p class="text-muted small mb-3">Enter your answer (${question.points} points)</p>
            <div data-question-id="${question.id}" data-question-type="text">
                <input type="text" class="form-control form-control-lg" 
                       placeholder="Type your answer here..." 
                       data-response-field="text">
            </div>
        `;
    },

    /**
     * Render essay question
     */
    _renderEssay(question) {
        return `
            <h3 class="mb-4">${question.question}</h3>
            <p class="text-muted small mb-3">Write your detailed answer (${question.points} points)</p>
            <div data-question-id="${question.id}" data-question-type="essay">
                <textarea class="form-control" rows="8" 
                          placeholder="Type your essay here..." 
                          data-response-field="text"></textarea>
            </div>
        `;
    },

    /**
     * Render numerical question
     */
    _renderNumerical(question) {
        return `
            <h3 class="mb-4">${question.question}</h3>
            <p class="text-muted small mb-3">Enter a numerical answer (${question.points} points)</p>
            <div data-question-id="${question.id}" data-question-type="number">
                <div class="input-group input-group-lg">
                    <input type="number" step="any" class="form-control" 
                           placeholder="Enter number..." 
                           data-response-field="number">
                    ${question.numerical_unit ? `<span class="input-group-text">${question.numerical_unit}</span>` : ''}
                </div>
            </div>
        `;
    },

    /**
     * Restore previously saved response
     */
    _restoreResponse(question) {
        const savedResponse = this.responses[question.id];
        if (!savedResponse) return;
        
        if (question.type === 'multiple_choice_single' || question.type === 'true_false') {
            const answerIds = savedResponse.answer_ids || [];
            if (answerIds.length > 0) {
                $(`input[data-answer-id="${answerIds[0]}"]`).prop('checked', true);
            }
        } else if (question.type === 'multiple_choice_multi') {
            const answerIds = savedResponse.answer_ids || [];
            answerIds.forEach(id => {
                $(`input[data-answer-id="${id}"]`).prop('checked', true);
            });
        } else if (savedResponse.text) {
            $('[data-response-field="text"]').val(savedResponse.text);
        } else if (savedResponse.number !== undefined) {
            $('[data-response-field="number"]').val(savedResponse.number);
        }
    },

    /**
     * Bind auto-save events
     */
    _bindAutoSave() {
        const self = this;
        $('#rto_quiz_question_container input, #rto_quiz_question_container textarea').on('change', function() {
            self._autoSaveResponse();
        });
    },

    /**
     * Auto-save response with debouncing
     */
    _autoSaveResponse() {
        clearTimeout(this.autoSaveTimeout);
        this.autoSaveTimeout = setTimeout(() => {
            this._saveCurrentResponse();
        }, 1000); // Save after 1 second of inactivity
    },

    /**
     * Save current question response
     */
    async _saveCurrentResponse() {
        const question = this.quizData.questions[this.currentQuestionIndex];
        const responseData = this._collectResponse();
        
        // Update local responses
        this.responses[question.id] = responseData;
        
        // Save to server
        try {
            await rpc('/slides/rto_quiz/save_response', {
                attempt_id: this.attemptId,
                question_id: question.id,
                response_data: responseData,
            });
        } catch (error) {
            console.error('Failed to save response:', error);
        }
    },

    /**
     * Collect current response data
     */
    _collectResponse() {
        const $container = $('#rto_quiz_question_container');
        const questionType = $container.find('[data-question-type]').data('question-type');
        const responseData = {};
        
        if (questionType === 'single') {
            const checked = $container.find('input[type="radio"]:checked');
            if (checked.length) {
                responseData.answer_ids = [parseInt(checked.data('answer-id'))];
            }
        } else if (questionType === 'multi') {
            const checked = $container.find('input[type="checkbox"]:checked');
            responseData.answer_ids = checked.map(function() {
                return parseInt($(this).data('answer-id'));
            }).get();
        } else if (questionType === 'text' || questionType === 'essay') {
            responseData.text = $container.find('[data-response-field="text"]').val();
        } else if (questionType === 'number') {
            responseData.number = parseFloat($container.find('[data-response-field="number"]').val()) || 0;
        }
        
        return responseData;
    },

    /**
     * Navigate to previous question
     */
    _onPrevQuestion(ev) {
        ev.preventDefault();
        this._saveCurrentResponse();
        this._renderQuestion(this.currentQuestionIndex - 1);
    },

    /**
     * Navigate to next question
     */
    _onNextQuestion(ev) {
        ev.preventDefault();
        this._saveCurrentResponse();
        this._renderQuestion(this.currentQuestionIndex + 1);
    },

    /**
     * Submit quiz
     */
    async _onSubmitQuiz(ev) {
        ev.preventDefault();
        
        if (!confirm('Are you sure you want to submit your quiz? You cannot change your answers after submission.')) {
            return;
        }
        
        // Save current response first
        await this._saveCurrentResponse();
        
        // Submit quiz
        try {
            const result = await rpc('/slides/rto_quiz/submit', {
                attempt_id: this.attemptId,
            });
            
            if (result.error) {
                this._showError(result.error);
                return;
            }
            
            // Show results
            this._showResults(result.results);
        } catch (error) {
            console.error('Failed to submit quiz:', error);
            this._showError('Failed to submit quiz. Please try again.');
        }
    },

    /**
     * Show quiz results
     */
    _showResults(results) {
        const passed = results.passed;
        const percentage = Math.round(results.percentage * 10) / 10;
        
        const resultHtml = `
            <div class="card shadow-sm">
                <div class="card-body text-center p-5">
                    <div class="mb-4">
                        <i class="fa ${passed ? 'fa-check-circle text-success' : 'fa-times-circle text-danger'}" 
                           style="font-size: 4rem;"></i>
                    </div>
                    <h2 class="mb-3">${passed ? 'Congratulations!' : 'Quiz Completed'}</h2>
                    <p class="lead mb-4">
                        You scored <strong>${results.score} out of ${results.max_score}</strong> points (${percentage}%)
                    </p>
                    <div class="alert ${passed ? 'alert-success' : 'alert-warning'}">
                        <strong>${passed ? 'You passed!' : 'You did not pass this time.'}</strong><br>
                        Pass threshold: ${results.pass_threshold}%
                    </div>
                    <div class="mt-4">
                        <button class="btn btn-primary" onclick="location.reload()">
                            <i class="fa fa-refresh"/> Try Again
                        </button>
                        <a href="/slides/${this.quizData.id}" class="btn btn-secondary">
                            <i class="fa fa-arrow-left"/> Back to Course
                        </a>
                    </div>
                </div>
            </div>
        `;
        
        $('#rto_quiz_interface').html(resultHtml);
    },

    /**
     * Show error message
     */
    _showError(message) {
        const errorHtml = `
            <div class="alert alert-danger alert-dismissible fade show" role="alert">
                <i class="fa fa-exclamation-triangle"/> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        $('#rto_quiz_question_container').prepend(errorHtml);
    },
});

export default publicWidget.registry.RTOQuizPortal;
