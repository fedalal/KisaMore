"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const source=fs.readFileSync("cloud/app/static/battle_site.js","utf8");
const start=source.indexOf("function dayInfo(b){");
const end=source.indexOf("function pct(",start);
assert.ok(start>=0 && end>start);
const context={};
vm.createContext(context);
vm.runInContext(source.slice(start,end),context);
assert.equal(JSON.stringify(context.dayInfo({
  planted_at:"2026-10-12T10:53:02Z",
  start_date:"2026-10-12",end_date:"2026-10-18",
  battle_day:7,battle_total_days:7,grow_days:10
})),JSON.stringify({day:7,total:7}));
assert.equal(context.dayInfo({
  planted_at:"2026-10-18T13:12:53Z",
  start_date:"2026-10-19",end_date:"2026-10-25",
  battle_day:null,battle_total_days:7,grow_days:10
}),null,"Do not start tomorrow's battle prematurely");
assert.equal(context.dayInfo({planted_at:null,battle_day:1,battle_total_days:7}),null);
assert.ok(!source.includes("total:b.grow_days"),"Never use plant growing time as battle duration");
console.log("PASS: website battle day comes from calendar API, not plant grow_days");
