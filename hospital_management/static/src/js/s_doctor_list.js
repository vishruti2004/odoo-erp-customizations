/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.s_doctor_list = publicWidget.Widget.extend({
    selector: '.s_doctor_list',

    start: function () {
        this._filterDoctors();
        return this._super.apply(this, arguments);
    },

    _filterDoctors: function () {
        const specId = this.$el.data('specialization') || 'all';
        const $items = this.$('.doctor-card-item');

        if (specId === 'all') {
            $items.removeClass('d-none');
        } else {
            $items.addClass('d-none');
            this.$(`.doctor-card-item[data-specialization='${specId}']`).removeClass('d-none');
        }
    },
});