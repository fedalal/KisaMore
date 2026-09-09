from __future__ import annotations

SUPPORTED_LANGUAGES = {"en", "ru", "de", "fr", "es", "it", "pt", "pl", "zh"}


def language_for(tg: dict | None) -> str:
    raw = str((tg or {}).get("language_code") or "en").strip().lower().replace("_", "-")
    base = raw.split("-", 1)[0]
    if base == "zh":
        return "zh"
    return base if base in SUPPORTED_LANGUAGES else "en"


MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "menu_plants": "🌱 Plants",
        "menu_garden": "🪴 My garden",
        "menu_community": "💬 Community",
        "menu_wallet": "🪙 Wallet",
        "menu_profile": "👤 Profile",
        "back_home": "◀️ Main menu",
        "back": "◀️ Back",
        "home": "🌱 <b>KisaMore</b>\n\nHi, {name}!\n\nWatch real plants grow, follow their progress, join the community and later grow your own plant in a rented container.\n\n🪙 Balance: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Kisa wallet</b>",
        "balance": "Balance: <b>{balance} Kisa</b>",
        "wallet_choose": "Choose a package to buy with Telegram Stars.",
        "wallet_terms_required": "Before your first purchase, please accept the KisaMore terms.",
        "read_terms": "📄 Read terms",
        "profile": "👤 <b>Profile</b>\n\nName: {name}\nTelegram: {username}\n🪙 Balance: <b>{balance} Kisa</b>\n\nYour plants, achievements, followers and rewards will appear here.",
        "plants": "🌱 <b>Plants</b>\n\nThe real plant feed with latest photos and timelapses will be connected next.",
        "garden": "🪴 <b>My garden</b>\n\nYour rented containers and plants will appear here.",
        "community": "💬 <b>Community</b>\n\nComments, ratings, contests and Plant Battles will appear here.",
        "terms": "<b>KisaMore Terms (beta)</b>\n\nKisa are internal virtual points used only inside KisaMore. They are not cryptocurrency, have no monetary value outside KisaMore, cannot be withdrawn for money and cannot be transferred between users.\n\nKisa can be earned inside the service and purchased with Telegram Stars. They are used for digital KisaMore features and, later, for access to growing-related services.\n\nBy tapping ‘Accept’, you agree to these terms.",
        "accept": "✅ Accept",
        "terms_accepted": "✅ Terms accepted.",
        "payment_received": "✅ <b>Payment received</b>\n\nAdded: <b>{kisa} Kisa</b>\nNew balance: <b>{balance} Kisa</b>",
        "payment_processing_error": "⚠️ The payment was received but could not be processed automatically. Please use /paysupport.",
        "payment_support_title": "💳 <b>Payment support</b>",
        "support_not_configured": "Support contact is not configured yet.",
        "invoice_description": "Add {kisa} Kisa to your KisaMore balance.",
        "precheckout_error": "We could not verify this order. Please create a new invoice in the KisaMore wallet.",
        "help": "ℹ️ <b>KisaMore help</b>\n\n🌱 /plants — browse plants\n🪴 /garden — your garden\n🪙 /wallet — Kisa wallet\n👤 /profile — profile\n📄 /terms — terms\n💳 /paysupport — payment support",
    },
    "ru": {
        "menu_plants": "🌱 Растения",
        "menu_garden": "🪴 Мой сад",
        "menu_community": "💬 Сообщество",
        "menu_wallet": "🪙 Кошелёк",
        "menu_profile": "👤 Профиль",
        "back_home": "◀️ Главное меню",
        "back": "◀️ Назад",
        "home": "🌱 <b>KisaMore</b>\n\nПривет, {name}!\n\nНаблюдайте за настоящими растениями, следите за ростом, общайтесь и позже выращивайте своё растение в арендованном контейнере.\n\n🪙 Баланс: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Кошелёк Kisa</b>",
        "balance": "Баланс: <b>{balance} Kisa</b>",
        "wallet_choose": "Выберите пакет для покупки через Telegram Stars.",
        "wallet_terms_required": "Перед первой покупкой нужно принять условия KisaMore.",
        "read_terms": "📄 Прочитать условия",
        "profile": "👤 <b>Профиль</b>\n\nИмя: {name}\nTelegram: {username}\n🪙 Баланс: <b>{balance} Kisa</b>\n\nЗдесь появятся выращенные растения, достижения, подписчики и награды.",
        "plants": "🌱 <b>Растения</b>\n\nСледующим этапом подключим реальную ленту растений, последние фото и таймлапсы.",
        "garden": "🪴 <b>Мой сад</b>\n\nЗдесь будут ваши арендованные контейнеры и растения.",
        "community": "💬 <b>Сообщество</b>\n\nЗдесь будут комментарии, рейтинги, соревнования и Plant Battles.",
        "terms": "<b>Условия KisaMore (beta)</b>\n\nKisa — внутренние виртуальные баллы KisaMore. Они не являются криптовалютой, не имеют денежной стоимости вне KisaMore, не выводятся в деньги и не переводятся между пользователями.\n\nKisa можно получать внутри сервиса и покупать за Telegram Stars. Баллы используются для цифровых функций KisaMore и в дальнейшем для доступа к услугам выращивания.\n\nНажимая «Принимаю», вы подтверждаете согласие с этими условиями.",
        "accept": "✅ Принимаю",
        "terms_accepted": "✅ Условия приняты.",
        "payment_received": "✅ <b>Оплата получена</b>\n\nНачислено: <b>{kisa} Kisa</b>\nНовый баланс: <b>{balance} Kisa</b>",
        "payment_processing_error": "⚠️ Платёж получен, но не обработан автоматически. Используйте /paysupport.",
        "payment_support_title": "💳 <b>Поддержка по платежам</b>",
        "support_not_configured": "Контакт поддержки пока не настроен.",
        "invoice_description": "Пополнение внутреннего баланса KisaMore на {kisa} Kisa.",
        "precheckout_error": "Не удалось проверить заказ. Создайте новый счёт в кошельке KisaMore.",
        "help": "ℹ️ <b>Помощь KisaMore</b>\n\n🌱 /plants — растения\n🪴 /garden — мой сад\n🪙 /wallet — кошелёк Kisa\n👤 /profile — профиль\n📄 /terms — условия\n💳 /paysupport — поддержка по оплате",
    },
    "de": {
        "menu_plants": "🌱 Pflanzen", "menu_garden": "🪴 Mein Garten", "menu_community": "💬 Community", "menu_wallet": "🪙 Wallet", "menu_profile": "👤 Profil", "back_home": "◀️ Hauptmenü", "back": "◀️ Zurück",
        "home": "🌱 <b>KisaMore</b>\n\nHallo, {name}!\n\nBeobachte echte Pflanzen beim Wachsen, verfolge ihre Entwicklung, tausche dich mit der Community aus und ziehe später deine eigene Pflanze in einem gemieteten Behälter.\n\n🪙 Guthaben: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Kisa-Wallet</b>", "balance": "Guthaben: <b>{balance} Kisa</b>", "wallet_choose": "Wähle ein Paket zum Kauf mit Telegram Stars.", "wallet_terms_required": "Vor dem ersten Kauf musst du die KisaMore-Bedingungen akzeptieren.", "read_terms": "📄 Bedingungen lesen",
        "profile": "👤 <b>Profil</b>\n\nName: {name}\nTelegram: {username}\n🪙 Guthaben: <b>{balance} Kisa</b>\n\nHier erscheinen später deine Pflanzen, Erfolge, Follower und Belohnungen.",
        "plants": "🌱 <b>Pflanzen</b>\n\nAls Nächstes verbinden wir den echten Pflanzen-Feed mit aktuellen Fotos und Zeitraffern.", "garden": "🪴 <b>Mein Garten</b>\n\nHier erscheinen deine gemieteten Behälter und Pflanzen.", "community": "💬 <b>Community</b>\n\nHier erscheinen Kommentare, Rankings, Wettbewerbe und Plant Battles.",
        "terms": "<b>KisaMore-Bedingungen (Beta)</b>\n\nKisa sind interne virtuelle Punkte, die nur innerhalb von KisaMore verwendet werden. Sie sind keine Kryptowährung, haben außerhalb von KisaMore keinen Geldwert, können nicht ausgezahlt und nicht zwischen Nutzern übertragen werden.\n\nKisa können im Dienst verdient und mit Telegram Stars gekauft werden. Sie werden für digitale KisaMore-Funktionen und später für wachstumsbezogene Dienste verwendet.\n\nMit „Akzeptieren“ stimmst du diesen Bedingungen zu.",
        "accept": "✅ Akzeptieren", "terms_accepted": "✅ Bedingungen akzeptiert.", "payment_received": "✅ <b>Zahlung erhalten</b>\n\nGutgeschrieben: <b>{kisa} Kisa</b>\nNeues Guthaben: <b>{balance} Kisa</b>", "payment_processing_error": "⚠️ Die Zahlung wurde empfangen, aber nicht automatisch verarbeitet. Bitte nutze /paysupport.", "payment_support_title": "💳 <b>Zahlungssupport</b>", "support_not_configured": "Der Support-Kontakt ist noch nicht eingerichtet.", "invoice_description": "{kisa} Kisa zum KisaMore-Guthaben hinzufügen.", "precheckout_error": "Die Bestellung konnte nicht geprüft werden. Bitte erstelle eine neue Rechnung im KisaMore-Wallet.",
        "help": "ℹ️ <b>KisaMore-Hilfe</b>\n\n🌱 /plants — Pflanzen\n🪴 /garden — mein Garten\n🪙 /wallet — Kisa-Wallet\n👤 /profile — Profil\n📄 /terms — Bedingungen\n💳 /paysupport — Zahlungssupport",
    },
    "fr": {
        "menu_plants": "🌱 Plantes", "menu_garden": "🪴 Mon jardin", "menu_community": "💬 Communauté", "menu_wallet": "🪙 Portefeuille", "menu_profile": "👤 Profil", "back_home": "◀️ Menu principal", "back": "◀️ Retour",
        "home": "🌱 <b>KisaMore</b>\n\nBonjour, {name} !\n\nRegardez de vraies plantes pousser, suivez leur évolution, participez à la communauté et, plus tard, faites pousser votre propre plante dans un contenant loué.\n\n🪙 Solde : <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Portefeuille Kisa</b>", "balance": "Solde : <b>{balance} Kisa</b>", "wallet_choose": "Choisissez un pack à acheter avec des Telegram Stars.", "wallet_terms_required": "Avant votre premier achat, veuillez accepter les conditions KisaMore.", "read_terms": "📄 Lire les conditions",
        "profile": "👤 <b>Profil</b>\n\nNom : {name}\nTelegram : {username}\n🪙 Solde : <b>{balance} Kisa</b>\n\nVos plantes, succès, abonnés et récompenses apparaîtront ici.",
        "plants": "🌱 <b>Plantes</b>\n\nLe vrai fil des plantes avec les dernières photos et timelapses sera connecté ensuite.", "garden": "🪴 <b>Mon jardin</b>\n\nVos contenants loués et vos plantes apparaîtront ici.", "community": "💬 <b>Communauté</b>\n\nCommentaires, classements, concours et Plant Battles apparaîtront ici.",
        "terms": "<b>Conditions KisaMore (bêta)</b>\n\nLes Kisa sont des points virtuels internes utilisables uniquement dans KisaMore. Ce ne sont pas des cryptomonnaies, ils n'ont aucune valeur monétaire hors de KisaMore, ne peuvent pas être retirés en argent ni transférés entre utilisateurs.\n\nLes Kisa peuvent être gagnés dans le service et achetés avec des Telegram Stars. Ils servent aux fonctions numériques de KisaMore et, plus tard, à l'accès aux services liés à la culture.\n\nEn appuyant sur « Accepter », vous acceptez ces conditions.",
        "accept": "✅ Accepter", "terms_accepted": "✅ Conditions acceptées.", "payment_received": "✅ <b>Paiement reçu</b>\n\nAjouté : <b>{kisa} Kisa</b>\nNouveau solde : <b>{balance} Kisa</b>", "payment_processing_error": "⚠️ Le paiement a été reçu mais n'a pas pu être traité automatiquement. Utilisez /paysupport.", "payment_support_title": "💳 <b>Assistance paiement</b>", "support_not_configured": "Le contact d'assistance n'est pas encore configuré.", "invoice_description": "Ajouter {kisa} Kisa à votre solde KisaMore.", "precheckout_error": "Impossible de vérifier cette commande. Créez une nouvelle facture dans le portefeuille KisaMore.",
        "help": "ℹ️ <b>Aide KisaMore</b>\n\n🌱 /plants — plantes\n🪴 /garden — mon jardin\n🪙 /wallet — portefeuille Kisa\n👤 /profile — profil\n📄 /terms — conditions\n💳 /paysupport — assistance paiement",
    },
    "es": {
        "menu_plants": "🌱 Plantas", "menu_garden": "🪴 Mi jardín", "menu_community": "💬 Comunidad", "menu_wallet": "🪙 Monedero", "menu_profile": "👤 Perfil", "back_home": "◀️ Menú principal", "back": "◀️ Atrás",
        "home": "🌱 <b>KisaMore</b>\n\n¡Hola, {name}!\n\nObserva cómo crecen plantas reales, sigue su progreso, participa en la comunidad y, más adelante, cultiva tu propia planta en un contenedor alquilado.\n\n🪙 Saldo: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Monedero Kisa</b>", "balance": "Saldo: <b>{balance} Kisa</b>", "wallet_choose": "Elige un paquete para comprar con Telegram Stars.", "wallet_terms_required": "Antes de tu primera compra debes aceptar las condiciones de KisaMore.", "read_terms": "📄 Leer condiciones",
        "profile": "👤 <b>Perfil</b>\n\nNombre: {name}\nTelegram: {username}\n🪙 Saldo: <b>{balance} Kisa</b>\n\nAquí aparecerán tus plantas, logros, seguidores y recompensas.",
        "plants": "🌱 <b>Plantas</b>\n\nA continuación conectaremos el feed real de plantas con fotos recientes y timelapses.", "garden": "🪴 <b>Mi jardín</b>\n\nAquí aparecerán tus contenedores alquilados y tus plantas.", "community": "💬 <b>Comunidad</b>\n\nAquí aparecerán comentarios, clasificaciones, concursos y Plant Battles.",
        "terms": "<b>Condiciones de KisaMore (beta)</b>\n\nKisa son puntos virtuales internos que solo se usan dentro de KisaMore. No son criptomonedas, no tienen valor monetario fuera de KisaMore, no se pueden retirar como dinero ni transferir entre usuarios.\n\nLos Kisa se pueden obtener dentro del servicio y comprar con Telegram Stars. Se usan para funciones digitales de KisaMore y, más adelante, para acceder a servicios relacionados con el cultivo.\n\nAl pulsar «Aceptar», aceptas estas condiciones.",
        "accept": "✅ Aceptar", "terms_accepted": "✅ Condiciones aceptadas.", "payment_received": "✅ <b>Pago recibido</b>\n\nAñadido: <b>{kisa} Kisa</b>\nNuevo saldo: <b>{balance} Kisa</b>", "payment_processing_error": "⚠️ El pago se recibió, pero no pudo procesarse automáticamente. Usa /paysupport.", "payment_support_title": "💳 <b>Soporte de pagos</b>", "support_not_configured": "El contacto de soporte aún no está configurado.", "invoice_description": "Añade {kisa} Kisa a tu saldo de KisaMore.", "precheckout_error": "No pudimos verificar este pedido. Crea una nueva factura en el monedero KisaMore.",
        "help": "ℹ️ <b>Ayuda de KisaMore</b>\n\n🌱 /plants — plantas\n🪴 /garden — mi jardín\n🪙 /wallet — monedero Kisa\n👤 /profile — perfil\n📄 /terms — condiciones\n💳 /paysupport — soporte de pagos",
    },
    "it": {
        "menu_plants": "🌱 Piante", "menu_garden": "🪴 Il mio giardino", "menu_community": "💬 Community", "menu_wallet": "🪙 Portafoglio", "menu_profile": "👤 Profilo", "back_home": "◀️ Menu principale", "back": "◀️ Indietro",
        "home": "🌱 <b>KisaMore</b>\n\nCiao, {name}!\n\nGuarda crescere piante reali, segui i loro progressi, partecipa alla community e in seguito coltiva la tua pianta in un contenitore a noleggio.\n\n🪙 Saldo: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Portafoglio Kisa</b>", "balance": "Saldo: <b>{balance} Kisa</b>", "wallet_choose": "Scegli un pacchetto da acquistare con Telegram Stars.", "wallet_terms_required": "Prima del primo acquisto devi accettare i termini di KisaMore.", "read_terms": "📄 Leggi i termini",
        "profile": "👤 <b>Profilo</b>\n\nNome: {name}\nTelegram: {username}\n🪙 Saldo: <b>{balance} Kisa</b>\n\nQui appariranno le tue piante, i traguardi, i follower e i premi.",
        "plants": "🌱 <b>Piante</b>\n\nIl vero feed delle piante con foto recenti e timelapse sarà collegato nel prossimo passaggio.", "garden": "🪴 <b>Il mio giardino</b>\n\nQui appariranno i contenitori noleggiati e le tue piante.", "community": "💬 <b>Community</b>\n\nQui appariranno commenti, classifiche, concorsi e Plant Battles.",
        "terms": "<b>Termini KisaMore (beta)</b>\n\nI Kisa sono punti virtuali interni utilizzabili solo in KisaMore. Non sono criptovaluta, non hanno valore monetario fuori da KisaMore, non possono essere riscattati in denaro né trasferiti tra utenti.\n\nI Kisa possono essere guadagnati nel servizio e acquistati con Telegram Stars. Sono usati per le funzioni digitali di KisaMore e, in seguito, per accedere ai servizi legati alla coltivazione.\n\nToccando «Accetta» accetti questi termini.",
        "accept": "✅ Accetta", "terms_accepted": "✅ Termini accettati.", "payment_received": "✅ <b>Pagamento ricevuto</b>\n\nAggiunti: <b>{kisa} Kisa</b>\nNuovo saldo: <b>{balance} Kisa</b>", "payment_processing_error": "⚠️ Il pagamento è stato ricevuto ma non elaborato automaticamente. Usa /paysupport.", "payment_support_title": "💳 <b>Supporto pagamenti</b>", "support_not_configured": "Il contatto di supporto non è ancora configurato.", "invoice_description": "Aggiungi {kisa} Kisa al saldo KisaMore.", "precheckout_error": "Impossibile verificare l'ordine. Crea una nuova fattura nel portafoglio KisaMore.",
        "help": "ℹ️ <b>Aiuto KisaMore</b>\n\n🌱 /plants — piante\n🪴 /garden — il mio giardino\n🪙 /wallet — portafoglio Kisa\n👤 /profile — profilo\n📄 /terms — termini\n💳 /paysupport — supporto pagamenti",
    },
    "pt": {
        "menu_plants": "🌱 Plantas", "menu_garden": "🪴 Meu jardim", "menu_community": "💬 Comunidade", "menu_wallet": "🪙 Carteira", "menu_profile": "👤 Perfil", "back_home": "◀️ Menu principal", "back": "◀️ Voltar",
        "home": "🌱 <b>KisaMore</b>\n\nOlá, {name}!\n\nAcompanhe plantas reais crescendo, siga o progresso, participe da comunidade e, mais tarde, cultive sua própria planta em um recipiente alugado.\n\n🪙 Saldo: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Carteira Kisa</b>", "balance": "Saldo: <b>{balance} Kisa</b>", "wallet_choose": "Escolha um pacote para comprar com Telegram Stars.", "wallet_terms_required": "Antes da primeira compra, aceite os termos do KisaMore.", "read_terms": "📄 Ler termos",
        "profile": "👤 <b>Perfil</b>\n\nNome: {name}\nTelegram: {username}\n🪙 Saldo: <b>{balance} Kisa</b>\n\nSuas plantas, conquistas, seguidores e recompensas aparecerão aqui.",
        "plants": "🌱 <b>Plantas</b>\n\nEm seguida conectaremos o feed real de plantas com fotos recentes e timelapses.", "garden": "🪴 <b>Meu jardim</b>\n\nSeus recipientes alugados e suas plantas aparecerão aqui.", "community": "💬 <b>Comunidade</b>\n\nComentários, rankings, concursos e Plant Battles aparecerão aqui.",
        "terms": "<b>Termos do KisaMore (beta)</b>\n\nKisa são pontos virtuais internos usados somente dentro do KisaMore. Não são criptomoeda, não têm valor monetário fora do KisaMore, não podem ser sacados em dinheiro nem transferidos entre usuários.\n\nKisa podem ser ganhos no serviço e comprados com Telegram Stars. Eles são usados em recursos digitais do KisaMore e, futuramente, no acesso a serviços relacionados ao cultivo.\n\nAo tocar em «Aceitar», você concorda com estes termos.",
        "accept": "✅ Aceitar", "terms_accepted": "✅ Termos aceitos.", "payment_received": "✅ <b>Pagamento recebido</b>\n\nAdicionado: <b>{kisa} Kisa</b>\nNovo saldo: <b>{balance} Kisa</b>", "payment_processing_error": "⚠️ O pagamento foi recebido, mas não processado automaticamente. Use /paysupport.", "payment_support_title": "💳 <b>Suporte de pagamentos</b>", "support_not_configured": "O contato de suporte ainda não está configurado.", "invoice_description": "Adicione {kisa} Kisa ao saldo do KisaMore.", "precheckout_error": "Não foi possível verificar o pedido. Crie uma nova fatura na carteira KisaMore.",
        "help": "ℹ️ <b>Ajuda KisaMore</b>\n\n🌱 /plants — plantas\n🪴 /garden — meu jardim\n🪙 /wallet — carteira Kisa\n👤 /profile — perfil\n📄 /terms — termos\n💳 /paysupport — suporte de pagamentos",
    },
    "pl": {
        "menu_plants": "🌱 Rośliny", "menu_garden": "🪴 Mój ogród", "menu_community": "💬 Społeczność", "menu_wallet": "🪙 Portfel", "menu_profile": "👤 Profil", "back_home": "◀️ Menu główne", "back": "◀️ Wstecz",
        "home": "🌱 <b>KisaMore</b>\n\nCześć, {name}!\n\nObserwuj wzrost prawdziwych roślin, śledź ich rozwój, dołącz do społeczności, a później uprawiaj własną roślinę w wynajętym pojemniku.\n\n🪙 Saldo: <b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Portfel Kisa</b>", "balance": "Saldo: <b>{balance} Kisa</b>", "wallet_choose": "Wybierz pakiet do zakupu za Telegram Stars.", "wallet_terms_required": "Przed pierwszym zakupem zaakceptuj warunki KisaMore.", "read_terms": "📄 Przeczytaj warunki",
        "profile": "👤 <b>Profil</b>\n\nImię: {name}\nTelegram: {username}\n🪙 Saldo: <b>{balance} Kisa</b>\n\nTutaj pojawią się Twoje rośliny, osiągnięcia, obserwujący i nagrody.",
        "plants": "🌱 <b>Rośliny</b>\n\nNastępnie podłączymy prawdziwy kanał roślin z najnowszymi zdjęciami i timelapse'ami.", "garden": "🪴 <b>Mój ogród</b>\n\nTutaj pojawią się wynajęte pojemniki i Twoje rośliny.", "community": "💬 <b>Społeczność</b>\n\nTutaj pojawią się komentarze, rankingi, konkursy i Plant Battles.",
        "terms": "<b>Warunki KisaMore (beta)</b>\n\nKisa to wewnętrzne wirtualne punkty używane wyłącznie w KisaMore. Nie są kryptowalutą, nie mają wartości pieniężnej poza KisaMore, nie można ich wypłacić jako pieniędzy ani przesyłać między użytkownikami.\n\nKisa można zdobywać w serwisie i kupować za Telegram Stars. Służą do cyfrowych funkcji KisaMore, a w przyszłości do dostępu do usług związanych z uprawą.\n\nKlikając „Akceptuję”, zgadzasz się na te warunki.",
        "accept": "✅ Akceptuję", "terms_accepted": "✅ Warunki zaakceptowane.", "payment_received": "✅ <b>Płatność otrzymana</b>\n\nDodano: <b>{kisa} Kisa</b>\nNowe saldo: <b>{balance} Kisa</b>", "payment_processing_error": "⚠️ Płatność została otrzymana, ale nie została automatycznie przetworzona. Użyj /paysupport.", "payment_support_title": "💳 <b>Pomoc dotycząca płatności</b>", "support_not_configured": "Kontakt do pomocy nie jest jeszcze skonfigurowany.", "invoice_description": "Dodaj {kisa} Kisa do salda KisaMore.", "precheckout_error": "Nie udało się zweryfikować zamówienia. Utwórz nową fakturę w portfelu KisaMore.",
        "help": "ℹ️ <b>Pomoc KisaMore</b>\n\n🌱 /plants — rośliny\n🪴 /garden — mój ogród\n🪙 /wallet — portfel Kisa\n👤 /profile — profil\n📄 /terms — warunki\n💳 /paysupport — pomoc dotycząca płatności",
    },
    "zh": {
        "menu_plants": "🌱 植物", "menu_garden": "🪴 我的花园", "menu_community": "💬 社区", "menu_wallet": "🪙 钱包", "menu_profile": "👤 个人资料", "back_home": "◀️ 主菜单", "back": "◀️ 返回",
        "home": "🌱 <b>KisaMore</b>\n\n你好，{name}！\n\n观看真实植物生长，关注它们的进度，参与社区互动，并在之后租用种植容器培育属于自己的真实植物。\n\n🪙 余额：<b>{balance} Kisa</b>",
        "wallet_title": "🪙 <b>Kisa 钱包</b>", "balance": "余额：<b>{balance} Kisa</b>", "wallet_choose": "请选择使用 Telegram Stars 购买的套餐。", "wallet_terms_required": "首次购买前，请先接受 KisaMore 使用条款。", "read_terms": "📄 阅读条款",
        "profile": "👤 <b>个人资料</b>\n\n姓名：{name}\nTelegram：{username}\n🪙 余额：<b>{balance} Kisa</b>\n\n你的植物、成就、关注者和奖励将显示在这里。",
        "plants": "🌱 <b>植物</b>\n\n下一步将接入真实植物动态、最新照片和延时视频。", "garden": "🪴 <b>我的花园</b>\n\n你租用的种植容器和植物将显示在这里。", "community": "💬 <b>社区</b>\n\n这里将提供评论、排行榜、比赛和 Plant Battles。",
        "terms": "<b>KisaMore 使用条款（Beta）</b>\n\nKisa 是仅可在 KisaMore 内使用的虚拟积分。它不是加密货币，在 KisaMore 之外不具有货币价值，不能兑换现金，也不能在用户之间转移。\n\nKisa 可以在服务内获得，也可以使用 Telegram Stars 购买。它用于 KisaMore 的数字功能，未来还将用于与种植相关的服务。\n\n点击“接受”即表示你同意这些条款。",
        "accept": "✅ 接受", "terms_accepted": "✅ 已接受条款。", "payment_received": "✅ <b>已收到付款</b>\n\n已增加：<b>{kisa} Kisa</b>\n新余额：<b>{balance} Kisa</b>", "payment_processing_error": "⚠️ 已收到付款，但未能自动处理。请使用 /paysupport。", "payment_support_title": "💳 <b>付款支持</b>", "support_not_configured": "尚未配置支持联系方式。", "invoice_description": "向你的 KisaMore 余额增加 {kisa} Kisa。", "precheckout_error": "无法验证此订单。请在 KisaMore 钱包中重新创建付款单。",
        "help": "ℹ️ <b>KisaMore 帮助</b>\n\n🌱 /plants — 植物\n🪴 /garden — 我的花园\n🪙 /wallet — Kisa 钱包\n👤 /profile — 个人资料\n📄 /terms — 使用条款\n💳 /paysupport — 付款支持",
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    messages = MESSAGES.get(lang) or MESSAGES["en"]
    template = messages.get(key) or MESSAGES["en"].get(key) or key
    return template.format(**kwargs)
