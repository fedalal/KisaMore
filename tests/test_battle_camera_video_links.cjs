"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const js=fs.readFileSync("cloud/app/static/battle_site.js","utf8");
const html=fs.readFileSync("cloud/app/static/battle_site.html","utf8");
const a=js.indexOf("function videoButtons(view){"),b=js.indexOf("function cameraViews(b){",a);
assert.ok(a>0&&b>a);
const scope={t:key=>key==="full"?"All":key==="timelapse"?"Timelapse":key,
 esc:s=>String(s).replaceAll("&","&amp;").replaceAll('"',"&quot;").replaceAll("<","&lt;")};
vm.createContext(scope);
vm.runInContext(js.slice(a,b),scope);
const b1="27195efe-6f1a-488e-bf38-3648fb582e81";
const view=camera=>({
 camera_id:camera,
 timelapse_urls:Object.fromEntries(["24h","3d","full"].map(period=>
 [period,"/api/v1/public/battles/"+b1+"/cameras/"+camera+"/timelapse/"+period]))
});
for(const camera of ["camera_1","camera_5"]){
 const out=scope.videoButtons(view(camera));
 for(const period of ["24h","3d","full"]){
  assert.ok(out.includes("/cameras/"+camera+"/timelapse/"+period));
  assert.ok(!out.includes("/slots/"));
  assert.ok(!out.includes("/plantings/"));
 }
}
const full=js.slice(js.indexOf("function arena(b,interactive){"),js.indexOf("function renderMyBattle(){"));
assert.ok(full.includes("videoButtons(view)"),"Battle video controls follow the camera selection");
assert.ok(!full.includes("videoButtons(selected)"),"No container-specific videos in battle panel");
assert.ok(html.includes("battle_site.js?v=20261018-1"),"Fresh JS cache version");
console.log("PASS: Battle 24h/3d/full use whole-rack camera, switching camera changes all timelapse URLs");
