"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");

const dir=path.join(__dirname,"../cloud/app/static");
const js=fs.readFileSync(path.join(dir,"battle_site.js"),"utf8");
const css=fs.readFileSync(path.join(dir,"battle_site.css"),"utf8");
const html=fs.readFileSync(path.join(dir,"battle_site.html"),"utf8");
const extract=js.slice(js.indexOf("function overlay("),js.indexOf("function renderMyBattle("));
const sandbox={
  state:{lang:"ru", selectedEntry:null, cameraViewByBattle:{}},
  t:key=>({container:"Контейнер",you:"ВЫ",players:"участников",growing:"Растём",secret:"ресурсы скрыты",
           selectPlant:"Выберите контейнер"}[key]||key),
  esc:value=>String(value??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"),
  smooth:{versioned:url=>url},
  dayInfo:()=>({day:1,total:10}),
  occupied:b=>b.entries.length,
  plantName:()=> "Редис",
  statusText:()=>"Растём"
};
vm.createContext(sandbox);
vm.runInContext(extract,sandbox);
const entries=Array.from({length:6},(_,idx)=>({
 id:"e"+(idx+1),slot_number:idx+1,
 is_mine:idx===0, resources_visible:false
}));
const battle={
 id:"battle-1",title:"Battle 12.10–18.10",status:"growing",rack_id:1,
 plant_name:"Редис",max_entries:6,entries,
 camera_views:[
  {camera_id:"camera_1",primary:true,photo_url:"/camera1.jpg",captured_at:"2026-10-12"},
  {camera_id:"camera_5",primary:false,photo_url:"/camera5.jpg",captured_at:"2026-10-12"}
 ]
};
const out=sandbox.arena(battle,true);
assert.ok(out.includes('class="rack-image-frame"'),"separate photo frame");
assert.ok(out.includes('data-full-photo="battle-1"'),"full-screen viewer");
assert.ok(out.includes('data-camera-view="camera_1"'));
assert.ok(out.includes('data-camera-view="camera_5"'));
assert.ok(out.includes('data-entry-select="e1"'),"clickable own container");
assert.ok(out.includes('class="slot-picker"'),"external container selector");
assert.equal((out.match(/class="slot-tag"/g)||[]).length,0,"no labels on camera image");
assert.equal((out.match(/class="rack-slot /g)||[]).length,6,"six transparent hitboxes");
assert.ok(out.indexOf('class="rack-overlay"')<out.indexOf('class="rack-media-toolbar"'));
assert.ok(out.indexOf('class="rack-media-toolbar"')<out.indexOf('class="slot-picker"'));
assert.ok(out.includes('data-smooth-photo="arena-battle-1-mine"'));
assert.ok(css.indexOf(".rack-image-frame>img")>css.indexOf(".rack-stage img{"),"new CSS overrides cropping");
assert.ok(css.includes("object-fit:contain"),"retain entire photo");
assert.ok(html.includes('id="photoDialog"')&&html.includes('id="photoViewerImage"'));
assert.ok(js.includes("ready.decode"),"full-photo replacement after load");
console.log("PASS: full camera frame, unobstructed image, camera switch, slot controls outside, fullscreen photo.");
assert.ok(!html.includes('id="arenaDialog"'),"battle details must not be a dialog");
assert.ok(html.includes('id="battleDetailSection"'),"battle detail belongs in page flow");
assert.ok(html.indexOf('id="battleDetailSection"')<html.indexOf('id="live"'),"detail above live list");
assert.ok(css.includes("#battleDetailArena .timeline-list{max-height:none;overflow:visible}"),
  "battle history must not introduce an internal scrollbar");
const detailCode=js.slice(js.indexOf("function renderBattleDetail(){"),js.indexOf("function openJoin("));
const detailSection={
  hidden:true,
  classList:{add(name){if(name==="hidden")detailSection.hidden=true},
             remove(name){if(name==="hidden")detailSection.hidden=false}},
  scrollIntoView(){detailSection.scrolled=true}
};
const detailArena={replaceChildren(){this.cleared=true}};
const detailLabel={textContent:""};
const detailClose={textContent:""};
const live={scrollIntoView(){this.scrolled=true}};
const nodes={
 "#battleDetailSection":detailSection,
 "#battleDetailArena":detailArena,
 "#battleDetailLabel":detailLabel,
 "#battleDetailClose":detailClose,
 "#live":live
};
const ui={
 state:{all:[battle],viewingBattleId:null,selectedEntry:"e1",lang:"ru"},
 $:name=>{assert.ok(nodes[name],"Missing mocked DOM node "+name);return nodes[name]},
 smooth:{replace(node,markup){assert.equal(node,detailArena);node.html=markup}},
 arena:()=>'<article class="arena">Full rack and controls</article>'
};
vm.createContext(ui);
vm.runInContext(detailCode,ui);
ui.openArena("battle-1");
assert.equal(detailSection.hidden,false,"detail is visible on the page");
assert.equal(detailSection.scrolled,true,"page navigates to details");
assert.ok(detailArena.html.includes("Full rack"),"battle dashboard inserted into page");
assert.equal(ui.state.viewingBattleId,"battle-1");
assert.equal(ui.state.selectedEntry,null);
ui.closeBattleDetail();
assert.equal(detailSection.hidden,true,"closing detail hides in-page section");
assert.equal(detailArena.cleared,true,"closing detail frees DOM");
assert.equal(live.scrolled,true,"returns to normal page scroll");
assert.equal(ui.state.viewingBattleId,null);
console.log("PASS: Battle opens in ordinary page flow; one scrollbar; full history; closes normally.");
