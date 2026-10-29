import "@mail/chatter/web/form_compiler";

import { registry } from "@web/core/registry";
import { evaluateExpr } from "@web/core/py_js/py";
import { setAttributes } from "@web/core/utils/xml";

const formCompilers = registry.category("form_compilers");
const chatterCompiler = formCompilers.get("chatter_compiler");

function compileChatter(node, params) {
    const result = chatterCompiler.fn.call(this, node, params);
    const options = node.getAttribute("options");
    const chatter = options && result?.querySelector("t[t-component='__comp__.mailComponents.Chatter']");
    if (!chatter) {
        return result;
    }
    const { advance_search, advance_filter } = evaluateExpr(options);
    if (advance_search !== undefined) {
        setAttributes(chatter, { advancesearch: advance_search ? "true" : "false" });
    }
    if (advance_filter !== undefined) {
        setAttributes(chatter, { advancefilter: advance_filter ? "true" : "false" });
    }
    return result;
}

formCompilers.add("chatter_compiler", { ...chatterCompiler, fn: compileChatter }, { force: true });
