/* Shared switcher for the public legal pages; no external translation calls. */
(() => {
  "use strict";
  const page = document.body.dataset.sitePage;
  const allowed = ["en","ru","de","fr","es","it","pt","pl","zh"];
  const titleKey = {terms:"termsTitle", privacy:"privacyTitle", "delete-account":"deleteTitle"}[page];
  if (!titleKey) return;
  const ru = {
    termsTitle:"KisaMore Battle — Условия использования",
    privacyTitle:"KisaMore — Политика конфиденциальности",
    deleteTitle:"Удаление аккаунта KisaMore",
    languageHint:"Язык страницы выбирается в верхнем меню.",
    effectiveDate:"Действует с",
    requestDelete:"Запросить удаление аккаунта"
  };
  const dated = {"terms":"2026-11-05", "privacy":"2026-10-05"};
  const localeCode = {en:"en-GB",ru:"ru-RU",de:"de-DE",fr:"fr-FR",es:"es-ES",it:"it-IT",pt:"pt-PT",pl:"pl-PL",zh:"zh-CN"};
  function labels(lang) {
    if(lang === "ru") return ru;
    return window.KisaLocales?.legalMeta?.[lang] || window.KisaLocales?.legalMeta?.en || {};
  }
  function render(value) {
    const lang = allowed.includes(value) ? value : "en";
    const dict = labels(lang);
    document.documentElement.lang=lang;
    document.querySelectorAll("main > section[id]").forEach(section=>{
      section.hidden = section.id !== lang;
    });
    const title=document.getElementById("legalTitle");
    if(title)title.textContent=dict[titleKey] || window.KisaLocales?.legalMeta?.en?.[titleKey] || title.textContent;
    document.title=(dict[titleKey]||title.textContent)+" · KisaMore";
    const hint=document.getElementById("legalLanguageHint");
    if(hint)hint.textContent=dict.languageHint || "";
    const date=dated[page];
    if(date) {
      const node=document.querySelector("main > p.muted:not(#legalLanguageHint)");
      if(node)node.textContent=(dict.effectiveDate||"Effective date")+": "+new Intl.DateTimeFormat(localeCode[lang],{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(date+"T00:00:00Z"));
    }
    const privacy=document.getElementById("legalPrivacy");
    if(privacy)privacy.textContent=labels(lang).privacyTitle || "Privacy Policy";
    const deleteLink=document.querySelector('main > section:not([hidden]) a[href="/delete-account"]');
    if(deleteLink)deleteLink.textContent=dict.requestDelete || deleteLink.textContent;
  }
  render(window.KisaSiteHeader?.getLanguage() || "en");
  document.addEventListener("kisamore:language-changed", e=>render(e.detail.language));
})();
