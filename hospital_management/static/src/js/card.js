import { Component } from "@odoo/owl";

export class Card extends Component {
    static template = "hospital_management.Card";
    static props = {
        label: String,
        value: { type: [Number, String] },
        icon: String,
        bgClass: String,
        onClick: { type: Function, optional: true }, 
    };
}