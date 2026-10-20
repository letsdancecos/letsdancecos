/* OneSignal public app ID only. Sending credentials must never be stored here. */
(() => {
  let sdk = null;
  let state = 'loading';
  let busy = false;
  let failure = '';
  function paint() {
    const button = document.getElementById('studio-push-toggle');
    const status = document.getElementById('studio-push-status');
    if (!button || !status) return;
    const subscribed = !!(sdk && sdk.User.PushSubscription.optedIn);
    const blocked = 'Notification' in window && Notification.permission === 'denied';
    button.textContent = subscribed ? 'Turn Off Notifications' : 'Enable Notifications';
    button.disabled = busy || state !== 'ready' || (blocked && !subscribed);
    status.textContent = failure || (state === 'unsupported'
      ? 'Notifications are unavailable here. On iPhone, add the app to your home screen and open it there.'
      : state === 'error' ? 'Notifications could not connect. Check your connection and reopen the app.'
      : state === 'loading' ? 'Connecting notification settings…'
      : blocked && !subscribed ? 'Notifications are blocked. Allow them in your browser or phone settings, then reopen the app.'
      : subscribed ? 'Notifications are enabled on this device.'
      : 'Notifications are off on this device.');
  }
  window.renderStudioPush = paint;
  document.addEventListener('click', async event => {
    if (!event.target.closest('#studio-push-toggle') || !sdk || busy || state !== 'ready') return;
    busy = true;
    failure = '';
    paint();
    try {
      if (sdk.User.PushSubscription.optedIn) await sdk.User.PushSubscription.optOut();
      else await sdk.User.PushSubscription.optIn();
    } catch (_) {
      failure = 'Could not change notifications. Please try again.';
    } finally { busy = false; paint(); }
  });
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
    state = 'unsupported';
    paint();
    return;
  }
  window.OneSignalDeferred = window.OneSignalDeferred || [];
  const timeout = setTimeout(() => { if (state === 'loading') { state = 'error'; paint(); } }, 15000);
  window.OneSignalDeferred.push(async function(OneSignal) {
    try {
      if (!OneSignal.Notifications.isPushSupported()) { state = 'unsupported'; return; }
      await OneSignal.init({
        appId: '4d59ba22-2de8-4714-9e23-63b84de1a58c',
        serviceWorkerPath: 'letsdancecos/app/push/OneSignalSDKWorker.js',
        serviceWorkerParam: { scope: '/letsdancecos/app/push/' },
        notifyButton: { enable: false },
        promptOptions: { slidedown: { prompts: [{ type: 'push', autoPrompt: false }] } },
        welcomeNotification: { disable: true }
      });
      sdk = OneSignal;
      state = 'ready';
      sdk.User.PushSubscription.addEventListener('change', paint);
      sdk.Notifications.addEventListener('permissionChange', paint);
    } catch (_) { state = 'error'; }
    finally { clearTimeout(timeout); paint(); }
  });
  const script = document.createElement('script');
  script.src = 'https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js';
  script.defer = true;
  script.onerror = () => { clearTimeout(timeout); state = 'error'; paint(); };
  document.head.append(script);
})();
