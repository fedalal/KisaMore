/* Private KisaMore Battle inbox on the public farm homepage. */
(function(){
"use strict";
const button=document.getElementById("battleInboxHomeButton");
const dialog=document.getElementById("battleInboxHomeDialog");
const list=document.getElementById("battleInboxHomeList");
const title=document.getElementById("battleInboxHomeTitle");
const close=document.getElementById("battleInboxHomeClose");
if(!button||!dialog||!list)return;
let lastUnread=0;
let account=null;
let initialized=false;
const ru=()=>document.getElementById("languageSelect")?.value==="ru";
async function refresh(){
  let me;
  try{
    const session=await fetch("/api/v1/auth/me",{credentials:"same-origin"});
    if(!session.ok)throw Error("no session");
    me=await session.json();
    const res=await fetch("/api/v1/battles/inbox",{credentials:"same-origin"});
    if(!res.ok)throw Error("inbox unavailable");
    const data=await res.json();
    if(account!==me.id){initialized=false;lastUnread=0;account=me.id;}
    button.hidden=false;
    const unread=Number(data.unread_count||0);
    button.textContent=(ru()?"📨 Сообщения":"📨 Messages")+(unread?" ("+unread+")":"");
    if(initialized&&unread>lastUnread){
      button.classList.add("has-new");
      button.title=ru()?"Новое сообщение участнику битвы":"New Battle participant message";
    }
    lastUnread=unread;initialized=true;
    return data;
  }catch{
    account=null;initialized=false;button.hidden=true;
    if(dialog.open)dialog.close();
    return null;
  }
}
function item(m){
  const article=document.createElement("article");
  article.className="battle-home-message"+(m.read_at?"":" unread");
  const name=document.createElement("strong");name.textContent=m.battle_title;
  const when=document.createElement("small");
  when.textContent=new Date(m.created_at).toLocaleString(ru()?"ru-RU":"en-GB");
  const body=document.createElement("p");body.textContent=m.body;
  article.append(name,when,body);
  if(!m.read_at){
    const read=document.createElement("button");read.type="button";
    read.className="secondary-button";
    read.textContent=ru()?"Отметить прочитанным":"Mark as read";
    read.addEventListener("click",async()=>{
      read.disabled=true;
      try{
        const response=await fetch("/api/v1/battles/inbox/"+encodeURIComponent(m.id)+"/read",
                                  {method:"POST",credentials:"same-origin"});
        if(!response.ok)throw Error("read failed");
        await open();
      }catch{read.disabled=false;}
    });
    article.append(read);
  }
  return article;
}
async function open(){
  const data=await refresh();
  if(!data)return;
  button.classList.remove("has-new");
  title.textContent=ru()?"📨 Сообщения битв":"📨 Battle messages";
  list.replaceChildren();
  if(!data.messages?.length){
    const empty=document.createElement("p");
    empty.textContent=ru()?"Сообщений пока нет.":"No messages yet.";
    list.append(empty);
  }else{
    for(const m of data.messages)list.append(item(m));
  }
  if(!dialog.open)dialog.showModal();
}
button.addEventListener("click",open);
close.addEventListener("click",()=>dialog.close());
dialog.addEventListener("click",event=>{if(event.target===dialog)dialog.close();});
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
setTimeout(refresh,750);
setInterval(refresh,30000);
})();
