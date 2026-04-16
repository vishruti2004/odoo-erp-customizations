/** @odoo-module **/
import { Component } from "@odoo/owl";

export class DeliveryBoyLine extends Component {
    static template = "point_of_sale.DeliveryBoyLine";
    static props = ["boy", "isSelected", "onClickDeliveryBoy"];
}