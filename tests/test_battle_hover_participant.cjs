"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const js=fs.readFileSync("cloud/app/static/battle_site.js","utf8");
const css=fs.readFileSync("cloud/app/static/battle_site.css","utf8");
const html=fs.readFileSync("cloud/app/static/battle_site.html","utf8");
const start=js.indexOf("function overlay(b,selectedId){");
const end=js.indexOf("function slotPicker(b,selectedId){",start);
assert.ok(start>0&&end>start);
const scope={
 state:{lang:"ru"},
 t:key=>({container:"Контейнер",you:"ВЫ"}[key]||key),
 esc:s=>String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")
};
vm.createContext(scope);vm.runInContext(js.slice(start,end),scope);
const entries=[
 {id:"e1",slot_number:1,is_mine:true,participant_name:"Alex",
  participant_avatar_url:"/api/v1/public/battles/entries/e1/avatar"},
 {id:"e2",slot_number:2,is_mine:false,participant_name:"Наталья",participant_avatar_url:null},
 {id:"e3",slot_number:3,participant_name:'<img src=x onerror="alert(1)">'},
];
const out=scope.overlay({entries},"e1");
assert.equal((out.match(/class="rack-slot /g)||[]).length,6);
assert.equal((out.match(/class="rack-slot-tooltip"/g)||[]).length,3,
  "only participating containers have tooltip");
assert.ok(out.includes("Alex"),"public display name visible");
assert.ok(out.includes('class="rack-slot-avatar" loading="lazy" src="/api/v1/public/battles/entries/e1/avatar" alt=""'),
  "participant avatar uses public battle endpoint");
assert.ok(out.includes('class="rack-slot-avatar rack-slot-avatar-initial"'),"fallback initial");
assert.ok(out.includes(">Н</span>"),"fallback initial supports Cyrillic");
assert.ok(out.includes("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;"),
  "malicious user-supplied display name is escaped");
assert.ok(!out.includes('<img src=x onerror='),"injected HTML not executable");
assert.ok(out.includes('data-entry-select="e1"'),"existing selection action remains");
assert.ok(out.includes('aria-label="Контейнер #1 · Alex"'),"screen-reader label contains name");
assert.ok(!out.includes("email"),"email is not exposed");
assert.ok(css.includes(".rack-slot-tooltip")&&css.includes("visibility:hidden"));
assert.ok(css.includes(":is(:hover,:focus-visible) .rack-slot-tooltip"));
assert.ok(css.includes("@media(hover:none)"),"touch support");
assert.ok(js.includes('hotspot.focus({preventScroll:true})'),"focus restored after touch selection");
assert.ok(css.includes('.rack-image-frame .rack-overlay .rack-slot .rack-slot-tooltip > img.rack-slot-avatar{'),
  "avatar selector must override the more specific legacy .rack-stage img rule");
assert.ok(css.includes('min-width:34px;min-height:0;max-width:34px;max-height:34px;'),
  "avatar must not inherit the old 560px image min-height");
assert.ok(css.includes('flex-basis:26px;width:26px;height:26px;'),
  "mobile avatar size must stay small");
assert.ok(html.includes("battle_site.css?v=20261013-1"));
assert.ok(html.includes("battle_site.js?v=20261018-1"));
console.log("PASS: participant hover tooltip, avatar/fallback, safely escaped names, keyboard/touch, selection retained");
