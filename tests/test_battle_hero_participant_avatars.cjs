"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("cloud/app/static/battle_site.js","utf8");
const html=fs.readFileSync("cloud/app/static/battle_site.html","utf8");
const css=fs.readFileSync("cloud/app/static/battle_site.css","utf8");
const start=source.indexOf("function miniSlots(b){");
const end=source.indexOf("function updateHero(){",start);
assert.ok(start>0 && end>start);
const context={
 state:{lang:"ru"}, t:key=>({container:"Контейнер"}[key]||key),
 esc:val=>String(val??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")
};
vm.createContext(context);vm.runInContext(source.slice(start,end),context);
const b={entries:[
 {slot_number:1,participant_name:"Alex",participant_avatar_url:"/api/v1/public/battles/entries/e1/avatar"},
 {slot_number:2,participant_name:"Наталья"},
 {slot_number:3,participant_name:"<img src=x onerror=alert(1)>",is_winner:true},
 {slot_number:4,participant_name:"Alex2"},
 {slot_number:5,participant_name:"Test3"},
 {slot_number:6,participant_name:"Test2"}
]};
const result=context.miniSlots(b);
assert.equal((result.match(/class="mini-slot taken/g)||[]).length,6);
assert.equal((result.match(/class="hero-slot-avatar/g)||[]).length,6);
assert.equal((result.match(/<img class="hero-slot-avatar"/g)||[]).length,1);
assert.ok(result.includes('src="/api/v1/public/battles/entries/e1/avatar"'));
assert.ok(result.includes(">Н</span>"),"Cyrillic fallback is first initial");
assert.ok(result.includes('title="Alex"')&&result.includes('title="Наталья"'));
assert.ok(result.includes('&lt;img src=x onerror=alert(1)&gt;'),"Public names HTML escaped");
assert.ok(!result.includes('<img src=x onerror=alert(1)>'),"Public names cannot inject markup");
assert.ok(result.includes("🏆"),"Winner status remains visible");
for(let i=1;i<=6;i++)assert.ok(result.includes('class="hero-slot-number">#'+i));
const partly=context.miniSlots({entries:[b.entries[0]]});
assert.equal((partly.match(/class="mini-slot"/g)||[]).length,5,"Empty slots remain numbered");
assert.ok(partly.includes('>2</div>'));
assert.ok(css.includes('.hero-scoreboard .mini-slot .hero-slot-avatar{'),"Scoped avatar sizing");
assert.ok(css.includes('min-width:44px;min-height:44px;max-width:44px;max-height:44px'),"Stable desktop avatar 44px");
assert.ok(css.includes('min-width:34px;min-height:34px;max-width:34px;max-height:34px'),"Stable mobile avatar 34px");
assert.ok(html.includes('battle_site.css?v=20261013-1'));
assert.ok(html.includes('battle_site.js?v=20261013-1'));
console.log("PASS: hero six avatars, names, initials fallback, winner, empty slots, escaping, sizes, cache");
