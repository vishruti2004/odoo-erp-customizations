import { Component } from "@odoo/owl";

export class Card extends Component {
    static template = "hospital.Card";


      static props = {
        title: String,
        content: String,
    };
}