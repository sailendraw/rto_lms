/** @odoo-module **/

import QuestionFormWidget from '@website_slides/js/slides_course_quiz_question_form';
import { Quiz } from '@website_slides/js/slides_course_quiz';
import { patch } from "@web/core/utils/patch";

// Patch QuestionFormWidget to handle question_type
patch(QuestionFormWidget.prototype, {
    init(parent, options) {
        super.init(...arguments);
        this.questionType = options.questionType || 'multiple_choice_single';
    },
    
    _serializeForm($form) {
        const result = super._serializeForm($form);
        result.question_type = this.questionType;
        return result;
    },
});

// Patch Quiz widget to capture question type from dropdown
patch(Quiz.prototype, {
    _onCreateQuizClick(ev) {
        let questionType = 'multiple_choice_single';
        
        // If event exists and it's a question button, get the type
        if (ev && ev.currentTarget) {
            const $target = $(ev.currentTarget);
            if ($target.hasClass('o_wslides_js_quiz_add_question')) {
                questionType = $target.data('question-type') || 'multiple_choice_single';
            }
        }
        
        // Create the question form
        const $elem = this.$('.o_wslides_js_lesson_quiz_new_question');
        this.$('.o_wslides_js_quiz_add').addClass('d-none');
        new QuestionFormWidget(this, {
            slideId: this.slide.id,
            sequence: this.quiz.questionsCount + 1,
            questionType: questionType,
        }).appendTo($elem);
    },
});

