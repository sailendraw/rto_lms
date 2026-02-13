/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import Fullscreen from "@website_slides/js/slides_course_fullscreen_player";

/**
 * Patch the Fullscreen class to support 'assignment' slide category
 * This allows assignment slides to display properly in fullscreen mode
 */
patch(Fullscreen.prototype, {
        /**
         * Override to include 'assignment' category for HTML content fetching
         */
        _fetchSlideContent() {
            const slide = this._slideValue;
            if ((slide.category === 'article' || slide.category === 'assignment') && !slide.isQuiz) {
                return this._fetchHtmlContent();
            }
            return Promise.resolve();
        },

        /**
         * Override to include 'assignment' in auto-complete categories
         */
        _preprocessSlideData(slidesDataList) {
            const result = super._preprocessSlideData(...arguments);

            result.forEach(function (slideData) {
                // Override auto-complete setting for assignment slides
                if (!slideData.hasQuestion && slideData.category === 'assignment') {
                    slideData._autoSetDone = true;  // assignments are marked as completed when opened
                }
            });

            return result;
        },

        /**
         * Override to add rendering logic for 'assignment' category
         */
        async _renderSlide() {
            const slide = this._slideValue;

            // Handle assignment category like article - render HTML content
            if (slide.category === 'assignment' && !slide.isQuiz) {
                const $content = this.$('.o_wslides_fs_content');
                $content.empty();

                const $wpContainer = $('<div>').addClass('o_wslide_fs_article_content bg-white block w-100 overflow-auto p-3');
                $wpContainer.html(slide.htmlContent);
                $content.append($wpContainer);
                this.trigger_up('widgets_start_request', {
                    $target: $content,
                });
                return;
            }

            // Call parent for all other categories
            return super._renderSlide(...arguments);
        },
    });
