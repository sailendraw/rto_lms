/** @odoo-module **/

import { Quiz } from '@website_slides/js/slides_course_quiz';
import { patch } from "@web/core/utils/patch";
import { markup } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { SlideQuizFinishDialog } from "@website_slides/js/public/components/slide_quiz_finish_dialog/slide_quiz_finish_dialog";

// Patch Quiz widget to use custom template and handle checkbox inputs
patch(Quiz.prototype, {
    template: 'rto_lms.slide.quiz',
    
    async willStart() {
        await super.willStart(...arguments);
    },
    
    async _submitQuiz() {
        // Get MCQ answer IDs (slide_answer IDs from radio/checkbox)
        const answer_ids = this.$('input[type=radio]:checked, input[type=checkbox]:checked').map(function () {
            return parseInt($(this).val());
        }).get();
        
        // Collect text-based question responses (question_id: value pairs)
        const text_answers = {};
        this.$('input[type=text][data-question-id], input[type=number][data-question-id]').each(function() {
            const questionId = parseInt($(this).data('question-id'));
            if (questionId) {
                text_answers[questionId] = $(this).val() || '';
            }
        });
        
        // Call backend
        const data = await rpc('/slides/slide/quiz/submit', {
            slide_id: this.slide.id,
            answer_ids: answer_ids,
            text_answers: text_answers,
        });
        
        if (data.error) {
            this._showErrorMessage(data.error);
            return;
        } else {
            this._hideErrorMessage();
        }
        
        Object.assign(this.quiz, data);
        const {rankProgress, completed, channel_completion: completion} = this.quiz;
        
        // Store student's text answers in quiz.questions for display
        if (data.text_answers) {
            this.quiz.questions.forEach(question => {
                if (data.text_answers[question.id] !== undefined) {
                    question.student_answer = data.text_answers[question.id];
                }
            });
        }
        
        // Handle markup for rank progress (using parent's method)
        if ('description' in rankProgress) {
            rankProgress['description'] = markup(rankProgress['description'] || '');
            rankProgress['previous_rank']['motivational'] =
                markup(rankProgress['previous_rank']['motivational'] || '');
            rankProgress['new_rank']['motivational'] =
                markup(rankProgress['new_rank']['motivational'] || '');
        }
        
        if (completed) {
            this._disableAnswers();
            this.call("dialog", "add", SlideQuizFinishDialog, {
                quiz: this.quiz,
                hasNext: this.slide.hasNext,
                onClickNext: (ev) => this._onClickNext(ev),
                userId: this.userId,
            });
            this.slide.completed = true;
            this.trigger_up('slide_completed', {
                slideId: this.slide.id,
                channelCompletion: completion,
                completed: true,
            });
        }
        
        this._hideEditOptions();
        this._renderAnswersHighlightingAndComments();
        this._renderValidationInfo();
        this._toggleAdditionalResourceInfo(!completed);
    },
    
    // Keep _getQuizAnswers returning array for compatibility with parent class
    // (used by session saving). Text answers handled separately in _submitQuiz.

    
    _disableAnswers() {
        const self = this;
        this.$('.o_wslides_js_lesson_quiz_question').addClass('completed-disabled');
        this.$('input[type=radio], input[type=checkbox]').each(function () {
            $(this).prop('disabled', self.slide.completed);
        });
    },
    
    _renderAnswersHighlightingAndComments() {
        const self = this;
        if (!self.quiz || !self.quiz.answers) {
            return;
        }
        
        this.$('.o_wslides_js_lesson_quiz_question').each(function () {
            const $question = $(this);
            const questionId = $question.data('questionId');
            
            if (!self.quiz.answers[questionId]) {
                return;
            }
            
            const isCorrect = self.quiz.answers[questionId].is_correct;
            
            // Handle MCQ-style questions (radio/checkbox answers)
            $question.find('a.o_wslides_quiz_answer').each(function () {
                const $answer = $(this);
                $answer.find('i.fa').addClass('d-none');
                
                // Check both radio and checkbox inputs
                const $input = $answer.find('input[type=radio], input[type=checkbox]');
                if ($input[0] && $input[0].checked) {
                    if (isCorrect) {
                        $answer.removeClass('list-group-item-danger').addClass('list-group-item-success');
                        $answer.find('i.fa-check-circle, i.fa-check-square').removeClass('d-none');
                    } else {
                        $answer.removeClass('list-group-item-success').addClass('list-group-item-danger');
                        $answer.find('i.fa-times-circle').removeClass('d-none');
                        $input.prop('checked', false);
                    }
                } else {
                    $answer.removeClass('list-group-item-danger list-group-item-success');
                    $answer.find('i.fa-circle, i.fa-square-o').removeClass('d-none');
                }
            });
            
            // Handle text-based questions (short_answer, numerical)
            const $textInput = $question.find('input[type=text][data-question-id], input[type=number][data-question-id]');
            
            if ($textInput.length > 0) {
                const $container = $textInput.closest('.list-group-item');
                
                // Remove existing result indicators
                $container.find('.o_wslides_quiz_text_result').remove();
                
                // Add visual feedback for correctness
                if (isCorrect) {
                    $container.removeClass('list-group-item-danger').addClass('list-group-item-success');
                    $textInput.removeClass('is-invalid').addClass('is-valid');
                    
                    // Add success indicator
                    $textInput.after(`
                        <div class="o_wslides_quiz_text_result mt-2 text-success">
                            <i class="fa fa-check-circle"></i> <strong>Correct!</strong>
                        </div>
                    `);
                } else {
                    $container.removeClass('list-group-item-success').addClass('list-group-item-danger');
                    $textInput.removeClass('is-valid').addClass('is-invalid');
                    
                    // Add error indicator
                    $textInput.after(`
                        <div class="o_wslides_quiz_text_result mt-2 text-danger">
                            <i class="fa fa-times-circle"></i> <strong>Incorrect</strong>
                        </div>
                    `);
                }
            }
            
            const comment = self.quiz.answers[questionId].comment;
            if (comment) {
                $question.find('.o_wslides_quiz_answer_info').removeClass('d-none');
                $question.find('.o_wslides_quiz_answer_comment').text(comment);
            }
        });
    },
    
    _applySessionAnswers() {
        if (!this.slide.sessionAnswers || this.slide.sessionAnswers.length === 0) {
            return;
        }

        const self = this;
        this.$('.o_wslides_js_lesson_quiz_question').each(function () {
            const $question = $(this);
            $question.find('a.o_wslides_quiz_answer').each(function () {
                const $answer = $(this);
                const $input = $answer.find('input[type=radio], input[type=checkbox]');
                if (!$input[0].checked && self.slide.sessionAnswers.includes($answer.data('answerId'))) {
                    $input.prop('checked', true);
                }
            });
        });

        // reset answers coming from the session
        this.slide.sessionAnswers = false;
    },
    
    _onAnswerClick(ev) {
        ev.preventDefault();
        const $answer = $(ev.currentTarget);
        
        // Skip click handling for text/number/textarea inputs - they handle themselves
        if ($(ev.target).is('input[type=text], input[type=number], textarea')) {
            return;
        }
        
        if (!this.slide.completed && this.isMember) {
            // Handle checkbox for multiple choice questions
            const $checkbox = $answer.find('input[type=checkbox]');
            const $radio = $answer.find('input[type=radio]');
            
            if ($checkbox.length > 0) {
                // Toggle checkbox state
                const isChecked = $checkbox.prop('checked');
                $checkbox.prop('checked', !isChecked);
                
                // Toggle visual icon
                const $icon = $answer.find('i.fa-square-o, i.fa-check-square-o');
                if (!isChecked) {
                    // Was unchecked, now checked - show checked icon
                    $icon.removeClass('fa-square-o').addClass('fa-check-square-o');
                } else {
                    // Was checked, now unchecked - show unchecked icon
                    $icon.removeClass('fa-check-square-o').addClass('fa-square-o');
                }
            } else if ($radio.length > 0) {
                // Handle radio button for single choice and true/false
                const radioName = $radio.attr('name');
                const $question = $answer.closest('.o_wslides_js_lesson_quiz_question');
                
                // Uncheck all radio buttons in this question first
                $question.find(`input[type=radio][name="${radioName}"]`).prop('checked', false);
                
                // Check the clicked radio button
                $radio.prop('checked', true);
            }
        }
    },
});
