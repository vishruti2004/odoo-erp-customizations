/** @odoo-module **/
import { DynamicSnippet } from "@website/snippets/s_dynamic_snippet/dynamic_snippet";
import { registry } from "@web/core/registry";

import { groupBy } from "@web/core/utils/arrays";

export class DoctorList extends DynamicSnippet {
    // While the selector has 'upcoming_snippet' in its name, it now has a filter
    // option to include ongoing events. The name is kept for backward compatibility.
    static selector = ".s_doctor_list";

    /**
     * @override
     */
    getSearchDomain() {
        let searchDomain = super.getSearchDomain(...arguments);
        const filterByTagIds = this.el.dataset.filterByTagIds;
        if (filterByTagIds) {
            let tagGroupedByCategory = groupBy(JSON.parse(filterByTagIds), "category_id");
            for (const category in tagGroupedByCategory) {
                searchDomain = searchDomain.concat(
                    [["tag_ids", "in", tagGroupedByCategory[category].map(e => e.id)]]);
            }
        }
        return searchDomain;
    }
}

registry
    .category("public.interactions")
    .add("hospital_management", DoctorList);

registry
    .category("public.interactions.edit")
    .add("hospital_management.DoctorList", {
        Interaction: DoctorList,
    });



// import publicWidget from "@web/legacy/js/public/public_widget";
// publicWidget.registry.s_doctor_list = publicWidget.Widget.extend({
//     selector: '.s_doctor_list', 

//     start: function () {
//         this._filterDoctors();
//         return this._super.apply(this, arguments);
//     },

//     _filterDoctors: function () {
//         const $wrapper = this.$('.doctor_option_selector');
//         const specId = $wrapper.data('specialization') || 'all';
//         const cols = $wrapper.data('columns') || '3';
        
//         const $items = this.$('.doctor-card-item');
//         const $grid = this.$('.doctor-grid');

//         if (specId === 'all') {
//             $items.removeClass('d-none');
//         } else {
//             $items.addClass('d-none');
//             this.$(`.doctor-card-item[data-specialization='${specId}']`).removeClass('d-none');
//         }

//         if ($grid.length) {
//             const classes = Array.from($grid[0].classList).filter(c => c.startsWith('row-cols-'));
//             $grid.removeClass(classes.join(' '));
//             $grid.addClass(`row-cols-md-${cols} row-cols-1`);
//         }
//     },
// });