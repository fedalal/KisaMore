"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const root = path.join(__dirname, "../cloud/app/static");
const js = fs.readFileSync(path.join(root, "battle_site.js"), "utf8");
const html = fs.readFileSync(path.join(root, "battle_site.html"), "utf8");
const css = fs.readFileSync(path.join(root, "battle_site.css"), "utf8");
for (const id of [
  "accountControl", "accountButton", "accountLabel", "accountAvatar", "accountChevron",
  "accountDropdown", "accountFullName", "accountEmail", "accountTelegram", "accountLogoutButton",
]) {
  assert(html.includes('id="' + id + '"'), "missing identity element " + id);
}
assert(css.includes(".account-dropdown") && css.includes(".account-name"));
assert(css.includes("text-overflow:ellipsis"), "name should fit in header");
assert(js.includes("accountLogoutButton"), "sign-out must remain accessible");

function element(hidden=false) {
  const active = new Set(hidden ? ["hidden"] : []);
  return {
    textContent: "", title: "", dataset: {},
    classList: {
      add: cls => active.add(cls),
      remove: cls => active.delete(cls),
      contains: cls => active.has(cls),
      toggle: (cls, force) => {
        const yes = force === undefined ? !active.has(cls) : force;
        if (yes) active.add(cls); else active.delete(cls);
      },
    },
    attrs: {},
    setAttribute(k,v) { this.attrs[k]=v; },
  };
}
const nodes={};
for (const id of [
  "accountButton", "accountLabel", "accountAvatar", "accountChevron",
  "accountDropdown", "accountFullName", "accountEmail", "accountTelegram"
]) nodes[id]=element(["accountAvatar","accountChevron","accountDropdown"].includes(id));
let calledAuth=0;
const state={user:null,lang:"ru"};
const context={
  state,
  $: key => nodes[key.slice(1)],
  $$: () => [],
  t: key => ({ru:{signIn:"Войти",signedInAs:"Вы вошли как",notLinked:"Не привязан"},
    en:{signIn:"Sign in",signedInAs:"Signed in as",notLinked:"Not connected"}}[state.lang][key]||key),
  api: async path => {
    assert.equal(path,"/api/v1/account/telegram-link/status");
    return {linked:true,telegram_username:"greenhouse_user"};
  },
  openAuth: () => calledAuth++,
  document:{documentElement:{lang:"ru"}},
};
const start=js.indexOf("function setAccountMenu(");
const end=js.indexOf("function isLive(",start);
assert(start>=0 && end>start);
vm.createContext(context);
vm.runInContext(js.slice(start,end),context);

(async()=>{
  context.applyI18n();
  assert.equal(nodes.accountLabel.textContent,"Войти");
  assert(nodes.accountAvatar.classList.contains("hidden"));
  await context.toggleAccountMenu();
  assert.equal(calledAuth,1,"guests still see sign-in dialog");

  state.user={id:"u1",display_name:"Сергей Иванов",email:"sergey@example.test"};
  context.applyI18n();
  assert.equal(nodes.accountLabel.textContent,"Сергей Иванов");
  assert(nodes.accountButton.title.includes("sergey@example.test"));
  assert(!nodes.accountAvatar.classList.contains("hidden"));
  await context.toggleAccountMenu();
  assert.equal(nodes.accountDropdown.classList.contains("hidden"),false);
  assert.equal(nodes.accountFullName.textContent,"Сергей Иванов");
  assert.equal(nodes.accountEmail.textContent,"sergey@example.test");
  assert.equal(nodes.accountTelegram.textContent,"@greenhouse_user");
  assert.equal(nodes.accountButton.attrs["aria-expanded"],"true");

  await context.toggleAccountMenu();
  assert(nodes.accountDropdown.classList.contains("hidden"));
  state.lang="en";
  context.applyI18n();
  assert.equal(context.document.documentElement.lang,"en");
  assert.equal(nodes.accountLabel.textContent,"Сергей Иванов");
  state.user=null;
  context.applyI18n();
  assert.equal(nodes.accountLabel.textContent,"Sign in");
  assert(nodes.accountDropdown.classList.contains("hidden"));
  assert.equal(nodes.accountButton.attrs["aria-expanded"],"false");
  console.log("PASS: guest login, name/email, Telegram, account dropdown, language, logout reset and responsive CSS");
})().catch(err=>{console.error(err);process.exitCode=1});
