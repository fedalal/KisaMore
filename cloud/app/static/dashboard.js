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
  const t = (key) => translations[language]?.[key] || translations.en[key] || key;
  const locale = () => ({ en: "en-US", ru: "ru-RU", de: "de-DE", fr: "fr-FR", es: "es-ES", it: "it-IT", pt: "pt-PT", pl: "pl-PL", zh: "zh-CN" }[language]);
  const plantName = (plant) => plant?.names?.[language] || plant?.names?.en || plant?.names?.ru || plant?.code || "—";

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
    const number = document.createElement("span");
    number.className = "slot-number";
    number.textContent = `${t("container")} ${slot.slot_number}`;
    const title = document.createElement("strong");
    const plantingPlant = plantsById.get(slot.planting?.plant_id);
    title.textContent = slot.planting ? plantName(plantingPlant) : statusLabel(slot.status);
    const detail = document.createElement("small");
    detail.textContent = slot.planting?.expected_harvest_at
      ? `${t("expected")}: ${new Intl.DateTimeFormat(locale(), { dateStyle: "medium" }).format(new Date(slot.planting.expected_harvest_at))}`
      : statusLabel(slot.status);
    card.append(number, title, detail);
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

  function renderRack(rack, plantsById) {
    const card = $("#rackTemplate").content.firstElementChild.cloneNode(true);
    translateTree(card);
    $(".rack-title", card).textContent = `${t("rack")} ${rack.rack_id}`;
    $(".light-value", card).textContent = rack.light_on ? t("lightOn") : t("lightOff");
    $(".water-value", card).textContent = rack.water_on ? t("waterOn") : t("waterOff");
    $(".temperature-value", card).textContent = Number.isFinite(rack.soil_temperature) ? `${rack.soil_temperature.toFixed(1)} °C` : "—";
    $(".moisture-value", card).textContent = Number.isFinite(rack.soil_moisture) ? `${rack.soil_moisture.toFixed(1)} %` : "—";
    const photo = $(".rack-photo", card);
    if (rack.photo_url) {
      const image = $("img", photo);
      image.src = `${rack.photo_url}?v=${encodeURIComponent(rack.photo_captured_at || Date.now())}`;
      image.alt = `${t("rack")} ${rack.rack_id}`;
      $("figcaption", photo).textContent = `${t("updated")}: ${date(rack.photo_captured_at)}`;
      photo.classList.remove("hidden");
    }
    const rackButton = $(".rack-action", card);
    rackButton.textContent = rack.whole_rack_available ? t("buyRack") : t("reserveRack");
    rackButton.addEventListener("click", () => openAction({
      mode: rack.whole_rack_available ? "purchase" : "reservation",
      resourceType: "rack",
      rackId: rack.rack_id,
      slotNumber: null
    }));
    $(".slots", card).replaceChildren(...rack.slots.map((slot) => renderSlot(slot, plantsById)));
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
  $("#authModeButton").addEventListener("click", () => { authMode = authMode === "login" ? "register" : "login"; renderAuthDialog(); });
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));

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
