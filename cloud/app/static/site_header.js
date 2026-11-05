/* One navigation and language control for every KisaMore page. */
(() => {
  "use strict";
  const root = document.querySelector("[data-site-header]");
  if (!root) return;
  const select = document.getElementById("languageSelect");
  const note = document.getElementById("siteLanguageNote");
  if (document.body.dataset.sitePage==="admin") {select.disabled=true; select.title="Панель администратора доступна на русском языке";}
  const page = document.body.dataset.sitePage || "";
  const available = (document.body.dataset.siteLanguages || "all").split(",");
  const nav = {
    en:["Greenhouse","Battles","Pricing","Messages"], ru:["Теплица","Битвы","Тарифы","Сообщения"],
    de:["Gewächshaus","Wettkämpfe","Preise","Nachrichten"], fr:["Serre","Compétitions","Tarifs","Messages"],
    es:["Invernadero","Competiciones","Precios","Mensajes"], it:["Serra","Gare","Prezzi","Messaggi"],
    pt:["Estufa","Competições","Preços","Mensagens"], pl:["Szklarnia","Rywalizacje","Cennik","Wiadomości"],
    zh:["温室","比赛","价格","消息"]
  };
  const account = {
    en:{signIn:"Sign in",signedInAs:"Signed in as",profile:"My account",wallet:"Kisa wallet",signOut:"Sign out",unavailable:"Account unavailable",retry:"Could not sign out. Try again."},
    ru:{signIn:"Войти",signedInAs:"Вы вошли как",profile:"Личный кабинет",wallet:"Кошелёк Kisa",signOut:"Выйти",unavailable:"Аккаунт недоступен",retry:"Не удалось выйти. Попробуйте ещё раз."},
    de:{signIn:"Anmelden",signedInAs:"Angemeldet als",profile:"Mein Konto",wallet:"Kisa-Guthaben",signOut:"Abmelden",unavailable:"Konto nicht verfügbar",retry:"Abmelden fehlgeschlagen."},
    fr:{signIn:"Connexion",signedInAs:"Connecté en tant que",profile:"Mon compte",wallet:"Portefeuille Kisa",signOut:"Déconnexion",unavailable:"Compte indisponible",retry:"Déconnexion impossible."},
    es:{signIn:"Entrar",signedInAs:"Sesión iniciada como",profile:"Mi cuenta",wallet:"Monedero Kisa",signOut:"Salir",unavailable:"Cuenta no disponible",retry:"No se pudo cerrar la sesión."},
    it:{signIn:"Accedi",signedInAs:"Accesso come",profile:"Il mio account",wallet:"Portafoglio Kisa",signOut:"Esci",unavailable:"Account non disponibile",retry:"Impossibile uscire."},
    pt:{signIn:"Entrar",signedInAs:"Sessão iniciada como",profile:"Minha conta",wallet:"Carteira Kisa",signOut:"Sair",unavailable:"Conta indisponível",retry:"Não foi possível sair."},
    pl:{signIn:"Zaloguj",signedInAs:"Zalogowano jako",profile:"Moje konto",wallet:"Portfel Kisa",signOut:"Wyloguj",unavailable:"Konto niedostępne",retry:"Nie udało się wylogować."},
    zh:{signIn:"登录",signedInAs:"已登录",profile:"我的账户",wallet:"Kisa 钱包",signOut:"退出登录",unavailable:"账户不可用",retry:"退出失败，请重试。"}
  };
  const notes = {
    en:["This page is available in English and Russian.","The administration panel is available in Russian."],
    ru:["Содержание страницы доступно на русском и английском.","Панель администратора доступна на русском языке."],
    de:["Der Seiteninhalt ist auf Englisch und Russisch verfügbar.","Die Verwaltung ist auf Russisch verfügbar."],
    fr:["Le contenu de cette page est disponible en anglais et en russe.","L’administration est disponible en russe."],
    es:["El contenido de esta página está disponible en inglés y ruso.","El panel de administración está disponible en ruso."],
    it:["Il contenuto della pagina è disponibile in inglese e russo.","Il pannello di amministrazione è disponibile in russo."],
    pt:["O conteúdo desta página está disponível em inglês e russo.","O painel de administração está disponível em russo."],
    pl:["Treść tej strony jest dostępna po angielsku i rosyjsku.","Panel administracyjny jest dostępny po rosyjsku."],
    zh:["此页面的内容有英语和俄语版本。","管理面板提供俄语版本。"]
  };
  const params = new URLSearchParams(location.search);
  const explicit = page === "certificate" ? (params.get("ui_lang") || params.get("lang")) : page === "pricing" ? params.get("lang") : null;
  let chosen = "en", userChoice = false;
  function valid(value) { const lang=String(value || "").toLowerCase().split("-")[0]; return nav[lang] ? lang : "en"; }
  function setLanguage(value, options = {}) {
    chosen = page==="admin" ? "ru" : valid(value);
    select.value = chosen;
    const [greenhouse,battles,pricing,messages] = nav[chosen];
    const dictionary = {greenhouse,battles,pricing,messages,currency:"Kisa Ⓚ",...account[chosen]};
    root.querySelectorAll("[data-site-text]").forEach(el => { const value=dictionary[el.dataset.siteText]; if (value) el.textContent=value; });
    const messageLink=document.getElementById("battleMessagesOpen");
    messageLink.setAttribute("aria-label",messages); messageLink.title=messages;
    if (note) { note.hidden=available.includes("all") || available.includes(chosen); note.textContent=notes[chosen][available.length===1 && available[0]==="ru" ? 1 : 0]; }
    if (options.persist !== false && page!=="admin") { localStorage.setItem("kisamore-language",chosen); localStorage.setItem("battleLang",chosen); }
    if (options.notify) document.dispatchEvent(new CustomEvent("kisamore:language-changed",{detail:{language:chosen}}));
  }
  select.addEventListener("change", async () => {
    userChoice=true;
    setLanguage(select.value,{notify:true});
    const selection=chosen;
    if (page === "pricing" && params.has("lang")) {
      const url=new URL(location.href); url.searchParams.set("lang",selection);
      history.replaceState({},document.title,url.pathname+url.search+url.hash);
    }
    // The homepage and battle already save the language with their own auth flows.
    const save = page !== "home" && page !== "battle"
      ? fetch("/api/v1/auth/me/language",{method:"PATCH",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({language:selection})}).catch(()=>{})
      : Promise.resolve();
    if (page === "certificate") {
      await Promise.race([save,new Promise(resolve=>setTimeout(resolve,3000))]);
      if (select.value!==selection) return;
      const url=new URL(location.href);
      url.searchParams.set("lang",selection);
      url.searchParams.delete("ui_lang");
      location.assign(url.pathname+url.search+url.hash);
    }
  });
  window.KisaSiteHeader = {setLanguage, getLanguage:()=>chosen, accountText:()=>account[chosen], hasExplicitLanguage:()=>Boolean(explicit || userChoice)};
  setLanguage(explicit || localStorage.getItem("kisamore-language") || localStorage.getItem("battleLang") || navigator.language || "en",{persist:false});
  if (page==="certificate" && !params.has("lang") && chosen!==document.documentElement.lang) {
    const target=new URL(location.href); target.searchParams.set("lang",chosen);
    location.replace(target.pathname+target.search+target.hash);
  }
  for (const link of root.querySelectorAll(".kisa-site-nav a")) {
    const destination=new URL(link.href,location.href);
    if ((page==="home" && destination.pathname==="/" && destination.hash) || (page!=="home" && destination.pathname===location.pathname)) link.setAttribute("aria-current","page");
  }
})();
