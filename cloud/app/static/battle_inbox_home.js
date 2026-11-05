/* Private KisaMore Battle inbox on the public farm homepage. */
(function(){
"use strict";
const button=document.getElementById("battleMessagesOpen");
const badge=document.getElementById("battleMessagesBadge");
const dialog=document.getElementById("battleInboxHomeDialog");
const list=document.getElementById("battleInboxHomeList");
const title=document.getElementById("battleInboxHomeTitle");
const close=document.getElementById("battleInboxHomeClose");
if(!button||!dialog||!list)return;
let lastUnread=0;
let account=null;
let initialized=false;
const currentLang=()=>window.KisaSiteHeader?.getLanguage()||document.getElementById("languageSelect")?.value||"en";
const russian={newBattleMessage:"Новое сообщение участнику битвы",markRead:"Отметить прочитанным",battleMessages:"Сообщения битв",noMessages:"Сообщений пока нет."};
const localized=(key)=>currentLang()==="ru"?(russian[key]||key):(window.KisaLocales?.battleExtra?.[currentLang()]?.[key]||window.KisaLocales?.battleExtra?.en?.[key]||key);
const locale=()=>({en:"en-GB",ru:"ru-RU",de:"de-DE",fr:"fr-FR",es:"es-ES",it:"it-IT",pt:"pt-PT",pl:"pl-PL",zh:"zh-CN"}[currentLang()]||"en-GB");
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
    if(badge)badge.textContent=unread?"("+unread+")":"";
    if(initialized&&unread>lastUnread){
      button.classList.add("has-new");
      button.title=localized("newBattleMessage");
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
  when.textContent=new Date(m.created_at).toLocaleString(locale());
  const body=document.createElement("p");body.textContent=m.body;
  article.append(name,when,body);
  if(!m.read_at){
    const read=document.createElement("button");read.type="button";
    read.className="secondary-button";
    read.textContent=localized("markRead");
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
  title.textContent="📨 "+localized("battleMessages");
  list.replaceChildren();
  if(!data.messages?.length){
    const empty=document.createElement("p");
    empty.textContent=localized("noMessages");
    list.append(empty);
  }else{
    for(const m of data.messages)list.append(item(m));
  }
  if(!dialog.open)dialog.showModal();
}
button.addEventListener("click",event=>{event.preventDefault();open();});
close.addEventListener("click",()=>dialog.close());
dialog.addEventListener("click",event=>{if(event.target===dialog)dialog.close();});
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
document.addEventListener("kisamore:auth-changed",refresh);
setTimeout(refresh,750);
setInterval(refresh,30000);
})();
