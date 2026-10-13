"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const html=fs.readFileSync("cloud/app/static/admin.html","utf8");
const css=fs.readFileSync("cloud/app/static/admin.css","utf8");
assert.ok(html.includes('admin.css?v=20261013-1'),"Browser must receive updated CSS");
const sidebar=html.slice(html.indexOf('<aside class="sidebar">'),html.indexOf('</aside>'));
assert.ok(sidebar.includes('<nav>')&&sidebar.includes('</nav>'));
assert.ok(sidebar.includes('data-section="sos"'));
assert.ok(sidebar.includes('data-section="comments"'));
assert.ok(sidebar.includes('id="logoutButton"'));
assert.ok(sidebar.indexOf("</nav>")<sidebar.indexOf('id="logoutButton"'),
 "Logout stays outside scrollable list");
const desktop=css.slice(css.lastIndexOf("/* Admin sidebar viewport overflow fix."));
const wide=desktop.slice(desktop.indexOf("@media(min-width:821px)"),desktop.indexOf("@media(max-width:820px)"));
const narrow=desktop.slice(desktop.indexOf("@media(max-width:820px)"));
assert.ok(wide.includes(".sidebar{height:100vh;height:100dvh;min-height:0;overflow:hidden}"),
 "Desktop sidebar background must be viewport tall");
assert.ok(wide.includes("flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden"),
 "Long navigation must scroll INSIDE the dark sidebar");
assert.ok(wide.includes(".sidebar .logout{flex:0 0 auto"),
 "Logout must not shrink or overflow dark background");
assert.ok(wide.includes(".sidebar-brand{flex:0 0 auto}"));
assert.ok(narrow.includes(".sidebar{height:auto;overflow:visible}"),
 "Mobile navigation grows naturally");
assert.ok(narrow.includes(".sidebar nav{flex:0 1 auto;min-height:auto;overflow:visible"),
 "Mobile navigation must not introduce an inner scrollbar");
console.log("PASS: Admin sidebar nav scrolls within dark background; logout remains visible; mobile stays in document flow");
