(() => {
  "use strict";

  const translations = {
    en: {
      smartGreenhouse: "smart greenhouse", signIn: "Sign in", signOut: "Sign out", connecting: "Connecting…", online: "Greenhouse online", offline: "Greenhouse offline", waiting: "Waiting for data", liveFarm: "Live farm", waitingData: "Waiting for the first data", lastSeen: "Last contact", refresh: "Refresh", racks: "racks", containers: "containers", available: "available", growing: "growing", choosePlace: "Choose a place", greenhouseRacks: "Greenhouse racks", rackHint: "Each rack has six container positions. Lighting and watering are shared within a rack.", loading: "Loading greenhouse data…", footerText: "Grow something real from anywhere in the world.", growingZone: "Growing zone", rack: "Rack", container: "Container", lightOn: "light on", lightOff: "light off", waterOn: "watering", waterOff: "not watering", noData: "no data", buyRack: "Get whole rack", reserveRack: "Reserve rack", buy: "Get container", reserve: "Join waitlist", occupied: "Occupied", ready: "Ready to harvest", maintenance: "Cleaning", disabled: "Unavailable", expected: "Expected", signInTitle: "Sign in", registerTitle: "Create account", createAccount: "Create account", haveAccount: "I already have an account", needAccount: "Create a new account", displayName: "Name", email: "Email", password: "Password", preferredPlant: "Preferred plant", anyPlant: "Decide later", sharedControls: "Lighting and watering settings are shared by all six containers on this rack.", cancel: "Cancel", confirmPurchase: "Confirm test purchase", confirmReservation: "Join waitlist", purchaseTitle: "Choose this place", reservationTitle: "Reserve for later", purchaseDescription: "This test purchase activates the container immediately. Real payment will be connected later.", reservationDescription: "We will create an offer when the selected place becomes available.", personalAccount: "Personal account", allocations: "My containers and racks", reservations: "Waitlist", offers: "Available offers", notifications: "Notifications", empty: "Nothing here yet", acceptOffer: "Accept offer", release: "Finish rental", status: "Status", updated: "Updated", loadError: "Could not load greenhouse data.", actionError: "Could not complete the action.", authError: "Check your details and try again.", passwordHint: "Password must contain at least 10 characters.", reservationCreated: "Reservation created.", purchaseCreated: "Container assigned to your account.", offerUntil: "Offer valid until"
    },
    ru: {
      smartGreenhouse: "умная теплица", signIn: "Войти", signOut: "Выйти", connecting: "Подключение…", online: "Теплица в сети", offline: "Теплица не в сети", waiting: "Ожидаем данные", liveFarm: "Прямой эфир с фермы", waitingData: "Ожидаем первые данные", lastSeen: "Последняя связь", refresh: "Обновить", racks: "полок", containers: "контейнеров", available: "свободно", growing: "растёт", choosePlace: "Выберите место", greenhouseRacks: "Полки теплицы", rackHint: "На каждой полке шесть контейнеров. Свет и полив общие для всей полки.", loading: "Получаем данные теплицы…", footerText: "Выращивайте настоящие растения из любой точки мира.", growingZone: "Зона выращивания", rack: "Полка", container: "Контейнер", lightOn: "свет включён", lightOff: "свет выключен", waterOn: "идёт полив", waterOff: "полив выключен", noData: "нет данных", buyRack: "Получить всю полку", reserveRack: "Забронировать полку", buy: "Получить контейнер", reserve: "Встать в очередь", occupied: "Занят", ready: "Готов к уборке", maintenance: "Очистка", disabled: "Недоступен", expected: "Плановая уборка", signInTitle: "Вход", registerTitle: "Регистрация", createAccount: "Создать аккаунт", haveAccount: "У меня уже есть аккаунт", needAccount: "Создать новый аккаунт", displayName: "Имя", email: "Email", password: "Пароль", preferredPlant: "Желаемое растение", anyPlant: "Выбрать позже", sharedControls: "Свет и полив общие для всех шести контейнеров на этой полке.", cancel: "Отмена", confirmPurchase: "Подтвердить тестовую покупку", confirmReservation: "Встать в очередь", purchaseTitle: "Выбрать это место", reservationTitle: "Забронировать на будущее", purchaseDescription: "Тестовая покупка сразу закрепит место за вами. Реальная оплата будет подключена позднее.", reservationDescription: "Когда выбранное место освободится, мы создадим для вас предложение.", personalAccount: "Личный кабинет", allocations: "Мои контейнеры и полки", reservations: "Очередь бронирования", offers: "Доступные предложения", notifications: "Уведомления", empty: "Здесь пока ничего нет", acceptOffer: "Принять предложение", release: "Завершить аренду", status: "Статус", updated: "Обновлено", loadError: "Не удалось загрузить данные теплицы.", actionError: "Не удалось выполнить действие.", authError: "Проверьте данные и попробуйте снова.", passwordHint: "Пароль должен содержать не менее 10 символов.", reservationCreated: "Бронирование создано.", purchaseCreated: "Место закреплено за вашим аккаунтом.", offerUntil: "Предложение действует до"
    },
    de: {
      smartGreenhouse: "intelligentes Gewächshaus", signIn: "Anmelden", signOut: "Abmelden", connecting: "Verbindung…", online: "Gewächshaus online", offline: "Gewächshaus offline", waiting: "Warten auf Daten", liveFarm: "Live von der Farm", waitingData: "Warten auf erste Daten", lastSeen: "Letzter Kontakt", refresh: "Aktualisieren", racks: "Regale", containers: "Behälter", available: "frei", growing: "im Anbau", choosePlace: "Platz auswählen", greenhouseRacks: "Gewächshausregale", rackHint: "Jedes Regal hat sechs Behälter. Licht und Bewässerung werden pro Regal geteilt.", loading: "Gewächshausdaten werden geladen…", footerText: "Bauen Sie echte Pflanzen von überall aus an.", growingZone: "Anbauzone", rack: "Regal", container: "Behälter", lightOn: "Licht an", lightOff: "Licht aus", waterOn: "Bewässerung", waterOff: "keine Bewässerung", noData: "keine Daten", buyRack: "Ganzes Regal wählen", reserveRack: "Regal reservieren", buy: "Behälter wählen", reserve: "Warteliste", occupied: "Belegt", ready: "Erntebereit", maintenance: "Reinigung", disabled: "Nicht verfügbar", expected: "Geplant", signInTitle: "Anmelden", registerTitle: "Konto erstellen", createAccount: "Konto erstellen", haveAccount: "Ich habe bereits ein Konto", needAccount: "Neues Konto erstellen", displayName: "Name", email: "E-Mail", password: "Passwort", preferredPlant: "Bevorzugte Pflanze", anyPlant: "Später entscheiden", sharedControls: "Licht und Bewässerung werden von allen sechs Behältern geteilt.", cancel: "Abbrechen", confirmPurchase: "Testkauf bestätigen", confirmReservation: "Warteliste beitreten", purchaseTitle: "Diesen Platz wählen", reservationTitle: "Für später reservieren", purchaseDescription: "Der Testkauf aktiviert den Platz sofort. Die echte Zahlung folgt später.", reservationDescription: "Wir erstellen ein Angebot, sobald der Platz frei wird.", personalAccount: "Persönliches Konto", allocations: "Meine Plätze", reservations: "Warteliste", offers: "Verfügbare Angebote", notifications: "Benachrichtigungen", empty: "Noch keine Einträge", acceptOffer: "Angebot annehmen", release: "Miete beenden", status: "Status", updated: "Aktualisiert", loadError: "Gewächshausdaten konnten nicht geladen werden.", actionError: "Aktion konnte nicht abgeschlossen werden.", authError: "Angaben prüfen und erneut versuchen.", passwordHint: "Das Passwort muss mindestens 10 Zeichen haben.", reservationCreated: "Reservierung erstellt.", purchaseCreated: "Platz wurde Ihrem Konto zugewiesen.", offerUntil: "Angebot gültig bis"
    },
    fr: {
      smartGreenhouse: "serre intelligente", signIn: "Connexion", signOut: "Déconnexion", connecting: "Connexion…", online: "Serre en ligne", offline: "Serre hors ligne", waiting: "En attente des données", liveFarm: "Ferme en direct", waitingData: "En attente des premières données", lastSeen: "Dernier contact", refresh: "Actualiser", racks: "étagères", containers: "conteneurs", available: "libres", growing: "en culture", choosePlace: "Choisissez une place", greenhouseRacks: "Étagères de la serre", rackHint: "Chaque étagère contient six conteneurs. L'éclairage et l'arrosage sont partagés.", loading: "Chargement des données…", footerText: "Cultivez de vraies plantes depuis partout.", growingZone: "Zone de culture", rack: "Étagère", container: "Conteneur", lightOn: "lumière allumée", lightOff: "lumière éteinte", waterOn: "arrosage", waterOff: "sans arrosage", noData: "aucune donnée", buyRack: "Choisir toute l'étagère", reserveRack: "Réserver l'étagère", buy: "Choisir le conteneur", reserve: "Liste d'attente", occupied: "Occupé", ready: "Prêt à récolter", maintenance: "Nettoyage", disabled: "Indisponible", expected: "Prévu", signInTitle: "Connexion", registerTitle: "Créer un compte", createAccount: "Créer un compte", haveAccount: "J'ai déjà un compte", needAccount: "Créer un nouveau compte", displayName: "Nom", email: "E-mail", password: "Mot de passe", preferredPlant: "Plante préférée", anyPlant: "Décider plus tard", sharedControls: "L'éclairage et l'arrosage sont partagés entre les six conteneurs.", cancel: "Annuler", confirmPurchase: "Confirmer l'achat test", confirmReservation: "Rejoindre la liste", purchaseTitle: "Choisir cette place", reservationTitle: "Réserver pour plus tard", purchaseDescription: "L'achat test active immédiatement la place. Le paiement réel sera ajouté plus tard.", reservationDescription: "Nous créerons une offre lorsque la place se libérera.", personalAccount: "Compte personnel", allocations: "Mes emplacements", reservations: "Liste d'attente", offers: "Offres disponibles", notifications: "Notifications", empty: "Aucun élément", acceptOffer: "Accepter l'offre", release: "Terminer la location", status: "Statut", updated: "Mis à jour", loadError: "Impossible de charger les données.", actionError: "Impossible de terminer l'action.", authError: "Vérifiez vos informations.", passwordHint: "Le mot de passe doit contenir au moins 10 caractères.", reservationCreated: "Réservation créée.", purchaseCreated: "La place est attribuée à votre compte.", offerUntil: "Offre valable jusqu'au"
    },
    es: {
      smartGreenhouse: "invernadero inteligente", signIn: "Entrar", signOut: "Salir", connecting: "Conectando…", online: "Invernadero en línea", offline: "Invernadero desconectado", waiting: "Esperando datos", liveFarm: "Granja en directo", waitingData: "Esperando los primeros datos", lastSeen: "Último contacto", refresh: "Actualizar", racks: "estantes", containers: "contenedores", available: "libres", growing: "cultivando", choosePlace: "Elige un lugar", greenhouseRacks: "Estantes del invernadero", rackHint: "Cada estante tiene seis contenedores. La luz y el riego son compartidos.", loading: "Cargando datos…", footerText: "Cultiva plantas reales desde cualquier lugar.", growingZone: "Zona de cultivo", rack: "Estante", container: "Contenedor", lightOn: "luz encendida", lightOff: "luz apagada", waterOn: "regando", waterOff: "sin riego", noData: "sin datos", buyRack: "Elegir estante completo", reserveRack: "Reservar estante", buy: "Elegir contenedor", reserve: "Lista de espera", occupied: "Ocupado", ready: "Listo para cosechar", maintenance: "Limpieza", disabled: "No disponible", expected: "Previsto", signInTitle: "Entrar", registerTitle: "Crear cuenta", createAccount: "Crear cuenta", haveAccount: "Ya tengo una cuenta", needAccount: "Crear una cuenta nueva", displayName: "Nombre", email: "Correo", password: "Contraseña", preferredPlant: "Planta preferida", anyPlant: "Decidir después", sharedControls: "La iluminación y el riego se comparten entre los seis contenedores.", cancel: "Cancelar", confirmPurchase: "Confirmar compra de prueba", confirmReservation: "Unirse a la lista", purchaseTitle: "Elegir este lugar", reservationTitle: "Reservar para después", purchaseDescription: "La compra de prueba activa el lugar de inmediato. El pago real se añadirá más adelante.", reservationDescription: "Crearemos una oferta cuando el lugar quede libre.", personalAccount: "Cuenta personal", allocations: "Mis lugares", reservations: "Lista de espera", offers: "Ofertas disponibles", notifications: "Notificaciones", empty: "Todavía no hay nada", acceptOffer: "Aceptar oferta", release: "Finalizar alquiler", status: "Estado", updated: "Actualizado", loadError: "No se pudieron cargar los datos.", actionError: "No se pudo completar la acción.", authError: "Comprueba tus datos.", passwordHint: "La contraseña debe tener al menos 10 caracteres.", reservationCreated: "Reserva creada.", purchaseCreated: "El lugar fue asignado a tu cuenta.", offerUntil: "Oferta válida hasta"
    },
    it: {
      smartGreenhouse: "serra intelligente", signIn: "Accedi", signOut: "Esci", connecting: "Connessione…", online: "Serra online", offline: "Serra offline", waiting: "In attesa dei dati", liveFarm: "Fattoria in diretta", waitingData: "In attesa dei primi dati", lastSeen: "Ultimo contatto", refresh: "Aggiorna", racks: "scaffali", containers: "contenitori", available: "liberi", growing: "in crescita", choosePlace: "Scegli un posto", greenhouseRacks: "Scaffali della serra", rackHint: "Ogni scaffale ha sei contenitori. Illuminazione e irrigazione sono condivise.", loading: "Caricamento dati…", footerText: "Coltiva piante vere da qualsiasi luogo.", growingZone: "Zona di coltivazione", rack: "Scaffale", container: "Contenitore", lightOn: "luce accesa", lightOff: "luce spenta", waterOn: "irrigazione", waterOff: "non irrigato", noData: "nessun dato", buyRack: "Scegli tutto lo scaffale", reserveRack: "Prenota scaffale", buy: "Scegli contenitore", reserve: "Lista d'attesa", occupied: "Occupato", ready: "Pronto al raccolto", maintenance: "Pulizia", disabled: "Non disponibile", expected: "Previsto", signInTitle: "Accedi", registerTitle: "Crea account", createAccount: "Crea account", haveAccount: "Ho già un account", needAccount: "Crea un nuovo account", displayName: "Nome", email: "Email", password: "Password", preferredPlant: "Pianta preferita", anyPlant: "Decidi dopo", sharedControls: "Illuminazione e irrigazione sono condivise tra i sei contenitori.", cancel: "Annulla", confirmPurchase: "Conferma acquisto di prova", confirmReservation: "Entra in lista", purchaseTitle: "Scegli questo posto", reservationTitle: "Prenota per dopo", purchaseDescription: "L'acquisto di prova attiva subito il posto. Il pagamento reale sarà aggiunto più avanti.", reservationDescription: "Creeremo un'offerta quando il posto sarà libero.", personalAccount: "Account personale", allocations: "I miei posti", reservations: "Lista d'attesa", offers: "Offerte disponibili", notifications: "Notifiche", empty: "Ancora nessun elemento", acceptOffer: "Accetta offerta", release: "Termina noleggio", status: "Stato", updated: "Aggiornato", loadError: "Impossibile caricare i dati.", actionError: "Impossibile completare l'azione.", authError: "Controlla i dati.", passwordHint: "La password deve contenere almeno 10 caratteri.", reservationCreated: "Prenotazione creata.", purchaseCreated: "Il posto è stato assegnato al tuo account.", offerUntil: "Offerta valida fino al"
    },
    pt: {
      smartGreenhouse: "estufa inteligente", signIn: "Entrar", signOut: "Sair", connecting: "A ligar…", online: "Estufa online", offline: "Estufa offline", waiting: "A aguardar dados", liveFarm: "Quinta em direto", waitingData: "A aguardar os primeiros dados", lastSeen: "Último contacto", refresh: "Atualizar", racks: "prateleiras", containers: "recipientes", available: "livres", growing: "a crescer", choosePlace: "Escolha um lugar", greenhouseRacks: "Prateleiras da estufa", rackHint: "Cada prateleira tem seis recipientes. A luz e a rega são partilhadas.", loading: "A carregar dados…", footerText: "Cultive plantas reais a partir de qualquer lugar.", growingZone: "Zona de cultivo", rack: "Prateleira", container: "Recipiente", lightOn: "luz ligada", lightOff: "luz desligada", waterOn: "a regar", waterOff: "sem rega", noData: "sem dados", buyRack: "Escolher prateleira inteira", reserveRack: "Reservar prateleira", buy: "Escolher recipiente", reserve: "Lista de espera", occupied: "Ocupado", ready: "Pronto para colher", maintenance: "Limpeza", disabled: "Indisponível", expected: "Previsto", signInTitle: "Entrar", registerTitle: "Criar conta", createAccount: "Criar conta", haveAccount: "Já tenho uma conta", needAccount: "Criar nova conta", displayName: "Nome", email: "Email", password: "Palavra-passe", preferredPlant: "Planta preferida", anyPlant: "Decidir depois", sharedControls: "A iluminação e a rega são partilhadas pelos seis recipientes.", cancel: "Cancelar", confirmPurchase: "Confirmar compra de teste", confirmReservation: "Entrar na lista", purchaseTitle: "Escolher este lugar", reservationTitle: "Reservar para depois", purchaseDescription: "A compra de teste ativa o lugar imediatamente. O pagamento real será adicionado depois.", reservationDescription: "Criaremos uma oferta quando o lugar ficar livre.", personalAccount: "Conta pessoal", allocations: "Os meus lugares", reservations: "Lista de espera", offers: "Ofertas disponíveis", notifications: "Notificações", empty: "Ainda não há nada", acceptOffer: "Aceitar oferta", release: "Terminar aluguer", status: "Estado", updated: "Atualizado", loadError: "Não foi possível carregar os dados.", actionError: "Não foi possível concluir a ação.", authError: "Verifique os seus dados.", passwordHint: "A palavra-passe deve ter pelo menos 10 caracteres.", reservationCreated: "Reserva criada.", purchaseCreated: "O lugar foi atribuído à sua conta.", offerUntil: "Oferta válida até"
    },
    pl: {
      smartGreenhouse: "inteligentna szklarnia", signIn: "Zaloguj się", signOut: "Wyloguj się", connecting: "Łączenie…", online: "Szklarnia online", offline: "Szklarnia offline", waiting: "Oczekiwanie na dane", liveFarm: "Transmisja z farmy", waitingData: "Oczekiwanie na pierwsze dane", lastSeen: "Ostatni kontakt", refresh: "Odśwież", racks: "półki", containers: "pojemniki", available: "wolne", growing: "rośnie", choosePlace: "Wybierz miejsce", greenhouseRacks: "Półki szklarni", rackHint: "Każda półka ma sześć pojemników. Oświetlenie i podlewanie są wspólne.", loading: "Ładowanie danych…", footerText: "Uprawiaj prawdziwe rośliny z dowolnego miejsca.", growingZone: "Strefa uprawy", rack: "Półka", container: "Pojemnik", lightOn: "światło włączone", lightOff: "światło wyłączone", waterOn: "podlewanie", waterOff: "bez podlewania", noData: "brak danych", buyRack: "Wybierz całą półkę", reserveRack: "Zarezerwuj półkę", buy: "Wybierz pojemnik", reserve: "Lista oczekujących", occupied: "Zajęty", ready: "Gotowy do zbioru", maintenance: "Czyszczenie", disabled: "Niedostępny", expected: "Planowany termin", signInTitle: "Logowanie", registerTitle: "Utwórz konto", createAccount: "Utwórz konto", haveAccount: "Mam już konto", needAccount: "Utwórz nowe konto", displayName: "Imię", email: "Email", password: "Hasło", preferredPlant: "Preferowana roślina", anyPlant: "Wybierz później", sharedControls: "Oświetlenie i podlewanie są wspólne dla wszystkich sześciu pojemników.", cancel: "Anuluj", confirmPurchase: "Potwierdź zakup testowy", confirmReservation: "Dołącz do listy", purchaseTitle: "Wybierz to miejsce", reservationTitle: "Zarezerwuj na później", purchaseDescription: "Zakup testowy natychmiast aktywuje miejsce. Prawdziwa płatność zostanie dodana później.", reservationDescription: "Utworzymy ofertę, gdy miejsce będzie wolne.", personalAccount: "Konto osobiste", allocations: "Moje miejsca", reservations: "Lista oczekujących", offers: "Dostępne oferty", notifications: "Powiadomienia", empty: "Jeszcze nic tu nie ma", acceptOffer: "Przyjmij ofertę", release: "Zakończ wynajem", status: "Status", updated: "Zaktualizowano", loadError: "Nie udało się wczytać danych.", actionError: "Nie udało się wykonać działania.", authError: "Sprawdź dane i spróbuj ponownie.", passwordHint: "Hasło musi mieć co najmniej 10 znaków.", reservationCreated: "Utworzono rezerwację.", purchaseCreated: "Miejsce przypisano do konta.", offerUntil: "Oferta ważna do"
    },
    zh: {
      smartGreenhouse: "智能温室", signIn: "登录", signOut: "退出", connecting: "正在连接…", online: "温室在线", offline: "温室离线", waiting: "等待数据", liveFarm: "农场实时状态", waitingData: "等待首次数据", lastSeen: "上次连接", refresh: "刷新", racks: "种植架", containers: "容器", available: "空闲", growing: "生长中", choosePlace: "选择位置", greenhouseRacks: "温室种植架", rackHint: "每个架子有六个容器。照明和灌溉由整架共享。", loading: "正在加载温室数据…", footerText: "从世界任何地方种植真实植物。", growingZone: "种植区", rack: "架子", container: "容器", lightOn: "灯光开启", lightOff: "灯光关闭", waterOn: "正在灌溉", waterOff: "未灌溉", noData: "无数据", buyRack: "选择整架", reserveRack: "预订整架", buy: "选择容器", reserve: "加入等待名单", occupied: "已占用", ready: "可收获", maintenance: "清洁中", disabled: "不可用", expected: "预计收获", signInTitle: "登录", registerTitle: "创建账户", createAccount: "创建账户", haveAccount: "我已有账户", needAccount: "创建新账户", displayName: "姓名", email: "电子邮箱", password: "密码", preferredPlant: "首选植物", anyPlant: "稍后决定", sharedControls: "该架六个容器共享照明和灌溉设置。", cancel: "取消", confirmPurchase: "确认测试购买", confirmReservation: "加入等待名单", purchaseTitle: "选择此位置", reservationTitle: "预约未来位置", purchaseDescription: "测试购买会立即分配位置，真实支付将在之后接入。", reservationDescription: "位置空闲时，我们会为您创建限时购买邀请。", personalAccount: "个人账户", allocations: "我的容器和架子", reservations: "等待名单", offers: "可用邀请", notifications: "通知", empty: "暂无内容", acceptOffer: "接受邀请", release: "结束租用", status: "状态", updated: "更新时间", loadError: "无法加载温室数据。", actionError: "无法完成操作。", authError: "请检查信息后重试。", passwordHint: "密码至少需要10个字符。", reservationCreated: "预约已创建。", purchaseCreated: "位置已分配到您的账户。", offerUntil: "邀请有效期至"
    }
  };


  const commercialTranslations = {
    en: {
      navHow: "How it works", navPlants: "Plants", navLive: "Live greenhouse", navKisa: "KISA",
      heroEyebrow: "A real greenhouse, online", heroTitle: "Grow something real from anywhere.",
      heroLead: "Choose a plant, rent a real container and follow its growth with live greenhouse data, photos and timelapses.",
      heroLiveCta: "Open live greenhouse", heroPlantsCta: "Choose a plant", heroNote: "Free to watch. Rent only when you want your own plant.",
      liveNow: "LIVE NOW", seeGreenhouse: "See the greenhouse",
      howEyebrow: "How KisaMore works", howTitle: "Your plant is real. The interface is online.",
      howLead: "KisaMore connects a physical greenhouse with a simple digital experience.",
      step1Title: "Choose what to grow", step1Body: "Pick an available crop and a real container in the greenhouse.",
      step2Title: "Watch it grow", step2Body: "Follow current photos, greenhouse status and growth progress from anywhere.",
      step3Title: "Keep the story", step3Body: "Get timelapses and updates that turn the growing cycle into a story you can share.",
      plantsEyebrow: "Choose your crop", plantsTitle: "What can we grow for you?",
      plantsLead: "Availability comes directly from the greenhouse. Rental price depends on the selected crop.",
      growTime: "Grow time", daysShort: "days", rentalFrom: "Rental", choosePlaceCta: "Choose a place", plantFallback: "A real crop available for your greenhouse container.",
      liveEyebrow: "Real greenhouse", liveTitle: "Live racks and containers", liveLead: "These are real places in the greenhouse, not a simulation.",
      pricingEyebrow: "KISA credits", pricingTitle: "Watch for free. Pay only for your own growing space.",
      pricingLead: "KISA is the internal credit used for rentals and extra paid actions. Credits can be topped up through the KisaMore Telegram bot using Telegram Stars.",
      freeBadge: "FREE", freeTitle: "Observer", freeFeature1: "Watch the live greenhouse", freeFeature2: "See current rack photos", freeFeature3: "Explore available plants and places", freeCta: "Watch now",
      popularBadge: "YOUR PLANT", containerTitle: "Container rental", from: "from", containerFeature1: "A real greenhouse container", containerFeature2: "Choose the crop you want", containerFeature3: "Photos, progress and timelapse", containerCta: "Choose a container",
      proBadge: "FULL RACK", rackPlanTitle: "Private rack", byRequest: "By request", rackFeature1: "All six container positions", rackFeature2: "One growing zone reserved for you", rackFeature3: "Suitable for experiments and projects", rackCta: "Ask in Telegram",
      tokenTitle: "KISA keeps payments simple", tokenBody: "Top up once in Telegram and use your balance for rentals and paid features inside KisaMore.", tokenCta: "Open @KisaMoreBot",
      telegramEyebrow: "KisaMore in Telegram", telegramTitle: "Your greenhouse can live in your pocket.", telegramBody: "Get plant updates, notifications and KISA credits through the Telegram bot. The website stays your full live view and personal account.", telegramCta: "Open Telegram bot", accountCta: "Personal account"
    },
    ru: {
      navHow: "Как это работает", navPlants: "Растения", navLive: "Теплица онлайн", navKisa: "KISA",
      heroEyebrow: "Настоящая теплица онлайн", heroTitle: "Выращивайте настоящее растение из любой точки мира.",
      heroLead: "Выберите растение, арендуйте реальный контейнер и следите за ростом по фотографиям, данным теплицы и таймлапсам.",
      heroLiveCta: "Открыть теплицу", heroPlantsCta: "Выбрать растение", heroNote: "Наблюдать можно бесплатно. Платите только когда хотите выращивать своё растение.",
      liveNow: "СЕЙЧАС В ЭФИРЕ", seeGreenhouse: "Смотреть теплицу",
      howEyebrow: "Как работает KisaMore", howTitle: "Растение настоящее. Управление — онлайн.",
      howLead: "KisaMore соединяет реальную теплицу с простым цифровым сервисом.",
      step1Title: "Выберите растение", step1Body: "Выберите доступную культуру и реальный контейнер в теплице.",
      step2Title: "Наблюдайте за ростом", step2Body: "Смотрите свежие фотографии, состояние теплицы и прогресс выращивания из любой точки мира.",
      step3Title: "Сохраните историю", step3Body: "Получайте таймлапсы и обновления, чтобы весь цикл выращивания остался у вас.",
      plantsEyebrow: "Выберите культуру", plantsTitle: "Что вы хотите вырастить?",
      plantsLead: "Доступность приходит прямо из теплицы. Стоимость аренды зависит от выбранного растения.",
      growTime: "Срок роста", daysShort: "дн.", rentalFrom: "Аренда", choosePlaceCta: "Выбрать место", plantFallback: "Реальная культура, доступная для выращивания в вашем контейнере.",
      liveEyebrow: "Реальная теплица", liveTitle: "Полки и контейнеры онлайн", liveLead: "Это реальные места в теплице, а не симуляция.",
      pricingEyebrow: "Кредиты KISA", pricingTitle: "Наблюдайте бесплатно. Платите только за своё место.",
      pricingLead: "KISA — внутренняя валюта для аренды и дополнительных платных функций. Пополнить баланс можно через Telegram-бот KisaMore с помощью Telegram Stars.",
      freeBadge: "БЕСПЛАТНО", freeTitle: "Наблюдатель", freeFeature1: "Смотреть теплицу онлайн", freeFeature2: "Смотреть актуальные фото полок", freeFeature3: "Изучать доступные растения и места", freeCta: "Смотреть сейчас",
      popularBadge: "СВОЁ РАСТЕНИЕ", containerTitle: "Аренда контейнера", from: "от", containerFeature1: "Реальный контейнер в теплице", containerFeature2: "Выбор растения для выращивания", containerFeature3: "Фото, прогресс и таймлапс", containerCta: "Выбрать контейнер",
      proBadge: "ЦЕЛАЯ ПОЛКА", rackPlanTitle: "Личная полка", byRequest: "По запросу", rackFeature1: "Все шесть контейнеров", rackFeature2: "Отдельная зона выращивания только для вас", rackFeature3: "Подходит для экспериментов и проектов", rackCta: "Спросить в Telegram",
      tokenTitle: "С KISA всё просто", tokenBody: "Один раз пополните баланс в Telegram и используйте его для аренды и платных возможностей KisaMore.", tokenCta: "Открыть @KisaMoreBot",
      telegramEyebrow: "KisaMore в Telegram", telegramTitle: "Ваша теплица всегда в кармане.", telegramBody: "Получайте обновления растений, уведомления и KISA через Telegram-бота. На сайте остаются полный live-просмотр и личный кабинет.", telegramCta: "Открыть Telegram-бот", accountCta: "Личный кабинет"
    },
    de: {
      navHow: "So funktioniert es", navPlants: "Pflanzen", navLive: "Live-Gewächshaus", navKisa: "KISA",
      heroEyebrow: "Ein echtes Gewächshaus online", heroTitle: "Bauen Sie etwas Echtes von überall aus an.",
      heroLead: "Wählen Sie eine Pflanze, mieten Sie einen echten Behälter und verfolgen Sie das Wachstum mit Live-Daten, Fotos und Zeitraffern.",
      heroLiveCta: "Live-Gewächshaus öffnen", heroPlantsCta: "Pflanze wählen", heroNote: "Zuschauen ist kostenlos. Bezahlen Sie nur für Ihren eigenen Anbauplatz.",
      liveNow: "JETZT LIVE", seeGreenhouse: "Gewächshaus ansehen",
      howEyebrow: "So funktioniert KisaMore", howTitle: "Ihre Pflanze ist echt. Die Oberfläche ist online.", howLead: "KisaMore verbindet ein reales Gewächshaus mit einem einfachen digitalen Erlebnis.",
      step1Title: "Pflanze auswählen", step1Body: "Wählen Sie eine verfügbare Kultur und einen echten Behälter.", step2Title: "Wachstum beobachten", step2Body: "Verfolgen Sie aktuelle Fotos, Gewächshausstatus und Fortschritt.", step3Title: "Geschichte behalten", step3Body: "Erhalten Sie Zeitraffer und Updates über den gesamten Anbauzyklus.",
      plantsEyebrow: "Kultur auswählen", plantsTitle: "Was dürfen wir für Sie anbauen?", plantsLead: "Verfügbarkeit kommt direkt aus dem Gewächshaus. Der Mietpreis hängt von der Kultur ab.", growTime: "Anbauzeit", daysShort: "Tage", rentalFrom: "Miete", choosePlaceCta: "Platz wählen", plantFallback: "Eine echte Kultur für Ihren Gewächshausbehälter.",
      liveEyebrow: "Echtes Gewächshaus", liveTitle: "Live-Regale und Behälter", liveLead: "Das sind reale Plätze im Gewächshaus, keine Simulation.",
      pricingEyebrow: "KISA-Guthaben", pricingTitle: "Kostenlos zuschauen. Nur für den eigenen Anbauplatz zahlen.", pricingLead: "KISA ist das interne Guthaben für Mieten und Zusatzfunktionen. Aufladen ist über den Telegram-Bot mit Telegram Stars möglich.",
      freeBadge: "KOSTENLOS", freeTitle: "Beobachter", freeFeature1: "Live-Gewächshaus ansehen", freeFeature2: "Aktuelle Regalfotos sehen", freeFeature3: "Pflanzen und Plätze entdecken", freeCta: "Jetzt ansehen",
      popularBadge: "IHRE PFLANZE", containerTitle: "Behälter mieten", from: "ab", containerFeature1: "Echter Gewächshausbehälter", containerFeature2: "Gewünschte Kultur wählen", containerFeature3: "Fotos, Fortschritt und Zeitraffer", containerCta: "Behälter wählen",
      proBadge: "GANZES REGAL", rackPlanTitle: "Privates Regal", byRequest: "Auf Anfrage", rackFeature1: "Alle sechs Behälterplätze", rackFeature2: "Eine Anbauzone nur für Sie", rackFeature3: "Für Experimente und Projekte", rackCta: "In Telegram fragen",
      tokenTitle: "KISA macht Zahlungen einfach", tokenBody: "Einmal in Telegram aufladen und das Guthaben für Mieten und Funktionen nutzen.", tokenCta: "@KisaMoreBot öffnen",
      telegramEyebrow: "KisaMore in Telegram", telegramTitle: "Ihr Gewächshaus passt in die Tasche.", telegramBody: "Erhalten Sie Pflanzen-Updates, Benachrichtigungen und KISA im Telegram-Bot. Die Website bleibt Ihre vollständige Live-Ansicht.", telegramCta: "Telegram-Bot öffnen", accountCta: "Persönliches Konto"
    },
    fr: {
      navHow: "Comment ça marche", navPlants: "Plantes", navLive: "Serre en direct", navKisa: "KISA",
      heroEyebrow: "Une vraie serre en ligne", heroTitle: "Cultivez quelque chose de réel, où que vous soyez.",
      heroLead: "Choisissez une plante, louez un vrai conteneur et suivez sa croissance avec les données, photos et timelapses.",
      heroLiveCta: "Ouvrir la serre en direct", heroPlantsCta: "Choisir une plante", heroNote: "Observer est gratuit. Vous payez seulement pour votre propre espace.",
      liveNow: "EN DIRECT", seeGreenhouse: "Voir la serre",
      howEyebrow: "Comment fonctionne KisaMore", howTitle: "Votre plante est réelle. L'interface est en ligne.", howLead: "KisaMore relie une serre physique à une expérience numérique simple.",
      step1Title: "Choisissez votre plante", step1Body: "Choisissez une culture disponible et un vrai conteneur.", step2Title: "Suivez sa croissance", step2Body: "Consultez les photos, l'état de la serre et la progression.", step3Title: "Gardez son histoire", step3Body: "Recevez des timelapses et des mises à jour pendant tout le cycle.",
      plantsEyebrow: "Choisissez votre culture", plantsTitle: "Que pouvons-nous cultiver pour vous ?", plantsLead: "La disponibilité vient directement de la serre. Le prix dépend de la culture.", growTime: "Durée", daysShort: "jours", rentalFrom: "Location", choosePlaceCta: "Choisir une place", plantFallback: "Une vraie culture disponible pour votre conteneur.",
      liveEyebrow: "Vraie serre", liveTitle: "Étagères et conteneurs en direct", liveLead: "Ce sont de vraies places dans la serre, pas une simulation.",
      pricingEyebrow: "Crédits KISA", pricingTitle: "Observez gratuitement. Payez seulement pour votre espace.", pricingLead: "KISA est le crédit interne pour les locations et fonctions payantes. Rechargez via le bot Telegram avec Telegram Stars.",
      freeBadge: "GRATUIT", freeTitle: "Observateur", freeFeature1: "Voir la serre en direct", freeFeature2: "Voir les photos actuelles", freeFeature3: "Explorer plantes et places", freeCta: "Voir maintenant",
      popularBadge: "VOTRE PLANTE", containerTitle: "Location d'un conteneur", from: "à partir de", containerFeature1: "Un vrai conteneur", containerFeature2: "Choisissez votre culture", containerFeature3: "Photos, progression et timelapse", containerCta: "Choisir un conteneur",
      proBadge: "ÉTAGÈRE ENTIÈRE", rackPlanTitle: "Étagère privée", byRequest: "Sur demande", rackFeature1: "Les six emplacements", rackFeature2: "Une zone réservée pour vous", rackFeature3: "Pour expériences et projets", rackCta: "Demander sur Telegram",
      tokenTitle: "KISA simplifie les paiements", tokenBody: "Rechargez une fois dans Telegram et utilisez votre solde pour les locations et fonctions.", tokenCta: "Ouvrir @KisaMoreBot",
      telegramEyebrow: "KisaMore sur Telegram", telegramTitle: "Votre serre tient dans votre poche.", telegramBody: "Recevez mises à jour, notifications et KISA via le bot Telegram. Le site reste votre vue complète.", telegramCta: "Ouvrir le bot Telegram", accountCta: "Compte personnel"
    },
    es: {
      navHow: "Cómo funciona", navPlants: "Plantas", navLive: "Invernadero en vivo", navKisa: "KISA",
      heroEyebrow: "Un invernadero real, online", heroTitle: "Cultiva algo real desde cualquier lugar.", heroLead: "Elige una planta, alquila un contenedor real y sigue su crecimiento con datos, fotos y timelapses.", heroLiveCta: "Abrir invernadero", heroPlantsCta: "Elegir planta", heroNote: "Mirar es gratis. Solo pagas por tu propio espacio.",
      liveNow: "EN DIRECTO", seeGreenhouse: "Ver invernadero",
      howEyebrow: "Cómo funciona KisaMore", howTitle: "Tu planta es real. La interfaz está online.", howLead: "KisaMore conecta un invernadero físico con una experiencia digital sencilla.", step1Title: "Elige qué cultivar", step1Body: "Elige un cultivo disponible y un contenedor real.", step2Title: "Mira cómo crece", step2Body: "Sigue fotos, estado y progreso desde cualquier lugar.", step3Title: "Guarda la historia", step3Body: "Recibe timelapses y actualizaciones durante todo el ciclo.",
      plantsEyebrow: "Elige tu cultivo", plantsTitle: "¿Qué podemos cultivar para ti?", plantsLead: "La disponibilidad llega directamente del invernadero. El precio depende del cultivo.", growTime: "Tiempo", daysShort: "días", rentalFrom: "Alquiler", choosePlaceCta: "Elegir lugar", plantFallback: "Un cultivo real disponible para tu contenedor.",
      liveEyebrow: "Invernadero real", liveTitle: "Estantes y contenedores en vivo", liveLead: "Son lugares reales del invernadero, no una simulación.",
      pricingEyebrow: "Créditos KISA", pricingTitle: "Mira gratis. Paga solo por tu propio espacio.", pricingLead: "KISA es el crédito interno para alquileres y funciones de pago. Puedes recargarlo en Telegram con Telegram Stars.",
      freeBadge: "GRATIS", freeTitle: "Observador", freeFeature1: "Ver el invernadero en vivo", freeFeature2: "Ver fotos actuales", freeFeature3: "Explorar plantas y lugares", freeCta: "Ver ahora",
      popularBadge: "TU PLANTA", containerTitle: "Alquiler de contenedor", from: "desde", containerFeature1: "Un contenedor real", containerFeature2: "Elige el cultivo", containerFeature3: "Fotos, progreso y timelapse", containerCta: "Elegir contenedor",
      proBadge: "ESTANTE COMPLETO", rackPlanTitle: "Estante privado", byRequest: "A consultar", rackFeature1: "Los seis contenedores", rackFeature2: "Una zona reservada para ti", rackFeature3: "Para experimentos y proyectos", rackCta: "Preguntar en Telegram",
      tokenTitle: "KISA simplifica los pagos", tokenBody: "Recarga una vez en Telegram y usa tu saldo para alquileres y funciones.", tokenCta: "Abrir @KisaMoreBot",
      telegramEyebrow: "KisaMore en Telegram", telegramTitle: "Tu invernadero cabe en tu bolsillo.", telegramBody: "Recibe novedades, notificaciones y KISA en el bot. La web sigue siendo tu vista completa.", telegramCta: "Abrir bot de Telegram", accountCta: "Cuenta personal"
    },
    it: {
      navHow: "Come funziona", navPlants: "Piante", navLive: "Serra live", navKisa: "KISA",
      heroEyebrow: "Una vera serra online", heroTitle: "Coltiva qualcosa di reale ovunque ti trovi.", heroLead: "Scegli una pianta, noleggia un vero contenitore e segui la crescita con dati, foto e timelapse.", heroLiveCta: "Apri la serra live", heroPlantsCta: "Scegli una pianta", heroNote: "Guardare è gratis. Paghi solo per il tuo spazio.",
      liveNow: "LIVE ORA", seeGreenhouse: "Vedi la serra",
      howEyebrow: "Come funziona KisaMore", howTitle: "La tua pianta è reale. L'interfaccia è online.", howLead: "KisaMore collega una serra fisica a un'esperienza digitale semplice.", step1Title: "Scegli cosa coltivare", step1Body: "Scegli una coltura disponibile e un vero contenitore.", step2Title: "Guardala crescere", step2Body: "Segui foto, stato e progresso da qualsiasi luogo.", step3Title: "Conserva la storia", step3Body: "Ricevi timelapse e aggiornamenti per tutto il ciclo.",
      plantsEyebrow: "Scegli la coltura", plantsTitle: "Cosa possiamo coltivare per te?", plantsLead: "La disponibilità arriva direttamente dalla serra. Il prezzo dipende dalla coltura.", growTime: "Tempo", daysShort: "giorni", rentalFrom: "Noleggio", choosePlaceCta: "Scegli posto", plantFallback: "Una coltura reale disponibile per il tuo contenitore.",
      liveEyebrow: "Serra reale", liveTitle: "Scaffali e contenitori live", liveLead: "Sono posti reali nella serra, non una simulazione.",
      pricingEyebrow: "Crediti KISA", pricingTitle: "Guarda gratis. Paga solo per il tuo spazio.", pricingLead: "KISA è il credito interno per noleggi e funzioni a pagamento. Ricarica via Telegram con Telegram Stars.",
      freeBadge: "GRATIS", freeTitle: "Osservatore", freeFeature1: "Guarda la serra live", freeFeature2: "Vedi foto aggiornate", freeFeature3: "Esplora piante e posti", freeCta: "Guarda ora",
      popularBadge: "LA TUA PIANTA", containerTitle: "Noleggio contenitore", from: "da", containerFeature1: "Un vero contenitore", containerFeature2: "Scegli la coltura", containerFeature3: "Foto, progresso e timelapse", containerCta: "Scegli contenitore",
      proBadge: "SCAFFALE INTERO", rackPlanTitle: "Scaffale privato", byRequest: "Su richiesta", rackFeature1: "Tutti e sei i contenitori", rackFeature2: "Una zona riservata a te", rackFeature3: "Per esperimenti e progetti", rackCta: "Chiedi su Telegram",
      tokenTitle: "KISA rende semplici i pagamenti", tokenBody: "Ricarica una volta in Telegram e usa il saldo per noleggi e funzioni.", tokenCta: "Apri @KisaMoreBot",
      telegramEyebrow: "KisaMore su Telegram", telegramTitle: "La tua serra può stare in tasca.", telegramBody: "Ricevi aggiornamenti, notifiche e KISA nel bot. Il sito resta la tua vista completa.", telegramCta: "Apri bot Telegram", accountCta: "Account personale"
    },
    pt: {
      navHow: "Como funciona", navPlants: "Plantas", navLive: "Estufa ao vivo", navKisa: "KISA",
      heroEyebrow: "Uma estufa real online", heroTitle: "Cultive algo real a partir de qualquer lugar.", heroLead: "Escolha uma planta, alugue um recipiente real e acompanhe o crescimento com dados, fotos e timelapses.", heroLiveCta: "Abrir estufa ao vivo", heroPlantsCta: "Escolher planta", heroNote: "Observar é grátis. Pague apenas pelo seu espaço.",
      liveNow: "AO VIVO", seeGreenhouse: "Ver estufa",
      howEyebrow: "Como funciona o KisaMore", howTitle: "A sua planta é real. A interface é online.", howLead: "KisaMore liga uma estufa física a uma experiência digital simples.", step1Title: "Escolha o que cultivar", step1Body: "Escolha uma cultura disponível e um recipiente real.", step2Title: "Veja crescer", step2Body: "Acompanhe fotos, estado e progresso de qualquer lugar.", step3Title: "Guarde a história", step3Body: "Receba timelapses e atualizações durante todo o ciclo.",
      plantsEyebrow: "Escolha a cultura", plantsTitle: "O que podemos cultivar para si?", plantsLead: "A disponibilidade vem diretamente da estufa. O preço depende da cultura.", growTime: "Tempo", daysShort: "dias", rentalFrom: "Aluguer", choosePlaceCta: "Escolher lugar", plantFallback: "Uma cultura real disponível para o seu recipiente.",
      liveEyebrow: "Estufa real", liveTitle: "Prateleiras e recipientes ao vivo", liveLead: "São lugares reais na estufa, não uma simulação.",
      pricingEyebrow: "Créditos KISA", pricingTitle: "Observe grátis. Pague apenas pelo seu espaço.", pricingLead: "KISA é o crédito interno para alugueres e funções pagas. Recarregue no Telegram com Telegram Stars.",
      freeBadge: "GRÁTIS", freeTitle: "Observador", freeFeature1: "Ver estufa ao vivo", freeFeature2: "Ver fotos atuais", freeFeature3: "Explorar plantas e lugares", freeCta: "Ver agora",
      popularBadge: "A SUA PLANTA", containerTitle: "Aluguer de recipiente", from: "desde", containerFeature1: "Um recipiente real", containerFeature2: "Escolha a cultura", containerFeature3: "Fotos, progresso e timelapse", containerCta: "Escolher recipiente",
      proBadge: "PRATELEIRA INTEIRA", rackPlanTitle: "Prateleira privada", byRequest: "Sob consulta", rackFeature1: "Todos os seis recipientes", rackFeature2: "Uma zona reservada para si", rackFeature3: "Para experiências e projetos", rackCta: "Perguntar no Telegram",
      tokenTitle: "KISA simplifica os pagamentos", tokenBody: "Recarregue uma vez no Telegram e use o saldo em alugueres e funções.", tokenCta: "Abrir @KisaMoreBot",
      telegramEyebrow: "KisaMore no Telegram", telegramTitle: "A sua estufa cabe no bolso.", telegramBody: "Receba atualizações, notificações e KISA no bot. O site continua a ser a sua vista completa.", telegramCta: "Abrir bot Telegram", accountCta: "Conta pessoal"
    },
    pl: {
      navHow: "Jak to działa", navPlants: "Rośliny", navLive: "Szklarnia na żywo", navKisa: "KISA",
      heroEyebrow: "Prawdziwa szklarnia online", heroTitle: "Uprawiaj coś prawdziwego z dowolnego miejsca.", heroLead: "Wybierz roślinę, wynajmij prawdziwy pojemnik i śledź wzrost dzięki danym, zdjęciom i timelapse.", heroLiveCta: "Otwórz szklarnię", heroPlantsCta: "Wybierz roślinę", heroNote: "Oglądanie jest bezpłatne. Płacisz tylko za własne miejsce.",
      liveNow: "NA ŻYWO", seeGreenhouse: "Zobacz szklarnię",
      howEyebrow: "Jak działa KisaMore", howTitle: "Twoja roślina jest prawdziwa. Interfejs jest online.", howLead: "KisaMore łączy fizyczną szklarnię z prostą usługą cyfrową.", step1Title: "Wybierz roślinę", step1Body: "Wybierz dostępną uprawę i prawdziwy pojemnik.", step2Title: "Obserwuj wzrost", step2Body: "Śledź zdjęcia, stan szklarni i postęp.", step3Title: "Zachowaj historię", step3Body: "Otrzymuj timelapse i aktualizacje przez cały cykl.",
      plantsEyebrow: "Wybierz uprawę", plantsTitle: "Co możemy dla Ciebie wyhodować?", plantsLead: "Dostępność pochodzi bezpośrednio ze szklarni. Cena zależy od rośliny.", growTime: "Czas", daysShort: "dni", rentalFrom: "Wynajem", choosePlaceCta: "Wybierz miejsce", plantFallback: "Prawdziwa uprawa dostępna w Twoim pojemniku.",
      liveEyebrow: "Prawdziwa szklarnia", liveTitle: "Półki i pojemniki na żywo", liveLead: "To prawdziwe miejsca w szklarni, nie symulacja.",
      pricingEyebrow: "Kredyty KISA", pricingTitle: "Oglądaj za darmo. Płać tylko za własne miejsce.", pricingLead: "KISA to wewnętrzne środki na wynajem i płatne funkcje. Doładuj je w Telegramie przez Telegram Stars.",
      freeBadge: "ZA DARMO", freeTitle: "Obserwator", freeFeature1: "Oglądaj szklarnię na żywo", freeFeature2: "Zobacz aktualne zdjęcia", freeFeature3: "Przeglądaj rośliny i miejsca", freeCta: "Oglądaj teraz",
      popularBadge: "TWOJA ROŚLINA", containerTitle: "Wynajem pojemnika", from: "od", containerFeature1: "Prawdziwy pojemnik", containerFeature2: "Wybierz roślinę", containerFeature3: "Zdjęcia, postęp i timelapse", containerCta: "Wybierz pojemnik",
      proBadge: "CAŁA PÓŁKA", rackPlanTitle: "Prywatna półka", byRequest: "Na zapytanie", rackFeature1: "Wszystkie sześć miejsc", rackFeature2: "Jedna strefa tylko dla Ciebie", rackFeature3: "Do eksperymentów i projektów", rackCta: "Zapytaj w Telegramie",
      tokenTitle: "KISA upraszcza płatności", tokenBody: "Doładuj raz w Telegramie i używaj salda do wynajmu i funkcji.", tokenCta: "Otwórz @KisaMoreBot",
      telegramEyebrow: "KisaMore w Telegramie", telegramTitle: "Twoja szklarnia może być w kieszeni.", telegramBody: "Otrzymuj aktualizacje, powiadomienia i KISA w bocie. Strona pozostaje pełnym widokiem live.", telegramCta: "Otwórz bota Telegram", accountCta: "Konto osobiste"
    },
    zh: {
      navHow: "如何运作", navPlants: "植物", navLive: "温室直播", navKisa: "KISA",
      heroEyebrow: "真实温室，在线体验", heroTitle: "无论身在何处，都能种植真实植物。", heroLead: "选择植物，租用真实种植容器，通过温室数据、照片和延时视频关注生长。", heroLiveCta: "打开温室直播", heroPlantsCta: "选择植物", heroNote: "观看免费。只有拥有自己的种植空间时才需付费。",
      liveNow: "正在直播", seeGreenhouse: "查看温室",
      howEyebrow: "KisaMore 如何运作", howTitle: "植物是真实的，界面在线。", howLead: "KisaMore 将实体温室与简单的数字体验连接起来。", step1Title: "选择种植内容", step1Body: "选择可用作物和真实容器。", step2Title: "观察生长", step2Body: "随时查看照片、温室状态和生长进度。", step3Title: "保存成长故事", step3Body: "获取延时视频和整个生长周期的更新。",
      plantsEyebrow: "选择作物", plantsTitle: "我们可以为您种什么？", plantsLead: "可用情况直接来自温室，租金取决于所选作物。", growTime: "生长周期", daysShort: "天", rentalFrom: "租金", choosePlaceCta: "选择位置", plantFallback: "可在您的真实温室容器中种植的作物。",
      liveEyebrow: "真实温室", liveTitle: "实时种植架和容器", liveLead: "这些都是真实温室中的位置，并非模拟。",
      pricingEyebrow: "KISA 积分", pricingTitle: "免费观看，只为自己的种植空间付费。", pricingLead: "KISA 是用于租赁和付费功能的内部积分，可通过 Telegram Stars 在 KisaMore 机器人中充值。",
      freeBadge: "免费", freeTitle: "观察者", freeFeature1: "观看温室直播", freeFeature2: "查看最新种植架照片", freeFeature3: "浏览植物和可用位置", freeCta: "立即观看",
      popularBadge: "您的植物", containerTitle: "容器租赁", from: "起", containerFeature1: "真实温室容器", containerFeature2: "选择想种的作物", containerFeature3: "照片、进度和延时视频", containerCta: "选择容器",
      proBadge: "整架", rackPlanTitle: "私人种植架", byRequest: "按需咨询", rackFeature1: "全部六个容器位置", rackFeature2: "专属于您的种植区", rackFeature3: "适合实验和项目", rackCta: "在 Telegram 咨询",
      tokenTitle: "KISA 让支付更简单", tokenBody: "在 Telegram 中充值一次，即可使用余额支付租赁和功能。", tokenCta: "打开 @KisaMoreBot",
      telegramEyebrow: "Telegram 中的 KisaMore", telegramTitle: "您的温室可以装进口袋。", telegramBody: "通过 Telegram 机器人获取植物更新、通知和 KISA。网站仍是完整的实时视图和个人账户。", telegramCta: "打开 Telegram 机器人", accountCta: "个人账户"
    }
  };

  const farmSlug = document.querySelector('meta[name="kisamore-farm-slug"]').content;
  let language = localStorage.getItem("kisamore-language") || "en";
  if (!translations[language]) language = "en";
  let liveData = null;
  let marketData = null;
  let user = null;
  let account = null;
  let authMode = "login";
  let pendingAction = null;

  const $ = (selector, root = document) => root.querySelector(selector);
  const t = (key) => commercialTranslations[language]?.[key] || translations[language]?.[key] || commercialTranslations.en[key] || translations.en[key] || key;
  const locale = () => ({ en: "en-US", ru: "ru-RU", de: "de-DE", fr: "fr-FR", es: "es-ES", it: "it-IT", pt: "pt-PT", pl: "pl-PL", zh: "zh-CN" }[language]);
  const plantName = (plant) => plant?.names?.[language] || plant?.names?.en || plant?.names?.ru || plant?.code || "—";
  const plantDescription = (plant) => plant?.descriptions?.[language] || plant?.descriptions?.en || plant?.descriptions?.ru || t("plantFallback");
  const temperatureLabel = () => ({
    en: "Temperature",
    ru: "Температура",
    de: "Temperatur",
    fr: "Température",
    es: "Temperatura",
    it: "Temperatura",
    pt: "Temperatura",
    pl: "Temperatura",
    zh: "温度"
  }[language] || "Temperature");

  const slotUiText = () => ({
    en: { planted: "Planted", day: "Day", like: "Like", dislike: "Dislike", gift: "Gift", comments: "Comments", full: "Full cycle" },
    ru: { planted: "Посажено", day: "День", like: "Лайк", dislike: "Дизлайк", gift: "Донат", comments: "Комментарии", full: "Весь цикл" },
    de: { planted: "Gepflanzt", day: "Tag", like: "Gefällt", dislike: "Gefällt nicht", gift: "Geschenk", comments: "Kommentare", full: "Gesamter Zyklus" },
    fr: { planted: "Planté", day: "Jour", like: "J’aime", dislike: "Je n’aime pas", gift: "Don", comments: "Commentaires", full: "Cycle complet" },
    es: { planted: "Plantado", day: "Día", like: "Me gusta", dislike: "No me gusta", gift: "Donar", comments: "Comentarios", full: "Ciclo completo" },
    it: { planted: "Piantato", day: "Giorno", like: "Mi piace", dislike: "Non mi piace", gift: "Dono", comments: "Commenti", full: "Ciclo completo" },
    pt: { planted: "Plantado", day: "Dia", like: "Gosto", dislike: "Não gosto", gift: "Doar", comments: "Comentários", full: "Ciclo completo" },
    pl: { planted: "Posadzono", day: "Dzień", like: "Lubię", dislike: "Nie lubię", gift: "Prezent", comments: "Komentarze", full: "Pełny cykl" },
    zh: { planted: "种植日期", day: "第", like: "喜欢", dislike: "不喜欢", gift: "赠礼", comments: "评论", full: "完整周期" }
  }[language] || {
    planted: "Planted", day: "Day", like: "Like", dislike: "Dislike", gift: "Gift", comments: "Comments", full: "Full cycle"
  });

  const plantingName = (planting, fallbackPlant) =>
    planting?.plant_names?.[language]
    || planting?.plant_names?.en
    || planting?.plant_names?.ru
    || plantName(fallbackPlant);

  function dateOnly(value) {
    return value
      ? new Intl.DateTimeFormat(locale(), { dateStyle: "medium" }).format(new Date(value))
      : "—";
  }

  function growthDay(value) {
    if (!value) return 0;
    return Math.max(1, Math.floor((Date.now() - new Date(value).getTime()) / 86400000) + 1);
  }

  const telegramPlantLink = (action, plantingId) =>
    `https://t.me/KisaMoreBot?start=${encodeURIComponent(action + "_" + plantingId)}`;

  function openVideoDialog(href, title) {
    const dialog = $("#videoDialog");
    const video = $("#videoPlayer");
    $("#videoTitle").textContent = title;
    $("#videoError").classList.add("hidden");
    video.src = href;
    video.load();
    dialog.showModal();
  }

  function closeVideoDialog() {
    const video = $("#videoPlayer");
    video.pause();
    video.removeAttribute("src");
    video.load();
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      credentials: "same-origin",
      cache: "no-store",
      ...options,
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) }
    });
    if (!response.ok) {
      let detail = "";
      try { detail = (await response.json()).detail || ""; } catch (_) {}
      const error = new Error(detail || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : response.json();
  }

  function translateTree(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
  }

  function relativeTime(value) {
    if (!value) return t("noData");
    const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
    const formatter = new Intl.RelativeTimeFormat(locale(), { numeric: "auto" });
    if (Math.abs(seconds) < 60) return formatter.format(seconds, "second");
    const minutes = Math.round(seconds / 60);
    if (Math.abs(minutes) < 60) return formatter.format(minutes, "minute");
    const hours = Math.round(minutes / 60);
    if (Math.abs(hours) < 24) return formatter.format(hours, "hour");
    return formatter.format(Math.round(hours / 24), "day");
  }

  function date(value) {
    return value ? new Intl.DateTimeFormat(locale(), { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
  }

  function applyLanguage() {
    document.documentElement.lang = language;
    $("#languageSelect").value = language;
    translateTree();
    render();
    renderAuthDialog();
    if (account) renderAccount();
  }

  function setConnection(status) {
    const normalized = ["online", "offline", "waiting"].includes(status) ? status : "waiting";
    $("#connectionPill").className = `connection-pill is-${normalized}`;
    $("#connectionText").textContent = t(normalized);
  }

  function statusLabel(status) {
    return t({ available: "available", growing: "growing", ready: "ready", maintenance: "maintenance", occupied: "occupied", disabled: "disabled", reserved: "occupied" }[status] || status);
  }

  function renderSlot(slot, plantsById) {
    const card = document.createElement("article");
    card.className = `slot is-${slot.status}`;

    const top = document.createElement("div");
    top.className = "slot-top";

    const number = document.createElement("span");
    number.className = "slot-number";
    number.textContent = `${t("container")} ${slot.slot_number}`;

    const status = document.createElement("span");
    status.className = "slot-status";
    status.textContent = statusLabel(slot.status);
    top.append(number, status);
    card.append(top);

    if (slot.planting) {
      const plantingPlant = plantsById.get(slot.planting.plant_id);
      const title = document.createElement("strong");
      title.className = "slot-plant-name";
      title.textContent = plantingName(slot.planting, plantingPlant);
      card.append(title);

      const labels = slotUiText();
      const meta = document.createElement("div");
      meta.className = "slot-growing-meta";

      const planted = document.createElement("span");
      planted.textContent = `${labels.planted}: ${dateOnly(slot.planting.planted_at)}`;

      const day = document.createElement("span");
      day.textContent = `${labels.day}: ${growthDay(slot.planting.planted_at)}`;

      meta.append(planted, day);
      card.append(meta);

      const social = document.createElement("div");
      social.className = "slot-social";

      const socialItems = [
        ["like", "❤️", slot.planting.likes || 0, labels.like],
        ["dislike", "👎", slot.planting.dislikes || 0, labels.dislike],
        ["gift", "🎁", slot.planting.gift_kisa || 0, labels.gift],
        ["comment", "💬", slot.planting.comments || 0, labels.comments]
      ];

      for (const [action, icon, count, label] of socialItems) {
        const link = document.createElement("a");
        link.className = "slot-social-button";
        link.href = telegramPlantLink(action, slot.planting.id);
        link.target = "_blank";
        link.rel = "noopener";
        link.title = label;
        link.setAttribute("aria-label", `${label}: ${count}`);

        const iconNode = document.createElement("span");
        iconNode.className = "slot-social-icon";
        iconNode.textContent = icon;

        const countNode = document.createElement("strong");
        countNode.className = "slot-social-count";
        countNode.textContent = String(count);

        link.append(iconNode, countNode);
        social.append(link);
      }
      card.append(social);

      const videos = document.createElement("div");
      videos.className = "slot-timelapses";

      const videoItems = [
        ["24h", "🎬 24h", `/api/v1/public/farms/${encodeURIComponent(farmSlug)}/racks/${slot.rack_id}/slots/${slot.slot_number}/timelapse/24h`],
        ["3d", "🎬 3d", `/api/v1/public/farms/${encodeURIComponent(farmSlug)}/racks/${slot.rack_id}/slots/${slot.slot_number}/timelapse/3d`],
        ["full", `🎞 ${labels.full}`, `/api/v1/public/plantings/${encodeURIComponent(slot.planting.id)}/timelapse/full`]
      ];

      for (const [, label, href] of videoItems) {
        const button = document.createElement("button");
        button.className = "slot-video-button";
        button.type = "button";
        button.textContent = label;
        button.addEventListener("click", () => openVideoDialog(
          href,
          `${plantingName(slot.planting, plantingPlant)} · ${label}`
        ));
        videos.append(button);
      }
      card.append(videos);
    }

    if (slot.status !== "disabled") {
      const button = document.createElement("button");
      button.className = "slot-action";
      button.type = "button";
      button.textContent = slot.available ? t("buy") : t("reserve");
      button.addEventListener("click", () => openAction({
        mode: slot.available ? "purchase" : "reservation",
        resourceType: "slot",
        rackId: slot.rack_id,
        slotNumber: slot.slot_number
      }));
      card.append(button);
    }

    return card;
  }


  function renderPlantCard(plant) {
    const card = document.createElement("a");
    card.className = "plant-card";
    card.href = "#greenhouse";
    card.setAttribute("aria-label", `${plantName(plant)} — ${t("choosePlaceCta")}`);

    const visual = document.createElement("div");
    visual.className = "plant-visual";

    const fallback = document.createElement("span");
    fallback.className = "plant-image-fallback";
    fallback.setAttribute("aria-hidden", "true");
    fallback.textContent = "🌿";
    visual.append(fallback);

    if (plant?.id && (plant.microgreen_image_name || plant.seed_image_name)) {
      const image = document.createElement("img");
      image.src = `/api/v1/public/plants/${encodeURIComponent(plant.id)}/image`;
      image.alt = plantName(plant);
      image.loading = "lazy";
      image.decoding = "async";
      image.addEventListener("load", () => fallback.classList.add("hidden"));
      image.addEventListener("error", () => image.remove());
      visual.append(image);
    }

    const body = document.createElement("div");
    body.className = "plant-card-body";

    const meta = document.createElement("div");
    meta.className = "plant-meta";
    const grow = document.createElement("span");
    grow.textContent = `${t("growTime")}: ${plant.grow_days} ${t("daysShort")}`;
    const price = document.createElement("span");
    price.textContent = `${t("rentalFrom")}: ${plant.rental_price_kisa} KISA`;
    meta.append(grow, price);

    const title = document.createElement("h3");
    title.textContent = plantName(plant);

    const description = document.createElement("p");
    description.textContent = plantDescription(plant);

    const action = document.createElement("span");
    action.className = "plant-action";
    action.textContent = t("choosePlaceCta");
    const arrow = document.createElement("span");
    arrow.className = "plant-action-arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "→";
    action.append(arrow);

    body.append(meta, title, description, action);
    card.append(visual, body);
    return card;
  }

  function renderPlants() {
    const container = $("#plantsGrid");
    if (!container || !marketData) return;
    const plants = Array.isArray(marketData.plants) ? marketData.plants : [];
    if (!plants.length) {
      container.replaceChildren();
      const empty = document.createElement("div");
      empty.className = "loading-card";
      empty.textContent = t("empty");
      container.append(empty);
      return;
    }
    container.replaceChildren(...plants.map(renderPlantCard));

    const prices = plants
      .map((plant) => Number(plant.rental_price_kisa))
      .filter((value) => Number.isFinite(value));
    const minPrice = prices.length ? Math.min(...prices) : null;
    const priceNode = $("#minRentalPrice");
    if (priceNode) priceNode.textContent = minPrice === null ? "—" : String(minPrice);
  }

  function renderRack(rack, plantsById) {
    const card = $("#rackTemplate").content.firstElementChild.cloneNode(true);
    translateTree(card);
    $(".rack-title", card).textContent = `${t("rack")} ${rack.rack_id}`;

    const temperature = $(".rack-temperature", card);
    if (Number.isFinite(rack.soil_temperature)) {
      temperature.textContent = `${temperatureLabel()}: ${rack.soil_temperature.toFixed(1)} °C`;
    } else {
      temperature.classList.add("hidden");
    }

    const photo = $(".rack-photo", card);
    if (rack.photo_url) {
      const image = $("img", photo);
      image.src = `${rack.photo_url}?v=${encodeURIComponent(rack.photo_captured_at || Date.now())}`;
      image.alt = `${t("rack")} ${rack.rack_id}`;
      $("figcaption", photo).textContent = `${t("updated")}: ${date(rack.photo_captured_at)}`;
      photo.classList.remove("hidden");
    }

    const orderedSlots = [...rack.slots].sort((a, b) => Number(a.slot_number) - Number(b.slot_number));
    const allSlotsFree = orderedSlots.length === 6 && orderedSlots.every((slot) => slot.available === true);

    const rackButton = $(".rack-action", card);
    if (allSlotsFree) {
      rackButton.textContent = t("reserveRack");
      rackButton.classList.remove("hidden");
      rackButton.addEventListener("click", () => openAction({
        mode: "purchase",
        resourceType: "rack",
        rackId: rack.rack_id,
        slotNumber: null
      }));
    }

    $(".slots", card).replaceChildren(...orderedSlots.map((slot) => renderSlot(slot, plantsById)));
    return card;
  }

  function render() {
    $("#accountButton").textContent = user ? user.display_name : t("signIn");
    if (!liveData || !marketData) return;
    setConnection(liveData.status);
    $("#farmName").textContent = marketData.farm_name || liveData.farm_name || "KisaMore Farm";
    $("#lastSeen").textContent = liveData.last_seen_at ? `${t("lastSeen")} ${relativeTime(liveData.last_seen_at)}` : t("waitingData");
    const slots = marketData.racks.flatMap((rack) => rack.slots);
    $("#rackCount").textContent = marketData.racks.length;
    $("#slotCount").textContent = slots.length;
    $("#availableCount").textContent = slots.filter((slot) => slot.available).length;
    $("#growingCount").textContent = slots.filter((slot) => slot.planting).length;
    const plantsById = new Map(marketData.plants.map((plant) => [plant.id, plant]));
    renderPlants();
    $("#racksGrid").replaceChildren(...marketData.racks.map((rack) => renderRack(rack, plantsById)));
    $("#racksGrid").setAttribute("aria-busy", "false");
    $("#pageUpdated").textContent = `${t("updated")}: ${new Intl.DateTimeFormat(locale(), { timeStyle: "medium" }).format(new Date())}`;
  }

  async function loadData() {
    $("#refreshButton").disabled = true;
    try {
      [liveData, marketData] = await Promise.all([
        api(`/api/v1/public/farms/${encodeURIComponent(farmSlug)}/live`),
        api(`/api/v1/public/farms/${encodeURIComponent(farmSlug)}/market`)
      ]);
      $("#notice").classList.add("hidden");
      render();
    } catch (error) {
      console.error(error);
      $("#notice").textContent = t("loadError");
      $("#notice").classList.remove("hidden");
      setConnection("offline");
    } finally {
      $("#refreshButton").disabled = false;
    }
  }

  async function loadUser() {
    try {
      user = await api("/api/v1/auth/me");
      language = user.preferred_language || language;
      localStorage.setItem("kisamore-language", language);
      applyLanguage();
    } catch (error) {
      if (error.status !== 401) console.error(error);
      user = null;
      render();
    }
  }

  function renderAuthDialog() {
    const register = authMode === "register";
    $("#authTitle").textContent = t(register ? "registerTitle" : "signInTitle");
    $("#authSubmit").textContent = t(register ? "createAccount" : "signIn");
    $("#authModeButton").textContent = t(register ? "haveAccount" : "needAccount");
    $("#displayNameLabel").classList.toggle("hidden", !register);
    $("#authForm").elements.displayName.required = register;
    $("#authForm").elements.password.autocomplete = register ? "new-password" : "current-password";
  }

  function openAuth() {
    authMode = "login";
    $("#authForm").reset();
    $(".form-error", $("#authForm")).classList.add("hidden");
    renderAuthDialog();
    $("#authDialog").showModal();
  }

  function fillPlants(select, selectedId = "") {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = t("anyPlant");
    const options = [option, ...(marketData?.plants || []).map((plant) => {
      const item = document.createElement("option");
      item.value = plant.id;
      item.textContent = plantName(plant);
      item.selected = plant.id === selectedId;
      return item;
    })];
    select.replaceChildren(...options);
  }

  function openAction(action) {
    if (!user) {
      pendingAction = action;
      openAuth();
      return;
    }
    const form = $("#actionForm");
    form.reset();
    form.elements.resourceType.value = action.resourceType;
    form.elements.rackId.value = action.rackId;
    form.elements.slotNumber.value = action.slotNumber ?? "";
    form.elements.mode.value = action.mode;
    form.elements.offerId.value = action.offerId || "";
    $("#actionTitle").textContent = t(action.mode === "purchase" ? "purchaseTitle" : "reservationTitle");
    $("#actionDescription").textContent = t(action.mode === "purchase" ? "purchaseDescription" : "reservationDescription");
    $("#actionSubmit").textContent = t(action.mode === "purchase" ? "confirmPurchase" : "confirmReservation");
    fillPlants(form.elements.plantId, action.plantId || "");
    $(".form-error", form).classList.add("hidden");
    $("#actionDialog").showModal();
  }

  function accountItem(primary, secondary, actionLabel, actionHandler) {
    const item = document.createElement("div");
    item.className = "account-item";
    const text = document.createElement("div");
    const strong = document.createElement("strong");
    strong.textContent = primary;
    const small = document.createElement("span");
    small.textContent = secondary;
    text.append(strong, document.createElement("br"), small);
    item.append(text);
    if (actionLabel) {
      const button = document.createElement("button");
      button.className = "secondary-button";
      button.textContent = actionLabel;
      button.addEventListener("click", actionHandler);
      item.append(button);
    }
    return item;
  }

  function accountGroup(titleKey, items) {
    const group = document.createElement("section");
    group.className = "account-group";
    const title = document.createElement("h3");
    title.textContent = t(titleKey);
    const list = document.createElement("div");
    list.className = "account-list";
    list.replaceChildren(...(items.length ? items : [accountItem(t("empty"), "", null, null)]));
    group.append(title, list);
    return group;
  }

  function targetLabel(item) {
    return item.resource_type === "rack"
      ? `${t("rack")} ${item.rack_id}`
      : `${t("rack")} ${item.rack_id} · ${t("container")} ${item.slot_number}`;
  }

  function renderAccount() {
    if (!account) return;
    $("#accountName").textContent = account.user.display_name;
    const activeAllocations = account.allocations.filter((item) => item.status === "active").map((item) =>
      accountItem(targetLabel(item), `${t("status")}: ${item.status}`, t("release"), () => releaseAllocation(item.id))
    );
    const reservations = account.reservations.filter((item) => ["waiting", "offered"].includes(item.status)).map((item) =>
      accountItem(targetLabel(item), `${t("status")}: ${item.status}`, null, null)
    );
    const offers = account.offers.filter((item) => item.status === "pending").map((item) =>
      accountItem(targetLabel(item), `${t("offerUntil")}: ${date(item.expires_at)}`, t("acceptOffer"), () => {
        $("#accountDialog").close();
        openAction({ mode: "purchase", resourceType: item.resource_type, rackId: item.rack_id, slotNumber: item.slot_number, plantId: item.plant_id, offerId: item.id });
      })
    );
    const notifications = account.notifications.slice(0, 20).map((item) =>
      accountItem(item.kind.replaceAll("_", " "), date(item.created_at), null, null)
    );
    $("#accountContent").replaceChildren(
      accountGroup("offers", offers),
      accountGroup("allocations", activeAllocations),
      accountGroup("reservations", reservations),
      accountGroup("notifications", notifications)
    );
  }

  async function openAccount() {
    if (!user) { openAuth(); return; }
    try {
      account = await api("/api/v1/account");
      renderAccount();
      $("#accountDialog").showModal();
    } catch (error) { console.error(error); }
  }

  async function releaseAllocation(id) {
    try {
      await api(`/api/v1/shop/allocations/${id}/release`, { method: "POST" });
      account = await api("/api/v1/account");
      renderAccount();
      await loadData();
    } catch (error) { console.error(error); }
  }

  $("#languageSelect").addEventListener("change", async (event) => {
    language = event.target.value;
    localStorage.setItem("kisamore-language", language);
    applyLanguage();
    if (user) {
      try { user = await api("/api/v1/auth/me/language", { method: "PATCH", body: JSON.stringify({ language }) }); } catch (error) { console.error(error); }
    }
  });
  $("#refreshButton").addEventListener("click", loadData);
  $("#accountButton").addEventListener("click", openAccount);
  $("#accountCtaButton")?.addEventListener("click", openAccount);
  $("#authModeButton").addEventListener("click", () => { authMode = authMode === "login" ? "register" : "login"; renderAuthDialog(); });
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $("#videoDialog")?.addEventListener("close", closeVideoDialog);
  $("#videoPlayer")?.addEventListener("error", () => {
    $("#videoError").classList.remove("hidden");
  });

  $("#authForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = authMode === "register"
      ? { email: form.elements.email.value, display_name: form.elements.displayName.value, password: form.elements.password.value, language }
      : { email: form.elements.email.value, password: form.elements.password.value };
    try {
      user = await api(`/api/v1/auth/${authMode === "register" ? "register" : "login"}`, { method: "POST", body: JSON.stringify(payload) });
      $("#authDialog").close();
      applyLanguage();
      if (pendingAction) {
        const action = pendingAction;
        pendingAction = null;
        openAction(action);
      } else {
        openAccount();
      }
    } catch (error) {
      const node = $(".form-error", form);
      node.textContent = error.message || t("authError");
      node.classList.remove("hidden");
    }
  });

  $("#actionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const payload = {
      device_id: marketData.device_id,
      resource_type: form.elements.resourceType.value,
      rack_id: Number(form.elements.rackId.value),
      slot_number: form.elements.slotNumber.value ? Number(form.elements.slotNumber.value) : null,
      plant_id: form.elements.plantId.value || null
    };
    if (form.elements.offerId.value) payload.offer_id = form.elements.offerId.value;
    const isPurchase = form.elements.mode.value === "purchase";
    try {
      await api(isPurchase ? "/api/v1/shop/purchases" : "/api/v1/shop/reservations", { method: "POST", body: JSON.stringify(payload) });
      $("#actionDialog").close();
      $("#notice").textContent = t(isPurchase ? "purchaseCreated" : "reservationCreated");
      $("#notice").classList.remove("hidden");
      await Promise.all([loadData(), openAccount()]);
    } catch (error) {
      const node = $(".form-error", form);
      node.textContent = error.message || t("actionError");
      node.classList.remove("hidden");
    }
  });

  $("#logoutButton").addEventListener("click", async () => {
    await api("/api/v1/auth/logout", { method: "POST" });
    user = null;
    account = null;
    $("#accountDialog").close();
    render();
  });

  applyLanguage();
  Promise.all([loadUser(), loadData()]);
  window.setInterval(loadData, 30_000);
})();
