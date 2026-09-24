'use strict';
/* Public app installation and connectivity only. No business records or secrets
   are written to localStorage, IndexedDB or CacheStorage by this component. */
(() => {
  let promptEvent = null, registration = null, state = 'checking', lastOK = null, checking = false;
  const installed = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  const banner = document.querySelector('#pwa-network-banner');
  const dialog = document.createElement('dialog');
  dialog.id = 'pwa-dialog'; dialog.className = 'pwa-dialog'; dialog.setAttribute('aria-labelledby', 'pwa-dialog-title');
  document.body.append(dialog);
  const closeDialog = () => dialog.close();

  function drawStatus() {
    const label = state === 'online' ? 'Servidor ativo' : state === 'offline' ? 'Sem conexão' : 'Conectando';
    document.querySelectorAll('[data-connection-state]').forEach(node => {
      if (node.textContent !== label) node.textContent = label;
      if (node.dataset.state !== state) node.dataset.state = state;
      const title = lastOK ? `Última resposta: ${lastOK.toLocaleTimeString('pt-BR')}. Campos ainda em edição não estão salvos.` : 'Conferindo a conexão com o servidor.';
      if (node.title !== title) node.title = title;
    });
    document.querySelectorAll('.install-nav span').forEach(node => {
      const text = installed() ? 'Sobre o aplicativo' : 'Instalar aplicativo';
      if (node.textContent !== text) node.textContent = text;
    });
    if (banner) {
      if (state === 'offline') {
        if (banner.hidden) {
          banner.innerHTML = '<span><strong>Sem conexão com o servidor.</strong> Dados exibidos podem estar desatualizados. Não feche campos ainda não salvos.</span><button type="button" data-pwa-action="reconnect">Reconectar</button>';
          banner.hidden = false;
        }
      } else if (!banner.hidden) banner.hidden = true;
    }
  }

  function status(ok) {
    const wasOffline = state === 'offline';
    state = ok ? 'online' : 'offline';
    if (ok) lastOK = new Date();
    drawStatus();
    if (ok && wasOffline) window.dispatchEvent(new Event('nexo:reconnected'));
  }

  async function checkServer() {
    if (checking) return;
    checking = true;
    const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('/api/health', {cache: 'no-store', credentials: 'same-origin', signal: controller.signal});
      const data = response.ok ? await response.json() : null;
      status(response.ok && data?.status === 'ok');
    } catch (_) { status(false); }
    finally { clearTimeout(timeout); checking = false; }
  }

  function showInstall() {
    const isInstalled = installed();
    dialog.innerHTML = `
      <button class="pwa-close" data-pwa-action="close" aria-label="Fechar instruções">×</button>
      <div class="eyebrow">NEXO CRM · MONO</div>
      <h2 id="pwa-dialog-title">${isInstalled ? 'Seu CRM, em formato de app.' : 'Um toque para entrar.'}</h2>
      <p>Adicione o Nexo à tela inicial do celular ou à área de aplicativos do computador. O mesmo endereço e a mesma conta continuam funcionando no navegador.</p>
      ${promptEvent && !isInstalled ? '<button class="btn primary" data-pwa-action="native-install">Instalar neste dispositivo</button>' : ''}
      ${isInstalled ? '<p><strong>O Nexo já está aberto no modo aplicativo.</strong></p>' : `
      <div class="pwa-help-step"><b>Android · Chrome</b><p>No menu do navegador, procure “Instalar aplicativo” ou “Adicionar à tela inicial”. A opção depende do navegador.</p></div>
      <div class="pwa-help-step"><b>iPhone / iPad · Safari</b><p>Toque em Compartilhar e depois em “Adicionar à Tela de Início”. Abra pelo ícone criado.</p></div>
      <div class="pwa-help-step"><b>Computador · Chrome / Edge</b><p>Use o ícone de instalação na barra de endereço ou a opção de instalar este site como aplicativo no menu.</p></div>`}
      <hr><p class="pwa-note"><strong>Instalar não hospeda o servidor.</strong> O acesso da equipe depende da publicação em uma hospedagem permanente com HTTPS. Login, consultas e alterações precisam de conexão. Não há gravação offline nem sincronização em segundo plano.</p>
      ${registration?.waiting ? '<p><strong>Uma nova versão está disponível.</strong> Salve seu trabalho antes de atualizar.</p><button class="btn primary" data-pwa-action="update">Atualizar aplicativo</button>' : '<p class="pwa-note">Atualizações são consultadas ao abrir o aplicativo. Uma edição em andamento não é recarregada automaticamente.</p>'}
      <div class="pwa-dialog-actions"><button class="btn" data-pwa-action="close">Entendi</button></div>`;
    if (!dialog.open) dialog.showModal();
  }

  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-pwa-action]');
    if (!button) return;
    const action = button.dataset.pwaAction;
    if (action === 'close') closeDialog();
    else if (action === 'install') showInstall();
    else if (action === 'reconnect') checkServer();
    else if (action === 'native-install' && promptEvent) {
      const current = promptEvent; promptEvent = null;
      try { await current.prompt(); await current.userChoice; }
      catch (_) { /* The platform can decline a prompt; menu instructions remain. */ }
      showInstall();
    } else if (action === 'update' && registration?.waiting) {
      const guard = new Event('nexo:before-reload', {cancelable: true});
      if (!window.dispatchEvent(guard)) { closeDialog(); return; }
      if (!confirm('Os dados já salvos ficam no servidor. Confirmar a atualização e recarregar o aplicativo?')) return;
      navigator.serviceWorker.addEventListener('controllerchange', () => location.reload(), {once: true});
      registration.waiting.postMessage({type: 'ACTIVATE_UPDATE'});
    }
  });
  dialog.addEventListener('click', event => { if (event.target === dialog) closeDialog(); });
  window.addEventListener('beforeinstallprompt', event => { event.preventDefault(); promptEvent = event; });
  window.addEventListener('appinstalled', () => { promptEvent = null; closeDialog(); drawStatus(); });
  window.addEventListener('nexo:network', event => status(event.detail?.ok === true));
  window.addEventListener('online', checkServer);
  window.addEventListener('offline', () => status(false));
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { checkServer(); registration?.update().catch(() => {}); } });
  let scheduled = false;
  new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => { scheduled = false; drawStatus(); });
  }).observe(document.querySelector('#app'), {childList: true, subtree: true});

  if ('serviceWorker' in navigator && window.isSecureContext) {
    navigator.serviceWorker.register('/sw.js', {scope: '/', updateViaCache: 'none'})
      .then(value => { registration = value; return value.update(); })
      .catch(() => { /* Installation is optional; the online CRM remains usable. */ });
  }
  setInterval(() => { if (!document.hidden) checkServer(); }, 30000);
  checkServer();
})();
