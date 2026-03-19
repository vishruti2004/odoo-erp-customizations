import { Component } from "@odoo/owl";

export class TodoItem extends Component {
    static template = "hospital.TodoItem";
    
    // Props validation: check data is true or not from parent to child
    static props = {
        todo: {
            type: Object,
            shape: { id: Number, description: String, is_completed: Boolean },
        },
        toggleState: Function, //when user click on checkbox then the function call and task is completed mark
        removeTodo: Function,  // when user click on delete button click the function remove from list
    };
}