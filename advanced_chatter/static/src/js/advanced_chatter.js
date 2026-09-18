/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { Thread } from "@mail/core/common/thread";
import { SearchMessageInput } from "@mail/core/common/search_message_input";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState } from "@odoo/owl";


patch(Chatter.prototype,{
    get childSubEnv(){
        return {...super.childSubEnv,advancedChatterSearch:this};
    },
    setup(){
        super.setup(...arguments);
        this.orm=useService("orm");
        this.messageTypeOptions=[
            {value:"comment",label:"Comment"},
            {value:"email",label:"Incoming Email"},
            {value:"email_outgoing",label:"Outgoing Email"},
            {value:"notification",label:"System Notification"},
            {value:"auto_comment",label:"Automated Targeted Notification"},
        ];
        this.searchSuggestionDefinitions=[
            {key:"message",label:"Message",icon:"fa fa-search",expandable:false},
            {key:"product",label:"Product",icon:"fa fa-cube",expandable:true},
            {key:"author",label:"Author",icon:"fa fa-user",expandable:true},
            {key:"messageType",label:"Message Type",icon:"fa fa-envelope-o",expandable:true},
            {key:"subtype",label:"Message Subtype",icon:"fa fa-tag",expandable:true},
        ];
        this.advancedFilterState=useState({
            showAdvancedFilters:false,
            showSuggestions:false,
            expandedSuggestionGroup:null,
            applied:false,
            searching:false,
            filters:{
                keyword:"",
                activeKeyword:"",
                activeKeywordMode:"",
                dateFrom:"",
                dateTo:"",
                userId:"",
                authorKeyword:"",
                messageType:"",
                subtypeId:"",
                productId:"",
                productKeyword:"",
                activityTypeId:"",
                activityUserId:"",
                activityState:"",
            },
            subtypes:[],
            activityTypes:[],
        });
        onWillStart(async()=>{
            this.advancedFilterState.subtypes=await this.orm.searchRead(
                "mail.message.subtype",
                [],
                ["id","name"],
                {limit:200,order:"name asc"}
            );
            this.advancedFilterState.activityTypes=await this.orm.searchRead(
                "mail.activity.type",
                [],
                ["id","name"],
                {limit:200,order:"name asc"}
            );
        });
    },
    get threadMessages(){
        return this.state.thread?.messages||this.state.thread?.orderedMessages||[];
    },
    get conversationAuthors(){
        const seen=new Set();
        const authors=[];
        for(const message of this.threadMessages){
            const author=message.author;
            if(!author?.id||seen.has(author.id)){
                continue;
            }
            seen.add(author.id);
            authors.push({id:author.id,name:author.name||""});
        }
        authors.sort((a,b)=>a.name.localeCompare(b.name));
        return authors;
    },
    get conversationMessageTypes(){
        const seen=new Set();
        for(const message of this.threadMessages){
            if(message.message_type){
                seen.add(message.message_type);
            }
        }
        return this.messageTypeOptions.filter(type=>seen.has(type.value));
    },
    get conversationSubtypes(){
        const seen=new Set();
        for(const message of this.threadMessages){
            const subtypeId=message.subtype_id?.id??message.subtype_id;
            if(subtypeId){
                seen.add(Number(subtypeId));
            }
        }
        return this.advancedFilterState.subtypes.filter(subtype=>seen.has(Number(subtype.id)));
    },
    get conversationActivities(){
        return this.state.thread?.activities||[];
    },
    get activities(){
        const activities=this.state.thread?.activities||[];
        const filters=this.advancedFilterState.filters;
        if(!filters.activityTypeId&&!filters.activityUserId&&!filters.activityState&&!filters.dateFrom&&!filters.dateTo){
            return activities;
        }
        return activities.filter(activity=>{
            const typeId=this.getMany2OneValue(activity.activity_type_id).id;
            const userId=this.getMany2OneValue(activity.user_id).id;
            const activityDate=activity.date_deadline||"";
            if(filters.dateFrom&&(!activityDate||activityDate<filters.dateFrom)){
                return false;
            }
            if(filters.dateTo&&(!activityDate||activityDate>filters.dateTo)){
                return false;
            }
            if(filters.activityTypeId&&Number(typeId)!==Number(filters.activityTypeId)){
                return false;
            }
            if(filters.activityUserId&&Number(userId)!==Number(filters.activityUserId)){
                return false;
            }
            if(filters.activityState&&activity.state!==filters.activityState){
                return false;
            }
            return true;
        });
    },
    get isActivityFilterActive(){
        const f=this.advancedFilterState.filters;
        return !!(f.activityTypeId||f.activityUserId||f.activityState);
    },
    getMany2OneValue(value){
        if(Array.isArray(value)){
            return {id:value[0]||null,name:value[1]||""};
        }
        if(value&&typeof value==="object"){
            return {
                id:value.id||value.res_id||null,
                name:value.display_name||value.name||"",
            };
        }
        return {id:value||null,name:""};
    },
    get conversationActivityTypes(){
        const seen=new Set();
        const result=[];
        for(const activity of this.conversationActivities){
            const value=this.getMany2OneValue(activity.activity_type_id);
            if(!value.id||seen.has(Number(value.id))){
                continue;
            }
            seen.add(Number(value.id));
            result.push({id:Number(value.id),name:value.name||""});
        }
        result.sort((a,b)=>a.name.localeCompare(b.name));
        return result;
    },
    get conversationActivityUsers(){
        const seen=new Set();
        const result=[];
        for(const activity of this.conversationActivities){
            const value=this.getMany2OneValue(activity.user_id);
            if(!value.id||seen.has(Number(value.id))){
                continue;
            }
            seen.add(Number(value.id));
            result.push({id:Number(value.id),name:value.name||""});
        }
        result.sort((a,b)=>a.name.localeCompare(b.name));
        return result;
    },
    get conversationActivityStates(){
        const states=[
            {value:"overdue",label:"Overdue"},
            {value:"today",label:"Today"},
            {value:"planned",label:"Planned"},
        ];
        const seen=new Set(
            this.conversationActivities
                .map(activity=>activity.state)
                .filter(Boolean)
        );
        return states.filter(state=>seen.has(state.value));
    },
    get conversationProducts(){
        const seen=new Set();
        const products=[];
        const addProduct=(defaultCode,rawName)=>{
            const name=rawName.trim().replace(/\s+/g," ");
            if(!name){
                return;
            }
            const key=`${defaultCode}|${name}`.toLowerCase();
            if(seen.has(key)){
                return;
            }
            seen.add(key);
            products.push({
                id:`chatter-product-${products.length+1}`,
                name,
                default_code:defaultCode,
                searchText:`${defaultCode} ${name}`.toLowerCase(),
            });
        };
        for(const message of this.threadMessages){
            const text=`${this.getMessageText(message.subject)} ${this.getMessageText(message.body)}`;
            const matches=[...text.matchAll(/\[([^\]]+)\]\s*([^\[\]\n<]+)/g)];
            for(const match of matches){
                addProduct(match[1].trim(),match[2]);
            }
            const extraMatches=[...text.matchAll(/Extra line with\s+([^\[\]\n<]+)/gi)];
            for(const match of extraMatches){
                addProduct("",match[1]);
            }
        }
        return products;
    },
    get searchSuggestionGroups(){
        const keyword=this.advancedFilterState.filters.keyword.trim();
        if(!keyword){
            return [];
        }
        const groups=[];
        for(const definition of this.searchSuggestionDefinitions){
            if(definition.key==="message"){
                groups.push({...definition,items:[],expandable:false});
                continue;
            }
            const items=this.getSuggestionItems(definition.key);
            if(!items.length){
                continue;
            }
            groups.push({...definition,items,expandable:items.length>1});
        }
        return groups;
    },
    getSuggestionItems(key){
        switch(key){
            case"product":
                return this.matchingProductSuggestions;
            case"author":
                return this.matchingAuthorSuggestions;
            case"messageType":
                return this.matchingMessageTypeSuggestions;
            case"subtype":
                return this.matchingSubtypeSuggestions;
            default:
                return [];
        }
    },
    get matchingProductSuggestions(){
        const term=this.advancedFilterState.filters.keyword.trim().toLowerCase();
        if(!term){
            return [];
        }
        return this.conversationProducts.filter(product=>
            product.name.toLowerCase().includes(term)||
            product.default_code.toLowerCase().includes(term)
        ).slice(0,2);
    },
    get matchingAuthorSuggestions(){
        const term=this.advancedFilterState.filters.keyword.trim().toLowerCase();
        if(!term){
            return [];
        }
        return this.conversationAuthors.filter(user=>
            user.name.toLowerCase().includes(term)
        ).slice(0,5);
    },
    get matchingMessageTypeSuggestions(){
        const term=this.advancedFilterState.filters.keyword.trim().toLowerCase();
        if(!term){
            return [];
        }
        return this.conversationMessageTypes.filter(type=>
            type.label.toLowerCase().includes(term)
        ).slice(0,5);
    },
    get matchingSubtypeSuggestions(){
        const term=this.advancedFilterState.filters.keyword.trim().toLowerCase();
        if(!term){
            return [];
        }
        return this.conversationSubtypes.filter(subtype=>
            subtype.name.toLowerCase().includes(term)
        ).slice(0,5);
    },
    toggleAdvancedFilters(){
        this.advancedFilterState.showAdvancedFilters=!this.advancedFilterState.showAdvancedFilters;
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    onKeywordInput(ev){
        this.advancedFilterState.filters.keyword=ev.target.value;
        this.advancedFilterState.showSuggestions=!!ev.target.value.trim();
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    onKeywordFocus(){
        if(this.advancedFilterState.filters.keyword.trim()){
            this.advancedFilterState.showSuggestions=true;
        }
    },
    clearKeywordSearch(){
        this.advancedFilterState.filters={
            keyword:"",
            activeKeyword:"",
            activeKeywordMode:"",
            dateFrom:"",
            dateTo:"",
            userId:"",
            authorKeyword:"",
            messageType:"",
            subtypeId:"",
            productId:"",
            productKeyword:"",
            activityTypeId:"",
            activityUserId:"",
            activityState:"",
        };
        this.advancedFilterState.applied=false;
        this.advancedFilterState.searching=false;
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    onKeywordBlur(){
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    onKeywordKeydown(ev){
        if(ev.key==="Enter"){
            const keyword=this.advancedFilterState.filters.keyword.trim();
            if(!keyword){
                return;
            }
            this.advancedFilterState.filters.activeKeyword=keyword;
            this.advancedFilterState.filters.activeKeywordMode="message";
            this.advancedFilterState.filters.authorKeyword="";
            this.advancedFilterState.filters.productId="";
            this.advancedFilterState.filters.productKeyword="";
            this.advancedFilterState.showSuggestions=false;
            this.advancedFilterState.expandedSuggestionGroup=null;
        }
        if(ev.key==="Escape"){
            this.advancedFilterState.showSuggestions=false;
            this.advancedFilterState.expandedSuggestionGroup=null;
        }
    },
    toggleSuggestionGroup(groupKey){
        this.advancedFilterState.expandedSuggestionGroup=
            this.advancedFilterState.expandedSuggestionGroup===groupKey?null:groupKey;
    },
    selectSearchSuggestion(group,item=null){
        switch(group.key){
            case"message":
                this.selectMessageSuggestion();
                break;
            case"product":
                if(item){
                    this.selectProductSuggestion(item);
                }
                break;
            case"author":
                if(item){
                    this.selectAuthorSuggestion(item);
                }else{
                    this.selectAuthorGroupSuggestion();
                }
                break;
            case"messageType":
                if(item){
                    this.selectMessageTypeSuggestion(item);
                }
                break;
            case"subtype":
                if(item){
                    this.selectSubtypeSuggestion(item);
                }
                break;
        }
    },
    selectMessageSuggestion(){
        const keyword=this.advancedFilterState.filters.keyword.trim();
        if(!keyword){
            return;
        }
        this.advancedFilterState.filters.activeKeyword=keyword;
        this.advancedFilterState.filters.activeKeywordMode="message";
        this.advancedFilterState.filters.authorKeyword="";
        this.advancedFilterState.filters.productId="";
        this.advancedFilterState.filters.productKeyword="";
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    selectAuthorSuggestion(user){
        this.advancedFilterState.filters.keyword=user.name;
        this.advancedFilterState.filters.activeKeyword=user.name;
        this.advancedFilterState.filters.activeKeywordMode="author";
        this.advancedFilterState.filters.userId=String(user.id);
        this.advancedFilterState.filters.authorKeyword=user.name;
        this.advancedFilterState.filters.productId="";
        this.advancedFilterState.filters.productKeyword="";
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    selectAuthorGroupSuggestion(){
        const keyword=this.advancedFilterState.filters.keyword.trim();
        if(!keyword){
            return;
        }
        this.advancedFilterState.filters.activeKeyword=keyword;
        this.advancedFilterState.filters.activeKeywordMode="author";
        this.advancedFilterState.filters.userId="";
        this.advancedFilterState.filters.authorKeyword=keyword;
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    selectMessageTypeSuggestion(type){
        this.advancedFilterState.filters.keyword=type.label;
        this.advancedFilterState.filters.activeKeyword=type.label;
        this.advancedFilterState.filters.activeKeywordMode="messageType";
        this.advancedFilterState.filters.messageType=type.value;
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    selectSubtypeSuggestion(subtype){
        this.advancedFilterState.filters.keyword=subtype.name;
        this.advancedFilterState.filters.activeKeyword=subtype.name;
        this.advancedFilterState.filters.activeKeywordMode="subtype";
        this.advancedFilterState.filters.subtypeId=String(subtype.id);
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    selectProductSuggestion(product){
        this.advancedFilterState.filters.keyword=product.name;
        this.advancedFilterState.filters.activeKeyword=product.name;
        this.advancedFilterState.filters.activeKeywordMode="product";
        this.advancedFilterState.filters.productId=product.id;
        this.advancedFilterState.filters.productKeyword=product.default_code;
        this.advancedFilterState.showSuggestions=false;
        this.advancedFilterState.expandedSuggestionGroup=null;
    },
    clearAdvancedFilters(){
        this.clearKeywordSearch();
    },
    applyAdvancedFilters(){
        /* No-op: filteredMessages now reads filter values directly,
           so every change triggers a re-render automatically. */
    },
    get filteredMessages(){
        const messages=this.threadMessages;
        const filters=this.advancedFilterState.filters;

        /* Activity filters active → hide all messages. */
        if(this.isActivityFilterActive){
            return [];
        }

        /* Any filter actually set? If not, show everything. */
        const hasAnyFilter=!!(
            filters.activeKeyword||
            filters.dateFrom||
            filters.dateTo||
            filters.userId||
            filters.authorKeyword||
            filters.messageType||
            filters.subtypeId||
            filters.productKeyword
        );
        if(!hasAnyFilter){
            return messages;
        }

        let result=messages;
        const activeKeyword=(filters.activeKeyword||"").trim().toLowerCase();
        const activeMode=filters.activeKeywordMode||"";
        if(activeKeyword&&activeMode==="message"){
            result=result.filter(message=>{
                const body=this.getMessageText(message.body);
                const subject=this.getMessageText(message.subject);
                return `${subject} ${body}`.toLowerCase().includes(activeKeyword);
            });
        }
        if(activeMode==="author"){
            if(filters.userId){
                result=result.filter(message=>
                    message.author?.id&&Number(message.author.id)===Number(filters.userId)
                );
            }else if(activeKeyword){
                result=result.filter(message=>
                    (message.author?.name||"").toLowerCase().includes(activeKeyword)
                );
            }
        }
        if(activeMode==="product"&&filters.productKeyword){
                const productCode=filters.productKeyword.trim().toLowerCase();
                const productName=(filters.activeKeyword||"").trim().toLowerCase();
                result=result.filter(message=>{
                    const body=this.getMessageText(message.body);
                    const subject=this.getMessageText(message.subject);
                    const text=`${subject} ${body}`.toLowerCase();
                    return (
                        (productCode&&text.includes(`[${productCode}]`))||
                        (productName&&text.includes(productName))
                    );
                });
            }
        if(activeKeyword&&activeMode==="messageType"){
            result=result.filter(message=>{
                const type=this.messageTypeOptions.find(item=>item.value===message.message_type);
                return type?.label.toLowerCase().includes(activeKeyword);
            });
        }
        if(activeKeyword&&activeMode==="subtype"){
            result=result.filter(message=>{
                const subtypeId=message.subtype_id?.id||message.subtype_id;
                const subtype=this.advancedFilterState.subtypes.find(
                    item=>Number(item.id)===Number(subtypeId)
                );
                return subtype?.name.toLowerCase().includes(activeKeyword);
            });
        }
        return result.filter(message=>{
            const messageDate=this.getMessageDate(message);
            if(filters.dateFrom&&(!messageDate||messageDate<filters.dateFrom)){
                return false;
            }
            if(filters.dateTo&&(!messageDate||messageDate>filters.dateTo)){
                return false;
            }
            if(filters.userId){
                const authorId=message.author?.id;
                if(!authorId||Number(authorId)!==Number(filters.userId)){
                    return false;
                }
            }
            if(filters.authorKeyword&&activeMode!=="author"){
                const authorName=(message.author?.name||"").toLowerCase();
                if(!authorName.includes(filters.authorKeyword.trim().toLowerCase())){
                    return false;
                }
            }
            if(filters.messageType&&message.message_type!==filters.messageType){
                return false;
            }
            if(filters.subtypeId){
                const subtypeId=message.subtype_id?.id||message.subtype_id;
                if(Number(subtypeId)!==Number(filters.subtypeId)){
                    return false;
                }
            }
            return true;
        });
    },
    get filteredActivities(){
        return this.activities;
    },
    getMessageDate(message){
        if(!message?.date){
            return null;
        }
        try{
            if(typeof message.date.toISODate==="function"){
                return message.date.toISODate();
            }
            if(typeof message.date==="string"){
                return message.date.substring(0,10);
            }
        }catch{
            return null;
        }
        return null;
    },
    getMessageText(value){
        if(!value){
            return "";
        }
        if(typeof value==="string"){
            const container=document.createElement("div");
            container.innerHTML=value;
            return (container.textContent||container.innerText||"").replace(/<[^>]*>/g," ");
        }
        return String(value).replace(/<[^>]*>/g," ");
    },
    async exportAdvancedResults(){
        const messages=this.filteredMessages||[];
        const activities=this.filteredActivities||[];
        if(!messages.length&&!activities.length){
            return;
        }
        const messageIds=messages
            .map(message=>Number(message.id))
            .filter(id=>Number.isFinite(id)&&id>0);
        const activityIds=activities
            .map(activity=>Number(activity.id))
            .filter(id=>Number.isFinite(id)&&id>0);
        let messageAudit=[];
        let activityAudit=[];
        try{
            [messageAudit,activityAudit]=await Promise.all([
                messageIds.length?this.orm.searchRead(
                    "mail.message",
                    [["id","in",messageIds]],
                    ["id","create_date","create_uid","write_date","write_uid"],
                    {limit:messageIds.length}
                ):[],
                activityIds.length?this.orm.searchRead(
                    "mail.activity",
                    [["id","in",activityIds]],
                    ["id","create_date","create_uid","write_date","write_uid"],
                    {limit:activityIds.length}
                ):[],
            ]);
        }catch{}
        const messageAuditMap=new Map((messageAudit||[]).map(record=>[Number(record.id),record]));
        const activityAuditMap=new Map((activityAudit||[]).map(record=>[Number(record.id),record]));
        const getAuditValue=value=>this.getMany2OneValue(value).name||"";
        const rows=[[
            "ID",
            "Create Date",
            "Created By",
            "Last Updated Date",
            "Last Updated By",
            "Date",
            "User / Author",
            "Message Type",
            "Subject / Summary",
            "Message / Note",
            "Result Type",
        ]];
        for(const message of messages){
            const audit=messageAuditMap.get(Number(message.id))||{};
            rows.push([
                message.id||"",
                audit.create_date||"",
                getAuditValue(audit.create_uid),
                audit.write_date||"",
                getAuditValue(audit.write_uid),
                this.getMessageDate(message)||"",
                message.author?.name||"",
                this.messageTypeOptions.find(type=>type.value===message.message_type)?.label||message.message_type||"",
                this.getMessageText(message.subject),
                this.getMessageText(message.body),
                "Message",
            ]);
        }
        for(const activity of activities){
            const audit=activityAuditMap.get(Number(activity.id))||{};
            rows.push([
                activity.id||"",
                audit.create_date||"",
                getAuditValue(audit.create_uid),
                audit.write_date||"",
                getAuditValue(audit.write_uid),
                activity.date_deadline||"",
                getAuditValue(activity.user_id),
                getAuditValue(activity.activity_type_id),
                activity.summary||"",
                this.getMessageText(activity.note),
                "Activity",
            ]);
        }
        const csv=rows.map(row=>row.map(value=>{
            const normalized=String(value??"")
                .replace(/\r\n/g,"\n")
                .replace(/\r/g,"\n")
                .replace(/\n/g," ");
            return `"${normalized.replace(/"/g,'""')}"`;
        }).join(",")).join("\r\n");
        const blob=new Blob(["\ufeff"+csv],{type:"text/csv;charset=utf-8;"});
        const url=URL.createObjectURL(blob);
        const link=document.createElement("a");
        link.href=url;
        link.download="advanced_chatter_results.csv";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },
});

patch(Thread.prototype,{
    get filteredMessages(){
        const chatter=this.env.advancedChatterSearch;
        if(!chatter){
            return this.orderedMessages;
        }
        return chatter.filteredMessages;
    },
});

patch(SearchMessageInput.prototype,{
    setup(){
        super.setup(...arguments);
        this.advancedDropdownState = useState({
            expandedGroup: null,
        });
    },

    toggleAdvancedGroup(groupKey){
        this.advancedDropdownState.expandedGroup =
            this.advancedDropdownState.expandedGroup === groupKey
                ? null
                : groupKey;
    },

    onKeywordSync(ev){
        const chatter=this.env.advancedChatterSearch;
        if(!chatter){
            return;
        }
        chatter.advancedFilterState.filters.keyword=ev.target.value;
        chatter.advancedFilterState.showSuggestions=!!ev.target.value.trim();
        this.advancedDropdownState.expandedGroup = null;
    },

    onKeywordFocusSync(){
        const chatter=this.env.advancedChatterSearch;
        if(chatter&&chatter.advancedFilterState.filters.keyword.trim()){
            chatter.advancedFilterState.showSuggestions=true;
        }
    },

    onKeywordBlurSync(){
        const chatter=this.env.advancedChatterSearch;
        if(!chatter){
            return;
        }

        setTimeout(()=>{
            chatter.advancedFilterState.showSuggestions=false;
            this.advancedDropdownState.expandedGroup = null;
        },200);
    },

    selectSuggestionAndSync(group,item=null){
        const chatter=this.env.advancedChatterSearch;
        if(!chatter){
            return;
        }
        chatter.selectSearchSuggestion(group,item);
        
        this.state.searchTerm="";
    },
});