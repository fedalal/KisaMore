
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const texts = {
    ru:{navPlans:"Тарифы",navBattles:"Битвы",navHome:"На главную",title:"Кошелёк Kisa",
      subtitle:"Пополнение внутреннего баланса и участие в битвах настоящих растений.",
      balanceLabel:"Ваш баланс",balanceHint:"Войдите в аккаунт KisaMore, чтобы увидеть баланс.",
      accountHint:"Баланс синхронизирован с аккаунтом KisaMore.",
      openAccount:"Личный кабинет ↗",topupTitle:"Пополнить баланс",
      topupDesc:"Kisa используются для выращивания растений и участия в битвах. Не обмениваются на деньги.",
      amountLabel:"Количество Kisa",topupButton:"Перейти к оплате",planTag:"ДЛЯ УЧАСТНИКОВ БИТВ",
      planTitle:"Садовод+",perMonth:"/ месяц",
      planDesc:"До 3 разных битв за оплаченный месяц. Каждое участие даёт одно место для выращивания растения.",
      perkOne:"До 3 участий за месяц",perkTwo:"Видеонаблюдение и таймлапсы",
      perkThree:"Возможность отменить продление",subButton:"Оформить подписку",
      waiting:"Онлайн-оплата через Lava.top готовится. Платежи пока не принимаются.",
      signIn:"Для оплаты войдите в аккаунт на главной странице KisaMore.",
      busy:"Создаём защищённый счёт…",error:"Не удалось создать счёт. Попробуйте позже.",
      disclaimer:"Оплата откроется через защищённую страницу Lava.top. Kisa начисляются только после подтверждения платежа сервером. Отмена подписки не отменяет уже начатые битвы.",
      privacyLink:"Конфиденциальность",plansLink:"Тарифы и условия"
    },
    en:{navPlans:"Pricing",navBattles:"Battles",navHome:"Home",title:"Kisa Wallet",
      subtitle:"Add Kisa to your wallet or join real plant-growing competitions.",
      balanceLabel:"Your balance",balanceHint:"Sign in to KisaMore to see your balance.",
      accountHint:"Balance is synced with your KisaMore account.",
      openAccount:"My account ↗",topupTitle:"Top up Kisa",
      topupDesc:"Kisa credits are used for plant growing and battles; they cannot be redeemed for cash.",
      amountLabel:"Kisa amount",topupButton:"Proceed to payment",planTag:"FOR BATTLE PARTICIPANTS",
      planTitle:"Gardener+",perMonth:"/ month",
      planDesc:"Up to three different battles per paid month. Each participation gives you one plant-growing space.",
      perkOne:"Up to 3 entries each month",perkTwo:"Camera photos and timelapses",
      perkThree:"Cancel auto-renewal",subButton:"Subscribe",
      waiting:"Lava.top payments are being configured. No charges are available yet.",
      signIn:"Sign in on the KisaMore home page before payment.",
      busy:"Creating secure invoice…",error:"Unable to create invoice. Please try later.",
      disclaimer:"Checkout will open on Lava.top. Kisa will be granted only after server-side payment confirmation. Cancelling membership does not affect battles already started.",
      privacyLink:"Privacy",plansLink:"Plans and terms"
    }
  };
  const saved=localStorage.getItem("battleLang") || localStorage.getItem("kisamore-language");
  const lang=(saved || navigator.language || "ru").toLowerCase().startsWith("ru")?"ru":"en";
  let dictionary=texts[lang], authed=false,topupEnabled=false,subscriptionEnabled=false;
  function translate(language){dictionary=texts[language];$("language").value=language;document.documentElement.lang=language;
    for(const [id,value] of Object.entries(dictionary)) if($(id) && id!=="balanceHint" && id!=="accountHint" && id!=="signIn" && id!=="busy" && id!=="error")$(id).textContent=value;
    document.title=(language==="ru"?"Кошелёк Kisa":"Kisa Wallet")+" · KisaMore";
    $("topupButton").disabled=!topupEnabled||!authed;$("subButton").disabled=!subscriptionEnabled||!authed;
    $("balanceHint").textContent=authed?dictionary.accountHint:dictionary.balanceHint;
    if(!topupEnabled && !subscriptionEnabled){$("topupButton").textContent=dictionary.waiting.length>0?(language==="ru"?"Оплата пока недоступна":"Payments unavailable"):"";
      $("subButton").textContent=language==="ru"?"Подписка пока недоступна":"Subscription unavailable";}
  }
  translate(lang);
  $("language").addEventListener("change",e=>{localStorage.setItem("battleLang",e.target.value);translate(e.target.value);});
  async function getJSON(url,options){const res=await fetch(url,{credentials:"same-origin",cache:"no-store",...options});if(!res.ok)throw new Error("HTTP "+res.status);return res.json();}
  Promise.allSettled([getJSON("/api/v1/account/kisa-wallet"),getJSON("/api/v1/payments/catalog"),getJSON("/api/v1/payments/membership")]).then(([wallet,catalog,member])=>{
    if(member.status==="fulfilled" && member.value.active) {
      const banner=document.createElement("div");
      banner.className="notice";
      banner.textContent=$("language").value==="ru"
        ?"Садовод+ активен · осталось участий: "+member.value.remaining_entries
        :"Gardener+ active · entries remaining: "+member.value.remaining_entries;
      document.querySelector(".cards").before(banner);
    }
    if(wallet.status==="fulfilled") {authed=true;$("balance").textContent=wallet.value.balance;$("balanceHint").textContent=dictionary.accountHint;}
    if(catalog.status==="fulfilled" && catalog.value.enabled === true){topupEnabled=catalog.value.topup_enabled===true;subscriptionEnabled=catalog.value.subscription_enabled===true;
      $("status").textContent=dictionary.signIn;
      
    } else {$("status").textContent=dictionary.waiting;}
    translate($("language").value);
  });
  async function pay(kind){if(!authed||(kind==="topup"?!topupEnabled:!subscriptionEnabled))return;
    const button=$(kind==="topup"?"topupButton":"subButton");button.disabled=true;
    $("status").textContent=dictionary.busy;
    try{const data=await getJSON("/api/v1/payments/checkout",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(kind==="topup"?{kind:"topup",kisa:Number(document.querySelector('input[name="amount"]:checked').value)}:{kind:"subscription"})});
      const u=new URL(data.checkout_url);if(u.protocol!=="https:"||!(u.hostname==="lava.top"||u.hostname.endsWith(".lava.top")))throw new Error("Unexpected provider URL");
      location.assign(u.href);
    }catch(_){$("status").textContent=dictionary.error;button.disabled=false;}
  }
  $("topupButton").addEventListener("click",()=>pay("topup"));
  const returned=new URLSearchParams(location.search);
  const invoiceId=returned.get("invoiceId");
  if(invoiceId && /^[0-9a-f-]{36}$/i.test(invoiceId)){
    getJSON("/api/v1/payments/status?invoice_id="+encodeURIComponent(invoiceId)).then(data=>{
      $("status").textContent=data.status==="paid"
        ?($("language").value==="ru"?"Оплата подтверждена! Обновите страницу для нового баланса.":"Payment confirmed! Refresh to see your balance.")
        :($("language").value==="ru"?"Платёж ещё проверяется. Баланс не изменён.":"Payment is still being verified. No credit has been granted.");
    }).catch(()=>{$("status").textContent=dictionary.error;});
  }
  $("subButton").addEventListener("click",()=>pay("subscription"));
})();
