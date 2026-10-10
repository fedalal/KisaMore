"use strict";
// Dependency-free DOM simulation for the photo-swap invariants.
// Run: node tests/test_smooth_images.js
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const downloads = [];
class FakeElement {
  constructor(tagName) {
    this.tagName = tagName.toLowerCase();
    this.dataset = {};
    this.children = [];
    this.parentElement = null;
    this.className = "";
    this.alt = "";
    this.loading = "eager";
  }
  get isConnected() {
    return this === root || Boolean(this.parentElement?.isConnected);
  }
  append(...nodes) {
    for (const node of nodes) {
      if (node.parentElement) node.parentElement.children.splice(node.parentElement.children.indexOf(node), 1);
      node.parentElement = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    this.children.forEach(node => { node.parentElement = null; });
    this.children = [];
    for (const node of nodes) {
      if (node.tagName === "#fragment") this.append(...[...node.children]);
      else this.append(node);
    }
  }
  replaceWith(other) {
    const parent = this.parentElement;
    assert(parent, "image must have a parent when replaced");
    const idx = parent.children.indexOf(this);
    assert(idx >= 0);
    if (other.parentElement) {
      const old = other.parentElement;
      old.children.splice(old.children.indexOf(other), 1);
    }
    parent.children[idx] = other;
    other.parentElement = parent;
    this.parentElement = null;
  }
  querySelectorAll() {
    const nodes = [];
    const visit = node => {
      for (const child of node.children) {
        if (child.tagName === "img" && child.dataset.smoothPhoto) nodes.push(child);
        visit(child);
      }
    };
    visit(this);
    return nodes;
  }
  querySelector() { return null; }
}
class FakeImage extends FakeElement {
  constructor() {
    super("img");
    this.complete = false;
    this.naturalWidth = 0;
    downloads.push(this);
  }
  set src(url) { this._src = url; }
  get src() { return this._src; }
  decode() { return Promise.resolve(); }
  async succeed() {
    this.complete = true;
    this.naturalWidth = 1920;
    await this.onload();
  }
  fail() { this.onerror(); }
}
const root = new FakeElement("main");
const window = {};
vm.runInNewContext(
  fs.readFileSync(path.join(__dirname, "../cloud/app/static/smooth_images.js"), "utf8"),
  { window, document: { createDocumentFragment: () => new FakeElement("#fragment") }, Image: FakeImage },
);
const smooth = window.KisaMoreSmoothImages;
function visual(url) {
  const card = new FakeElement("div");
  const img = new FakeElement("img");
  img.dataset.smoothPhoto = "rack-1";
  img.dataset.photoUrl = url;
  card.append(img);
  return card;
}
function visible() { return root.querySelectorAll()[0]; }

(async () => {
  smooth.replace(root, [visual("rack.jpg?v=1")]);
  assert.equal(downloads.length, 1, "first image should preload");
  assert.equal(visible().src, undefined, "no source until load completes");
  await downloads[0].succeed();
  assert.equal(visible().src, "rack.jpg?v=1");

  const first = visible();
  smooth.replace(root, [visual("rack.jpg?v=1")]);
  assert.equal(visible(), first, "same decoded image node is preserved");
  assert.equal(downloads.length, 1, "same timestamp never re-downloads");

  smooth.replace(root, [visual("rack.jpg?v=2")]);
  assert.equal(visible().src, "rack.jpg?v=1", "old photo stays visible until next is ready");
  assert.equal(downloads.length, 2);
  downloads[1].fail();
  assert.equal(visible().src, "rack.jpg?v=1", "failed download must not clear old photo");

  smooth.replace(root, [visual("rack.jpg?v=3")]);
  const beforeNewPhoto = visible();
  assert.equal(beforeNewPhoto.src, "rack.jpg?v=1");
  await downloads[2].succeed();
  assert.equal(visible().src, "rack.jpg?v=3", "decoded photo replaces previous one");

  smooth.replace(root, [visual("rack.jpg?v=4")]);
  smooth.replace(root, [visual("rack.jpg?v=5")]);
  const current = visible();
  await downloads[3].succeed();
  assert.equal(visible(), current, "stale asynchronous load cannot overwrite newer request");
  await downloads[4].succeed();
  assert.equal(visible().src, "rack.jpg?v=5", "latest photo wins");
  console.log("PASS: no blank image, same frame reused, failed download retained, stale decode ignored");
})().catch(err => { console.error(err); process.exitCode = 1; });
