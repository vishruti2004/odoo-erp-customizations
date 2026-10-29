# -*- coding: utf-8 -*-

import json
import logging
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound
from odoo.http import content_disposition, request, route, serialize_exception
from odoo.tools import osutil
from odoo.addons.web.controllers.export import CSVExport

_logger = logging.getLogger(__name__)

class CSVExport(CSVExport):

    @route("/advanced_chatter/export/csv", type="http", auth="user")
    def advanced_chatter_export_csv(self, data):
        params = json.loads(data)
        request.update_context(**params.get("context", {}))
        thread_model = params.get("thread_model")
        try:
            thread_id = int(params.get("thread_id"))
        except (TypeError, ValueError):
            raise BadRequest()
        if (
            thread_model not in request.env
            or not hasattr(request.env[thread_model], "_get_advanced_chatter_export")
        ):
            raise BadRequest()
        thread = request.env[thread_model].browse(thread_id)._advanced_chatter_thread()
        if not thread:
            raise NotFound()
        try:
            headers, rows = thread._get_advanced_chatter_export(
                messages_params=params.get("messages"),
                activity_ids=params.get("activity_ids"),
            )
            model_name = request.env["ir.model"]._get(thread._name).name
            filename = f"{model_name} - {thread.display_name}{self.extension}"
            return request.make_response(
                self.from_data(None, headers, rows),
                headers=[
                    ("Content-Disposition", content_disposition(osutil.clean_filename(filename))),
                    ("Content-Type", self.content_type),
                ],
            )
        except Exception as exc:
            _logger.exception("Exception during request handling.")
            payload = json.dumps({
                "code": 0,
                "message": "Odoo Server Error",
                "data": serialize_exception(exc),
            })
            raise InternalServerError(payload) from exc
