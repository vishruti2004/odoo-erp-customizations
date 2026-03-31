odoo.define('hospital_management.doctor_snippet', function (require) {
    'use strict';

    var options = require('web_editor.snippets.options');
    var ajax = require('web.ajax');

    options.registry.doctor_specialization = options.Class.extend({
        init: function () {
            this._super.apply(this, arguments);
            var self = this;
            
            this.$el.find('select[name="specialization_id"]').on('change', function () {
                var specializationId = $(this).val();
                self.applyChanges(specializationId);
            });
        },

        applyChanges: function (specializationId) {
            var self = this;
            var $snippet = this.$target;
            
            $snippet.attr('data-specialization-id', specializationId);
            
            ajax.jsonRpc('/hospital/get_doctors', 'call', {
                'specialization_id': parseInt(specializationId)
            }).then(function (doctors) {
                self.renderDoctors($snippet, doctors);
            });
        },

        renderDoctors: function ($snippet, doctors) {
            var $holder = $snippet.find('.js_doctor_holder');
            
            if (!doctors || doctors.length === 0) {
                $holder.html('<div class="col-12 text-center text-muted">No doctors found for this specialization.</div>');
                return;
            }
            
            var html = '';
            for (var i = 0; i < doctors.length; i++) {
                var doc = doctors[i];
                html += '<div class="col-md-4 mb-4">' +
                            '<div class="card shadow-sm">' +
                                (doc.image ? '<img src="' + doc.image + '" class="card-img-top" style="height: 200px; object-fit: cover;"/>' : '') +
                                '<div class="card-body text-center">' +
                                    '<h5 class="card-title">' + doc.name + '</h5>' +
                                    '<p class="card-text text-primary">' + doc.specialization_name + '</p>' +
                                '</div>' +
                            '</div>' +
                        '</div>';
            }
            $holder.html(html);
        },

        onBuilt: function () {
            var specializationId = this.$target.attr('data-specialization-id') || 0;
            this.applyChanges(specializationId);
        }
    });
});