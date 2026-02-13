/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import Fullscreen from "@website_slides/js/slides_course_fullscreen_player";

console.log('[RTO LMS] Assignment patch loading...');

/**
 * Patch the Fullscreen class to support 'assignment' slide category
 * This allows assignment slides to display properly in fullscreen mode
 */
patch(Fullscreen.prototype, {
        setup() {
            super.setup(...arguments);
            console.log('[Assignment Patch] Setup called');
        },
        /**
         * Override to include 'assignment' category for HTML content fetching
         */
        async _fetchSlideContent() {
            const slide = this._slideValue;
            if ((slide.category === 'article' || slide.category === 'assignment') && !slide.isQuiz) {
                console.log('[Assignment] Fetching HTML content for slide:', slide.id);
                const result = await this._fetchHtmlContent();
                console.log('[Assignment] HTML content fetched, length:', slide.htmlContent ? slide.htmlContent.length : 0);
                return result;
            }
            return Promise.resolve();
        },

        /**
         * Override to include 'assignment' in auto-complete categories
         */
        _preprocessSlideData(slidesDataList) {
            console.log('[Assignment] _preprocessSlideData called with', slidesDataList.length, 'slides');
            const result = super._preprocessSlideData(...arguments);

            result.forEach(function (slideData) {
                console.log('[Assignment] Processing slide:', slideData.id, 'category:', slideData.category);
                // Override auto-complete setting for assignment slides
                // Assignments should NOT auto-complete - they require submission and grading
                if (!slideData.hasQuestion && slideData.category === 'assignment') {
                    console.log('[Assignment] Setting _autoSetDone=false for assignment slide:', slideData.id);
                    slideData._autoSetDone = false;  // assignments require submission, not auto-complete
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
                console.log('[Assignment] Rendering slide:', slide.id, 'htmlContent:', slide.htmlContent ? 'exists' : 'missing');
                const $content = this.$('.o_wslides_fs_content');

                // Find the existing assignment content container created by the XML template
                const $wpContainer = $content.find('.o_wslide_fs_article_content');

                if ($wpContainer.length) {
                    console.log('[Assignment] Using existing container');
                    // Use existing container from XML template
                    $wpContainer.html(slide.htmlContent || '<div class="alert alert-warning">No assignment content loaded</div>');
                } else {
                    console.log('[Assignment] Creating new container');
                    // Fallback: create container if template didn't (shouldn't happen)
                    $content.empty();
                    const $newContainer = $('<div>').addClass('o_wslide_fs_article_content bg-white block w-100 overflow-auto p-3');
                    $newContainer.html(slide.htmlContent || '<div class="alert alert-warning">No assignment content loaded</div>');
                    $content.append($newContainer);
                }

                this.trigger_up('widgets_start_request', {
                    $target: $content,
                });
                return;
            }

            // Call parent for all other categories
            return super._renderSlide(...arguments);
        },
    });
