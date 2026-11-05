
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
      testReady:"Тестовая оплата доступна только администратору. Списание денег будет настоящим.",
      paymentReady:"Пополнение Kisa доступно. Проверьте сумму перед оплатой.",
      emailRejected:"Lava.top отклонил email покупателя. Проверьте, что он отличается от email продавца Lava.top.",
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
      testReady:"Admin-only test checkout. Your payment will be a real charge.",
      paymentReady:"Kisa top-up is available. Verify the amount before paying.",
      emailRejected:"Lava.top rejected the buyer email. Use a customer account with an email different from the Lava.top seller.",
      busy:"Creating secure invoice…",error:"Unable to create invoice. Please try later.",
      disclaimer:"Checkout will open on Lava.top. Kisa will be granted only after server-side payment confirmation. Cancelling membership does not affect battles already started.",
      privacyLink:"Privacy",plansLink:"Plans and terms"
    }
  };
  for(const [lang,labels] of Object.entries(window.KisaLocales?.wallet || {})){
    if(lang!=="en" && lang!=="ru") texts[lang]=labels;
  }
  const ex=window.KisaLocales?.walletExtra||{};
  const saved=localStorage.getItem("kisamore-language") || localStorage.getItem("battleLang");
  const lang=window.KisaSiteHeader?.getLanguage() || (saved || navigator.language || "ru").toLowerCase().slice(0,2);
  let dictionary=texts[lang] || texts.en, authed=false,topupEnabled=false,subscriptionEnabled=false, membershipRemaining=null;
  function translate(selected){const language=texts[selected]?selected:"en";dictionary=texts[language];document.documentElement.lang=language;
    for(const [id,value] of Object.entries(dictionary)) if($(id) && id!=="balanceHint" && id!=="accountHint" && id!=="signIn" && id!=="testReady" && id!=="paymentReady" && id!=="emailRejected" && id!=="busy" && id!=="error")$(id).textContent=value;
    document.title=(dictionary.title||"Kisa Wallet")+" · KisaMore";
    if($("plansLink"))$("plansLink").textContent=dictionary.navPlans||"Pricing";
    if($("termsLink"))$("termsLink").textContent=(language==="ru"?"Условия использования":window.KisaLocales?.legalMeta?.[language]?.termsTitle||"Terms of Use").replace(/^KisaMore Battle\s*[—–-]\s*/,"");
    $("topupButton").disabled=!topupEnabled||!authed;$("subButton").disabled=!subscriptionEnabled||!authed;
    $("balanceHint").textContent=authed?dictionary.accountHint:dictionary.balanceHint;
    const memberBanner=$("membershipBanner");
    if(memberBanner&&membershipRemaining!==null){const extra=ex[language]||{};
      memberBanner.textContent=(language==="ru"?"Садовод+ активен":extra.memberActive||"Gardener+ active")+" · "+(language==="ru"?"осталось участий":extra.entriesRemaining||"entries remaining")+": "+membershipRemaining;}
    if(!topupEnabled && !subscriptionEnabled){$("topupButton").textContent=dictionary.waiting.length>0?((ex[language]?.unavailablePayments || (language==="ru"?"Оплата пока недоступна":"Payments unavailable"))):"";
      $("subButton").textContent=(ex[language]?.unavailableSub || (language==="ru"?"Подписка пока недоступна":"Subscription unavailable"));}
  }
  translate(lang);
  document.addEventListener("kisamore:language-changed",e=>translate(e.detail.language));
  async function getJSON(url,options){
    const res=await fetch(url,{credentials:"same-origin",cache:"no-store",...options});
    if(!res.ok){
      const payload=await res.json().catch(()=>({}));
      const err=new Error("HTTP "+res.status);
      err.code=payload.detail;
      throw err;
    }
    return res.json();
  }
  Promise.allSettled([getJSON("/api/v1/account/kisa-wallet"),getJSON("/api/v1/payments/catalog"),getJSON("/api/v1/payments/membership")]).then(([wallet,catalog,member])=>{
    if(member.status==="fulfilled" && member.value.active) {
      membershipRemaining=member.value.remaining_entries;
      const banner=document.createElement("div");
      banner.className="notice";banner.id="membershipBanner";
      document.querySelector(".cards").before(banner);
    }
    if(wallet.status==="fulfilled") {authed=true;$("balance").textContent=wallet.value.balance;$("balanceHint").textContent=dictionary.accountHint;}
    if(catalog.status==="fulfilled" && catalog.value.enabled === true){topupEnabled=catalog.value.topup_enabled===true;subscriptionEnabled=catalog.value.subscription_enabled===true;
      $("status").textContent=!authed?dictionary.signIn:(catalog.value.test_mode?dictionary.testReady:dictionary.paymentReady);
      if(!subscriptionEnabled) $("subButton").textContent=$("languageSelect").value==="ru"?"Подписка пока недоступна":"Subscription unavailable";
    } else {$("status").textContent=dictionary.waiting;}
    translate($("languageSelect").value);
  });
  async function pay(kind){if(!authed||(kind==="topup"?!topupEnabled:!subscriptionEnabled))return;
    const button=$(kind==="topup"?"topupButton":"subButton");button.disabled=true;
    $("status").textContent=dictionary.busy;
    const returnOrigin=location.hostname==="ru.kisamore.farm"?"https://ru.kisamore.farm":"https://kisamore.farm";
    const paymentLanguage=$("languageSelect").value==="ru"?"ru":"en";
    try{const data=await getJSON("/api/v1/payments/checkout",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(kind==="topup"?{kind:"topup",kisa:Number(document.querySelector('input[name="amount"]:checked').value),language:paymentLanguage,return_origin:returnOrigin}:{kind:"subscription",language:paymentLanguage,return_origin:returnOrigin})});
      const u=new URL(data.checkout_url);if(u.protocol!=="https:"||!(u.hostname==="lava.top"||u.hostname.endsWith(".lava.top")))throw new Error("Unexpected provider URL");
      location.assign(u.href);
    }catch(err){$("status").textContent=err.code==="lava_buyer_email_rejected"?dictionary.emailRejected:dictionary.error;button.disabled=false;}
  }
  $("topupButton").addEventListener("click",()=>pay("topup"));
  const returned=new URLSearchParams(location.search);
  const invoiceId=returned.get("invoiceId");
  if(invoiceId && /^[0-9a-f-]{36}$/i.test(invoiceId)){
    getJSON("/api/v1/payments/status?invoice_id="+encodeURIComponent(invoiceId)).then(data=>{
      const chosen=window.KisaSiteHeader?.getLanguage()||"en", translated=ex[chosen]||{};
      $("status").textContent=data.status==="paid"
        ?(chosen==="ru"?"Оплата подтверждена! Обновите страницу для нового баланса.":translated.paid||ex.en?.paid)
        :data.status==="failed"
          ?(chosen==="ru"?"Оплата отменена или не прошла. Kisa не начислены.":translated.failed||ex.en?.failed)
          :(chosen==="ru"?"Платёж ещё проверяется. Баланс не изменён.":translated.pending||ex.en?.pending);
    }).catch(()=>{$("status").textContent=dictionary.error;});
  }
  $("subButton").addEventListener("click",()=>pay("subscription"));
})();
