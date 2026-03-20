// import { Component, useState, useRef, onMounted } from "@odoo/owl";
// import { TodoItem } from "./TodoItem.js";

// export class TodoList extends Component {
//     static template = "hospital.TodoList";
//     static components = { TodoItem };

//     setup() {
//         this.todos = useState([]);
//         this.nextId = 1;//every item give number 1,2,3,4

//         // when dashboard load cursor focus
//         this.inputRef = useRef("todoInput");
//         onMounted(() => {
//             this.inputRef.el.focus();
//         });
//     }

//     // add todolist enter
//     addTodo(ev) {
//         if (ev.keyCode === 13 && ev.target.value.trim() !== "") {
//             this.todos.push({
//                 id: this.nextId++,//give id and count +
//                 description: ev.target.value,//input
//                 isCompleted: false,
//             });
//             ev.target.value = "";//input box empty after add list
//         }
//     }

    
//     toggleState(todoId) {
//         const todo = this.todos.find((t) => t.id === todoId);
//         if (todo) {
//             todo.isCompleted = !todo.isCompleted;
//         }
//     }

//     // task list remove
//     removeTodo(todoId) {
//         const index = this.todos.findIndex((t) => t.id === todoId);
//         if (index >= 0) {
//             this.todos.splice(index, 1);
//         }
//     }
// }


import { Component, useState, useRef, onMounted, onWillStart } from "@odoo/owl";
import { TodoItem } from "./TodoItem.js";
import { useService } from "@web/core/utils/hooks"; 
export class TodoList extends Component {
    static template = "hospital.TodoList";
    static components = { TodoItem };

    setup() {
        this.orm = useService("orm"); 
        this.todos = useState([]);
        this.inputRef = useRef("todoInput");

     
        onWillStart(async () => {
            const records = await this.orm.searchRead("hospital.todo", [], ["description", "is_completed"]);
            this.todos.push(...records);
        });

        onMounted(() => {
            this.inputRef.el.focus();
        });
    }

    //record create in db
    async addTodo(ev) {
    if (ev.keyCode === 13 && ev.target.value.trim() !== "") {
        const description = ev.target.value;
        
        const result = await this.orm.create("hospital.todo", [{
            description: description,
            is_completed: false,
        }]);
        
        const newId = result[0]; 

        this.todos.push({
            id: newId, 
            description: description,
            is_completed: false,
        });

        ev.target.value = ""; 
    }
}
    

    async toggleState(todoId) {
        const todo = this.todos.find((t) => t.id === todoId);
        if (todo) {
            // Database Write 
            await this.orm.write("hospital.todo", [todoId], {
                is_completed: !todo.is_completed,
            });
            todo.is_completed = !todo.is_completed;
        }
    }

    async removeTodo(todoId) {
        // Database  Unlink 
        await this.orm.unlink("hospital.todo", [todoId]);
        
        const index = this.todos.findIndex((t) => t.id === todoId);
        if (index >= 0) {
            this.todos.splice(index, 1);
        }
    }
}