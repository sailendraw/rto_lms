/** @odoo-module **/

import { SlideUploadDialog } from '@website_slides/js/public/components/slide_upload_dialog/slide_upload_dialog';
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

// Patch SlideUploadDialog to add Assignment category
patch(SlideUploadDialog, {
    categoryData: {
        ...SlideUploadDialog.categoryData,
        assignment: { icon: "fa-tasks", label: _t("Assignment") },
    },
    pagesTemplates: {
        ...SlideUploadDialog.pagesTemplates,
        assignment: "rto_lms.SlideCategoryTutorial.Assignment",
    },
});
