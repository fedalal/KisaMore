/* Shared account menu for the greenhouse, pricing and wallet pages. */
(() => {
  "use strict";
  const root = document.querySelector("[data-kisa-account]");
  if (!root) return;

  const labels = {
    en: {signIn:"Sign in", signedInAs:"Signed in as", profile:"My account", wallet:"Kisa wallet", signOut:"Sign out", unavailable:"Account unavailable", retry:"Could not sign out. Try again."},
    ru: {signIn:"Войти", signedInAs:"Вы вошли как", profile:"Личный кабинет", wallet:"Кошелёк Kisa", signOut:"Выйти", unavailable:"Аккаунт недоступен", retry:"Не удалось выйти. Попробуйте ещё раз."},
    de: {signIn:"Anmelden", signedInAs:"Angemeldet als", profile:"Mein Konto", wallet:"Kisa-Guthaben", signOut:"Abmelden", unavailable:"Konto nicht verfügbar", retry:"Abmelden fehlgeschlagen."},
    fr: {signIn:"Connexion", signedInAs:"Connecté en tant que", profile:"Mon compte", wallet:"Portefeuille Kisa", signOut:"Déconnexion", unavailable:"Compte indisponible", retry:"Déconnexion impossible."},
    es: {signIn:"Entrar", signedInAs:"Sesión iniciada como", profile:"Mi cuenta", wallet:"Monedero Kisa", signOut:"Salir", unavailable:"Cuenta no disponible", retry:"No se pudo cerrar la sesión."},
    it: {signIn:"Accedi", signedInAs:"Accesso come", profile:"Il mio account", wallet:"Portafoglio Kisa", signOut:"Esci", unavailable:"Account non disponibile", retry:"Impossibile uscire."},
    pt: {signIn:"Entrar", signedInAs:"Sessão iniciada como", profile:"Minha conta", wallet:"Carteira Kisa", signOut:"Sair", unavailable:"Conta indisponível", retry:"Não foi possível sair."},
    pl: {signIn:"Zaloguj", signedInAs:"Zalogowano jako", profile:"Moje konto", wallet:"Portfel Kisa", signOut:"Wyloguj", unavailable:"Konto niedostępne", retry:"Nie udało się wylogować."},
    zh: {signIn:"登录", signedInAs:"已登录", profile:"我的账户", wallet:"Kisa 钱包", signOut:"退出登录", unavailable:"账户不可用", retry:"退出失败，请重试。"}
  };
  const $ = selector => root.querySelector(selector);
  const button = $("[data-account-button]");
  const menu = $("[data-account-menu]");
  const avatar = $("[data-account-avatar]");
  const nameLabel = $("[data-account-label]");
  const chevron = $("[data-account-chevron]");
  const caption = $("[data-account-caption]");
  const fullName = $("[data-account-name]");
  const email = $("[data-account-email]");
  const profile = $("[data-account-profile]");
  const wallet = $("[data-account-wallet]");
  const logout = $("[data-account-logout]");
  const error = $("[data-account-error]");
  let user = null;
  let ready = false;
  let failed = false;

  function text() {
    return labels[(document.documentElement.lang || "en").toLowerCase().split("-")[0]] || labels.en;
  }
  function close() {
    menu.hidden = true;
    button.setAttribute("aria-expanded", "false");
  }
  function render() {
    const t = text();
    const name = user ? String(user.display_name || user.email || t.profile).trim() : "";
    nameLabel.textContent = user ? name : (ready ? t.signIn : (failed ? t.unavailable : "…"));
    avatar.textContent = name ? Array.from(name)[0].toLocaleUpperCase() : "";
    avatar.hidden = !user;
    chevron.hidden = !user;
    caption.textContent = t.signedInAs;
    fullName.textContent = name;
    email.textContent = user?.email || "";
    profile.textContent = t.profile;
    wallet.textContent = t.wallet;
    logout.textContent = t.signOut;
    button.title = user ? [name, user.email].filter(Boolean).join(" · ") : (ready ? t.signIn : t.unavailable);
    button.setAttribute("aria-label", button.title);
    if (!user) close();
  }
  function setUser(value) {
    user = value || null;
    ready = true;
    failed = false;
    error.hidden = true;
    render();
  }
  async function refresh() {
    try {
      const response = await fetch("/api/v1/auth/me", {credentials:"same-origin", cache:"no-store"});
      if (!response.ok && response.status !== 401) throw new Error("Account unavailable");
      const nextUser = response.status === 401 ? null : await response.json();
      // Refresh other page state (such as the wallet balance) if another tab
      // signed in, signed out, or switched accounts while this page was hidden.
      if (ready && (user?.id || null) !== (nextUser?.id || null)) {
        location.reload();
        return;
      }
      setUser(nextUser);
    } catch (_) {
      ready = false;
      failed = true;
      user = null;
      render();
      close();
    }
  }
  button.addEventListener("click", () => {
    if (!ready) { refresh(); return; }
    if (!user) {
      if (root.dataset.inlineAuth === "true") {
        document.dispatchEvent(new CustomEvent("kisamore:account-signin"));
      } else {
        const next = location.pathname;
        location.assign("/?account=signin&next=" + encodeURIComponent(next));
      }
      return;
    }
    menu.hidden = !menu.hidden;
    button.setAttribute("aria-expanded", String(!menu.hidden));
  });
  profile.addEventListener("click", event => {
    if (root.dataset.inlineAuth === "true") {
      event.preventDefault();
      close();
      document.dispatchEvent(new CustomEvent("kisamore:account-profile"));
    }
  });
  logout.addEventListener("click", async () => {
    logout.disabled = true;
    error.hidden = true;
    try {
      const response = await fetch("/api/v1/auth/logout", {method:"POST", credentials:"same-origin"});
      if (!response.ok) throw new Error("Sign-out failed");
      setUser(null);
      document.dispatchEvent(new CustomEvent("kisamore:account-signed-out"));
      if (root.dataset.inlineAuth !== "true") location.reload();
    } catch (_) {
      error.textContent = text().retry;
      error.hidden = false;
    } finally {
      logout.disabled = false;
    }
  });
  document.addEventListener("click", event => { if (!root.contains(event.target)) close(); });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && !menu.hidden) { close(); button.focus(); }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && root.dataset.inlineAuth !== "true") refresh();
  });
  new MutationObserver(render).observe(document.documentElement, {attributes:true, attributeFilter:["lang"]});
  window.KisaMoreAccountHeader = {setUser, refresh};
  render();
  if (root.dataset.inlineAuth !== "true") refresh();
})();
