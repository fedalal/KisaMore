(() => {
  "use strict";
  const strings = {
    en: {
      navHome:"Greenhouse",navBattles:"Battles",navPricing:"Options & pricing",navKisa:"Kisa Ⓚ",
      eyebrow:"ONE REAL GREENHOUSE · TWO WAYS TO GROW",
      title:"What would you like to grow?",
      lead:"Choose a plant just for yourself — or test your gardening skills in a battle with other growers.",
      choicesTitle:"Choose your growing experience",
      soloKicker:"OPTION 1 · PERSONAL GROWING",soloTitle:"Grow your own plant",
      soloDesc:"Choose the crop you like. We'll plant it in a real greenhouse, and you can follow its growth online — without competing against anyone.",
      soloF1:"Choose the type of plant you want to grow",soloF2:"Your own growing container in the greenhouse",soloF3:"Watch photos, progress and timelapses",
      soloPriceLabel:"PRICE",soloPrice:"Depends on the plant you choose",soloPriceNote:"Each crop has its own price in Ⓚ and growing period.",soloCta:"Choose a plant ↗",
      battleKicker:"OPTION 2 · GROWING COMPETITION",battleTitle:"Join a plant battle",
      battleDesc:"Six participants grow the same plant under equal starting conditions. Make your own watering, nutrient and shading decisions — and see who wins.",
      battleF1:"The same crop and starting resources for everyone",battleF2:"Control water, nutrients and shade",battleF3:"Compare results and receive achievements",
      battlePriceLabel:"PRICING",battlePrice:"20 Ⓚ per battle or 30 Ⓚ / month",battlePriceNote:"Monthly membership includes up to 3 battles.",battleCta:"Compare battle plans ↓",
      freeTitle:"Just want to watch?",freeDesc:"Watching the greenhouse, battles and public timelapses is always free. No subscription needed.",freeCta:"Watch for free ↗",
      plansEyebrow:"ONLY FOR PLANT BATTLES",plansTitle:"Choose how often you want to compete",
      plansLead:"These prices apply to competitions. Growing your own chosen plant is a separate service with crop-dependent pricing.",
      onceKicker:"ONE-TIME ENTRY",onceTitle:"One battle",onceUnit:"one-time",onceDesc:"One real plant in one complete competition. No recurring charges.",
      onceF1:"One container in one battle",onceF2:"Watering, nutrient and shading controls",onceF3:"Photos, timelapses and competition results",
      subKicker:"MONTHLY MEMBERSHIP",subTitle:"Gardener+",subUnit:"/ month",subDesc:"Join up to three different battles each paid month. Each battle has the same fair resources.",
      subF1:"Up to 3 battle entries per paid month",subF2:"One container per battle",subF3:"Started battles continue after cancellation",
      betterDeal:"SAVE 50% ON 3 BATTLES",paymentSoon:"Card payments coming soon",walletCta:"View Kisa wallet",
      kisaTitle:"Ⓚ is the internal currency of KisaMore",kisaText:"Ⓚ is used for growing plants and joining battles; it cannot be cashed out.",
      paymentNote:"Payment is being configured. Open your Kisa wallet to view the available options.",
      faqEyebrow:"QUESTIONS & ANSWERS",faqTitle:"How it works",faqLead:"The difference between a personal plant and a competition.",
      q1:"What is the difference between growing a plant and joining a battle?",
      a1:"For personal growing, you pick the plant species and follow your own container without competing. In a battle, participants receive identical plants and resources and compete on the result.",
      q2:"How much does personal growing cost?",
      a2:"The price and growing time depend on your chosen crop. Available plants and their current prices in Ⓚ are listed on the greenhouse page.",
      q3:"Do I need a subscription to grow my own plant?",
      a3:"No. Personal growing is separate from the battle membership. You choose a plant and pay for its growing cycle.",
      q4:"Can I cancel Gardener+?",
      a4:"Yes. The membership won't renew after cancellation. A battle you've already started continues until its end.",
      closingTitle:"Real plants. Your choice.",closingDesc:"Start by choosing a plant or exploring the battles — everything grows in a real greenhouse.",
      closingPlant:"Choose a plant",closingBattle:"Explore battles",footerTag:"Grow something real.",privacy:"Privacy"
    },
    ru: {
      navHome:"Теплица",navBattles:"Битвы",navPricing:"Тарифы",navKisa:"Kisa Ⓚ",
      eyebrow:"ОДНА НАСТОЯЩАЯ ТЕПЛИЦА · ДВА СПОСОБА ВЫРАЩИВАНИЯ",
      title:"Что ты хочешь вырастить?",
      lead:"Выбери растение для себя — или проверь свои навыки в битве с другими садоводами.",
      choicesTitle:"Выбери способ выращивания",
      soloKicker:"ВАРИАНТ 1 · ВЫРАЩИВАНИЕ ДЛЯ СЕБЯ",soloTitle:"Посадить своё растение",
      soloDesc:"Выбери понравившуюся культуру. Мы посадим её в настоящей теплице, а ты будешь следить за ростом через сайт — без соревнования с другими.",
      soloF1:"Сам выбираешь, какое растение посадить",soloF2:"Собственный контейнер в реальной теплице",soloF3:"Фотографии, прогресс и таймлапсы",
      soloPriceLabel:"СТОИМОСТЬ",soloPrice:"Зависит от выбранного растения",soloPriceNote:"Цена в Ⓚ и срок выращивания указаны для каждой культуры.",soloCta:"Выбрать растение ↗",
      battleKicker:"ВАРИАНТ 2 · СОРЕВНОВАНИЕ",battleTitle:"Участвовать в битве",
      battleDesc:"Шесть участников выращивают одинаковые растения в равных стартовых условиях. Решай, когда поливать, добавлять питание и затемнять растение, и соревнуйся за победу.",
      battleF1:"Одинаковые растения и ресурсы для всех",battleF2:"Управление водой, питанием и затемнением",battleF3:"Сравнение результатов и награды",
      battlePriceLabel:"СТОИМОСТЬ",battlePrice:"20 Ⓚ за битву или 30 Ⓚ в месяц",battlePriceNote:"Подписка включает до 3 битв за месяц.",battleCta:"Сравнить тарифы битв ↓",
      freeTitle:"Хочешь просто наблюдать?",freeDesc:"Смотреть теплицу, битвы и общие таймлапсы можно бесплатно. Подписка не требуется.",freeCta:"Смотреть бесплатно ↗",
      plansEyebrow:"ТАРИФЫ ТОЛЬКО ДЛЯ БИТВ",plansTitle:"Выбери, как часто соревноваться",
      plansLead:"Эти цены относятся только к соревнованиям. Выращивание собственного выбранного растения — отдельная услуга, стоимость зависит от культуры.",
      onceKicker:"РАЗОВОЕ УЧАСТИЕ",onceTitle:"Одна битва",onceUnit:"разово",onceDesc:"Одно настоящее растение в одном полном соревновании. Без регулярных списаний.",
      onceF1:"Один контейнер в одной битве",onceF2:"Управление поливом, питанием и затемнением",onceF3:"Фотографии, таймлапсы и результаты",
      subKicker:"ЕЖЕМЕСЯЧНАЯ ПОДПИСКА",subTitle:"Садовод+",subUnit:"/ мес.",subDesc:"До трёх разных битв за оплаченный месяц. В каждой битве сохраняются равные условия.",
      subF1:"До 3 участий в битвах за оплаченный месяц",subF2:"Один контейнер в каждой битве",subF3:"Начатые битвы продолжаются после отмены",
      betterDeal:"ЭКОНОМИЯ 50% НА 3 БИТВАХ",paymentSoon:"Оплата картой скоро",walletCta:"Открыть кошелёк Kisa",
      kisaTitle:"Ⓚ — внутренняя валюта KisaMore",kisaText:"Ⓚ можно тратить на выращивание растений и участие в битвах, но нельзя обменять на деньги или вывести.",
      paymentNote:"Оплата подключается. Открой кошелёк Kisa, чтобы посмотреть доступные варианты.",
      faqEyebrow:"ВОПРОСЫ И ОТВЕТЫ",faqTitle:"Как это работает",faqLead:"Чем собственная посадка отличается от соревнования.",
      q1:"Чем отличается обычная посадка от участия в битве?",
      a1:"При обычной посадке ты сам выбираешь культуру и следишь за своим контейнером без соревнования. В битве участники выращивают одинаковые растения с равными ресурсами и сравнивают результаты.",
      q2:"Сколько стоит посадка своего растения?",
      a2:"Цена и срок роста зависят от выбранной культуры. Доступные растения и их актуальная стоимость в Ⓚ указаны на странице теплицы.",
      q3:"Нужна ли подписка для обычного выращивания?",
      a3:"Нет. Обычная посадка не зависит от подписки на битвы. Ты выбираешь растение и оплачиваешь его цикл выращивания.",
      q4:"Можно ли отменить подписку «Садовод+»?",
      a4:"Да. После отмены новые списания не выполняются. Уже начатую оплаченную битву можно завершить.",
      closingTitle:"Настоящие растения. Твой выбор.",closingDesc:"Выбери растение или посмотри соревнования — всё происходит в реальной теплице.",
      closingPlant:"Выбрать растение",closingBattle:"Смотреть битвы",footerTag:"Выращивай настоящее.",privacy:"Конфиденциальность"
    }
  };
  const languageSelect=document.getElementById("languageSelect");
  const query=new URLSearchParams(location.search).get("lang");
  const saved=localStorage.getItem("battleLang") || localStorage.getItem("kisamore-language");
  const browser=(navigator.language||"en").slice(0,2).toLowerCase();
  function apply(lang) {
    const chosen=lang==="ru"?"ru":"en", labels=strings[chosen];
    document.documentElement.lang=chosen;
    languageSelect.value=lang;
    document.querySelectorAll("[data-i18n]").forEach(node=>{
      const key=node.getAttribute("data-i18n");
      if(Object.prototype.hasOwnProperty.call(labels,key)) {
        const icon=node.querySelector('[aria-hidden="true"]');
        node.textContent=labels[key];
        // The navigation arrows are included in the translated labels.
      }
    });
    document.title=chosen==="ru"?"Выращивание и тарифы — KisaMore":"Growing options & pricing — KisaMore";
    document.querySelector('meta[name="description"]').content=chosen==="ru"
      ?"Выращивай выбранное растение или участвуй в битвах KisaMore. Посадка по цене культуры, битва — 20 Ⓚ, подписка — 30 Ⓚ в месяц."
      :"Grow your own plant or join a KisaMore battle. Personal growing is priced per crop. Battles: 20 Ⓚ each or 30 Ⓚ monthly.";
  }
  apply(window.KisaSiteHeader?.getLanguage() || (query==="en" || query==="ru"?query:(saved||browser)));
  document.addEventListener("kisamore:language-changed", event=>apply(event.detail.language));
})();
