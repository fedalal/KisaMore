"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const js=fs.readFileSync("cloud/app/static/battle_site.js","utf8");
const html=fs.readFileSync("cloud/app/static/battle_site.html","utf8");
const battle={id:"b1",entries:[{id:"e1",water_budget_ml:1000,water_used_ml:150,
 nutrient_budget_ml:100,nutrient_used_ml:0,shade_budget_minutes:2000,shade_used_minutes:0}]};
const dom=Object.fromEntries(["actionTitle","actionRemaining","actionPresets","actionAmount","actionError","actionDialog"].map(k=>["#"+k,{textContent:"",innerHTML:"",value:0,max:0,showModal(){this.opened=true}}]));
const ctx={state:{lang:"ru",mine:[battle]},$:(s)=>dom[s],esc:x=>String(x),
 pct:(used,total)=>total?used/total*100:0,fmtDate:()=> "12.10"};
vm.createContext(ctx);
const snippets=[
 js.slice(js.indexOf("const T="),js.indexOf("function detectLang")),
 js.slice(js.indexOf("function t(k){"),js.indexOf("function esc(v){")),
 js.slice(js.indexOf("function resource("),js.indexOf("function overlay(")),
 js.slice(js.indexOf("function openAction("),js.indexOf("async function confirmAction("))
];
for(const s of snippets)vm.runInContext(s,ctx);
const sample= {actions:[
 {kind:"water",amount:150,status:"completed",requested_at:"2026-10-12"},
 {kind:"shade",amount:30,status:"pending",requested_at:"2026-10-12"}
]};
for(const [lang,expectedWater,expectedShade,wrongWater,wrongShade] of [
 ["ru","мл","мин","ml","min"],["en","ml","min","мл","мин"]
]){
 ctx.state.lang=lang;
 assert.equal(ctx.t("ml"),expectedWater);
 assert.equal(ctx.t("min"),expectedShade);
 assert.equal(ctx.actionUnit("water"),expectedWater);
 assert.equal(ctx.actionUnit("shade"),expectedShade);
 const water=ctx.resource(ctx.t("water"),"💧",150,1000,ctx.t("ml"));
 assert.ok(water.includes("850 "+expectedWater),water);
 assert.ok(water.includes("150 "+expectedWater));
 assert.ok(water.includes("1000 "+expectedWater));
 const shade=ctx.resource(ctx.t("shade"),"🌘",0,2000,ctx.t("min"));
 assert.ok(shade.includes("2000 "+expectedShade),shade);
 const history=ctx.timeline(sample);
 assert.ok(history.includes("150 "+expectedWater),history);
 assert.ok(history.includes("30 "+expectedShade),history);
 for(const kind of ["water","nutrient","shade"]){
  ctx.openAction({dataset:{battle:"b1",entry:"e1",actionKind:kind}});
  assert.equal(dom["#actionDialog"].opened,true);
  assert.ok(dom["#actionRemaining"].textContent.includes(" "+(kind==="shade"?expectedShade:expectedWater)+" "));
  assert.ok(dom["#actionPresets"].innerHTML.includes(" "+(kind==="shade"?expectedShade:expectedWater)+"</button>"));
 }
 assert.ok(!water.includes("850 "+wrongWater));
}
assert.ok(html.includes("battle_site.js?v=20261013-1"));
assert.ok(!/selected\.water_budget_ml,"ml"\)/.test(js));
assert.ok(!/k==="shade"\?"min":"ml"/.test(js));
console.log("PASS: ru uses мл/мин and en uses ml/min in resources, action history and command dialog");
