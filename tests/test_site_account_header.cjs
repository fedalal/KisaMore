"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "../cloud/app/static");
const source = fs.readFileSync(path.join(root, "account_header.js"), "utf8");
const dashboard = fs.readFileSync(path.join(root, "dashboard.js"), "utf8");
const wallet = fs.readFileSync(path.join(root, "wallet.js"), "utf8");
const header = fs.readFileSync(path.join(root, "site_header.html"), "utf8");
assert(wallet.includes('return_origin:returnOrigin') && wallet.includes('location.hostname==="ru.kisamore.farm"'),
  "checkout preserves the mirror origin");
for (const page of ["index.html", "pricing.html", "wallet.html", "privacy.html", "delete_account.html", "admin.html"]) {
  const html = fs.readFileSync(path.join(root, page), "utf8");
  for (const field of ["data-kisa-account", "data-account-button", "data-account-menu", "data-account-profile", "data-account-wallet", "data-account-logout"]) {
    assert(header.includes(field), `shared header is missing ${field}`);
  }
  assert(html.includes("<!-- KISAMORE_SITE_HEADER -->") && html.includes("account_header.js") && html.includes("site_header.css"));
}

function element(hidden = false) {
  return {
    hidden, textContent: "", title: "", disabled: false, attrs: {}, events: {},
    addEventListener(type, handler) { this.events[type] = handler; },
    setAttribute(key, value) { this.attrs[key] = value; },
    focus() { this.focused = true; },
  };
}
function setup({inline = false, response = {ok:true, json:async()=>({id:"u1",display_name:"Алекс",email:"person@example.test"})}} = {}) {
  const fields = {};
  for (const field of ["button", "menu", "avatar", "label", "chevron", "caption", "name", "email", "profile", "wallet", "logout", "error"]) fields[field] = element(["menu", "avatar", "chevron", "error"].includes(field));
  const widget = {
    dataset: inline ? {inlineAuth:"true"} : {},
    querySelector(selector) { const name = selector.match(/data-account-([^\]]+)/)?.[1]; return fields[name]; },
    contains(target) { return Object.values(fields).includes(target); },
  };
  const handlers = {}, dispatched = [], calls = [];
  const document = {
    documentElement:{lang:"ru"},
    querySelector: () => widget,
    addEventListener: (type, handler) => { handlers[type] = handler; },
    dispatchEvent: event => dispatched.push(event.type),
  };
  const location = {pathname:"/pricing", search:"", hash:"", assigned:null, reloaded:false,
    assign(value) { this.assigned=value; }, reload() { this.reloaded=true; }};
  let logoutResponse = {ok:true};
  let observer;
  class MutationObserver { constructor(callback) { observer=callback; } observe() {} }
  class CustomEvent { constructor(type) { this.type=type; } }
  const context = {document, location, window:{}, MutationObserver, CustomEvent, encodeURIComponent,
    fetch: async (url, options) => { calls.push([url,options]); return url.endsWith("logout") ? logoutResponse : response; }};
  vm.createContext(context);
  vm.runInContext(source, context);
  return {fields,widget,handlers,dispatched,calls,document,location,context,
    changeLanguage: lang => { document.documentElement.lang=lang; observer(); },
    failLogout: () => { logoutResponse={ok:false}; }};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));

(async () => {
  const signed=setup();
  await settle();
  assert.equal(signed.fields.label.textContent,"Алекс");
  assert.equal(signed.fields.avatar.textContent,"А");
  assert.equal(signed.fields.avatar.hidden,false);
  signed.fields.button.events.click();
  assert.equal(signed.fields.menu.hidden,false);
  assert.equal(signed.fields.name.textContent,"Алекс");
  assert.equal(signed.fields.email.textContent,"person@example.test");
  assert.equal(signed.fields.profile.textContent,"Личный кабинет");
  assert.equal(signed.fields.button.attrs["aria-expanded"],"true");
  signed.changeLanguage("en");
  assert.equal(signed.fields.profile.textContent,"My account");
  signed.handlers.keydown({key:"Escape"});
  assert.equal(signed.fields.menu.hidden,true);
  assert.equal(signed.fields.button.focused,true);
  signed.fields.button.events.click();
  signed.failLogout();
  await signed.fields.logout.events.click();
  assert.equal(signed.fields.error.hidden,false);
  assert.equal(signed.location.reloaded,false);
  assert.equal(signed.fields.label.textContent,"Алекс");

  const guest=setup({response:{status:401,ok:false}});
  await settle();
  assert.equal(guest.fields.label.textContent,"Войти");
  guest.fields.button.events.click();
  assert.equal(guest.location.assigned,"/?account=signin&next=%2Fpricing");

  const home=setup({inline:true});
  assert.equal(home.calls.length,0,"the homepage uses its existing auth state");
  home.context.window.KisaMoreAccountHeader.setUser(null);
  home.fields.button.events.click();
  assert(home.dispatched.includes("kisamore:account-signin"));
  home.context.window.KisaMoreAccountHeader.setUser({display_name:"<img onerror=alert(1)>",email:"x@example.test"});
  assert.equal(home.fields.label.textContent,"<img onerror=alert(1)>","the name is rendered as text");
  let prevented=false;
  home.fields.profile.events.click({preventDefault(){prevented=true;}});
  assert(prevented && home.dispatched.includes("kisamore:account-profile"));
  await home.fields.logout.events.click();
  assert(home.dispatched.includes("kisamore:account-signed-out"));
  assert.equal(home.fields.label.textContent,"Войти");
  assert.equal(home.location.reloaded,false);

  const start=dashboard.indexOf("  function safeAccountReturn(");
  const end=dashboard.indexOf("  let returnAfterAuth",start);
  assert(start>=0 && end>start);
  const safeContext={window:{location:{origin:"https://kisamore.farm"}},URL};
  vm.createContext(safeContext);
  vm.runInContext(dashboard.slice(start,end),safeContext);
  assert.equal(safeContext.safeAccountReturn("/wallet"),"/wallet");
  assert.equal(safeContext.safeAccountReturn("/pricing?lang=ru"),"/pricing?lang=ru");
  assert.equal(safeContext.safeAccountReturn("https://evil.example/wallet"),null);
  assert.equal(safeContext.safeAccountReturn("//evil.example/wallet"),null);
  assert.equal(safeContext.safeAccountReturn("/admin"),"/admin");
  assert.equal(safeContext.safeAccountReturn("/privacy"),"/privacy");
  assert.equal(safeContext.safeAccountReturn("/api/v1/battle-certificate/123-abc?lang=ru"),"/api/v1/battle-certificate/123-abc?lang=ru");
  assert.equal(safeContext.safeAccountReturn("/api/v1/admin/123"),null);
  assert.equal(safeContext.safeAccountReturn("/admin/delete"),null);
  console.log("PASS: shared account header, guest flow, identity, translation, logout and safe return URLs");
})().catch(error => { console.error(error); process.exitCode=1; });
