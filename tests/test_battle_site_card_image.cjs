"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const js=fs.readFileSync("cloud/app/static/battle_site.js","utf8");
const css=fs.readFileSync("cloud/app/static/battle_site.css","utf8");
const html=fs.readFileSync("cloud/app/static/battle_site.html","utf8");
const code=js.slice(js.indexOf("function battleCard(b){"),js.indexOf("function renderLists(){"));
const context={
 isLive:b=>b.status==="growing"||b.status==="judging",
 dayInfo:()=>({day:3,total:10}),
 occupied:b=>b.entries.length,
 pct:(n,d)=>Math.round(n/d*100),
 cameraViews:b=>b.camera_views,
 plantName:()=>"Редис Ред коралл",
 statusText:s=>s,
 t:key=>({viewBattle:"Открыть битву",joinBattle:"Участвовать",day:"День",of:"из",players:"участников",prize:"приз"}[key]||key),
 esc:value=>String(value??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"),
 smooth:{versioned:(url,ts)=>url+"?v="+ts}
};
vm.createContext(context);vm.runInContext(code,context);
const battle={id:"b1",title:"Plant Battle 12.10-18.10",status:"growing",
 rack_photo_url:"/api/battle/photo.jpg",camera_views:[{primary:true,captured_at:"2026-10-12"}],
 entries:[{id:"p1"}],max_entries:6,entry_price_kisa:10,winner_reward_kisa:20};
const markup=context.battleCard(battle);
assert.ok(markup.includes('data-smooth-photo="battle-card-b1"'),"smooth photo refresh preserved");
assert.ok(markup.includes('alt="Редис Ред коралл"'));
assert.ok(markup.includes('class="battle-card-meta"'));
const imgSection=markup.slice(markup.indexOf('<div class="battle-card-top">'),markup.indexOf('<div class="battle-card-meta">'));
assert.ok(imgSection.includes("<img "),"image appears first");
assert.ok(!imgSection.includes("<h3>"),"title not covering image");
assert.ok(!imgSection.includes("card-live"),"status not covering image");
assert.ok(!imgSection.includes("photo-shade"),"dark shade not covering plants");
assert.ok(markup.includes("Открыть битву"),"working action button preserved");
assert.ok(markup.includes("Ⓚ 20"),"reward preserved");
const upcoming=context.battleCard({...battle,status:"open",remaining_entries:5});
assert.ok(upcoming.includes("Участвовать"),"join action preserved");
assert.ok(!upcoming.includes("photo-shade"));
const missing=context.battleCard({...battle,rack_photo_url:null});
assert.ok(missing.includes("battle-card-no-photo"),"camera missing gracefully handled");
assert.ok(css.includes(".battle-card-top{position:relative;aspect-ratio:auto;min-height:0"),"legacy 16:9 crop overridden");
assert.ok(css.includes(".battle-card-top img{display:block;width:100%;height:auto;min-height:0"),"natural image aspect ratio");
assert.ok(css.includes("object-fit:contain"),"no cover cropping");
assert.ok(html.includes("battle_site.js?v=20261012-3"),"JS cache busted");
assert.ok(html.includes("battle_site.css?v=20261012-3"),"CSS cache busted");
console.log("PASS full-frame live/upcoming cards, text below photo, no shade, buttons, fallback, caching");
