"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const html=fs.readFileSync("cloud/app/static/admin.html","utf8");
const css=fs.readFileSync("cloud/app/static/admin.css","utf8");
assert.ok(html.includes('admin.css?v=20261013-2'),"Browser must load compact navigation CSS");
const sidebar=html.slice(html.indexOf('<aside class="sidebar">'),html.indexOf('</aside>'));
assert.ok(sidebar.includes('data-section="sos"')&&sidebar.includes('data-section="comments"'));
assert.ok(sidebar.indexOf("</nav>")<sidebar.indexOf('id="logoutButton"'),
  "Logout remains outside the navigation");
const desktop=css.slice(css.lastIndexOf("/* Compact desktop navigation:"));
assert.ok(desktop.includes("@media(min-width:821px)"));
const wide=desktop.slice(desktop.indexOf("@media(min-width:821px){"),
  desktop.indexOf("/* Extra-small desktop"));
const small=desktop.slice(desktop.indexOf("@media(min-width:821px) and (max-height:660px)"),
  desktop.indexOf("@media(min-width:821px) and (max-height:510px)"));
const fallback=desktop.slice(desktop.indexOf("@media(min-width:821px) and (max-height:510px)"),
  desktop.indexOf("@media(max-width:820px)"));
const mobile=desktop.slice(desktop.indexOf("@media(max-width:820px)"));
assert.ok(wide.includes("overflow:visible;")&&wide.includes("gap:3px;align-content:start"),
  "Ordinary desktop nav must not scroll or stretch rows");
assert.ok(wide.includes("height:35px;line-height:18px")&&wide.includes("font-size:14px;white-space:nowrap"),
  "Short navigation rows must not wrap");
assert.ok(wide.includes("padding:12px 10px")&&wide.includes("padding:4px 9px 10px"),
  "Header and sidebar padding are compact");
assert.ok(wide.includes(".sidebar .logout{")&&wide.includes("min-height:39px"),
  "Logout remains visibly inside sidebar");

const staticEntries=(sidebar.match(/class="nav-item/g)||[]).length;
const jsStars=fs.readFileSync("cloud/app/static/admin_stars.js","utf8");
const jsBroadcasts=fs.readFileSync("cloud/app/static/admin_broadcasts.js","utf8");
const dynamic=(jsStars.includes('data-section="stars"')?1:0)+
 (jsBroadcasts.includes('data-section="broadcasts"')?1:0);
assert.equal(staticEntries,12);
assert.equal(dynamic,2);
const entries=staticEntries+dynamic;
const listHeight=entries*35+(entries-1)*3;
const upperBound=listHeight+24+65+39+8;
// 895 device pixels at 125% browser zoom -> 716 CSS pixels.
assert.ok(upperBound < 895/1.25,"All "+entries+" items must fit in 895px @125% zoom: "+upperBound+"px");
assert.ok(small.includes(".sidebar .nav-item{height:30px"),"Short window compacts rows");
assert.ok(small.includes(".sidebar nav{gap:1px}"));
assert.ok(!wide.includes("overflow-y:auto")&&!small.includes("overflow-y:auto"),
  "Ordinary desktop nav should never have a scrollbar");
assert.ok(fallback.includes("overflow-y:auto"),"Extremely short viewport gets accessibility fallback");
assert.ok(mobile.includes(".sidebar{height:auto;overflow:visible}"));
console.log("PASS: "+entries+" admin items fit without scrolling (upper bound "+upperBound+" CSS px); desktop/mobile/short viewport rules");
