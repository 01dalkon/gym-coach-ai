/**
 * GymCoach AI — widget embebible.
 * Uso en cualquier app/web:
 *   <script src="https://TU-DOMINIO/widget.js" data-api="https://TU-DOMINIO" defer></script>
 * Crea un botón flotante que abre el chat en un iframe.
 */
(function () {
  var script = document.currentScript;
  var base = (script && script.getAttribute('data-api')) || script.src.replace(/\/widget\.js.*$/, '');

  var btn = document.createElement('button');
  btn.innerHTML = '🏋️';
  btn.setAttribute('aria-label', 'Abrir GymCoach AI');
  btn.style.cssText = 'position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;' +
    'border:none;background:#ff4400;color:#fff;font-size:26px;cursor:pointer;z-index:99998;' +
    'box-shadow:0 4px 14px rgba(0,0,0,.35);transition:transform .15s;';
  btn.onmouseenter = function () { btn.style.transform = 'scale(1.08)'; };
  btn.onmouseleave = function () { btn.style.transform = 'scale(1)'; };

  var frame = document.createElement('iframe');
  frame.src = base + '/chat.html';
  frame.title = 'GymCoach AI';
  frame.allow = 'clipboard-write';
  frame.style.cssText = 'position:fixed;bottom:88px;right:20px;width:min(400px,calc(100vw - 32px));' +
    'height:min(620px,calc(100vh - 120px));border:none;border-radius:16px;z-index:99999;' +
    'box-shadow:0 10px 40px rgba(0,0,0,.45);display:none;background:#0f1115;';

  btn.onclick = function () {
    var open = frame.style.display !== 'none';
    frame.style.display = open ? 'none' : 'block';
    btn.innerHTML = open ? '🏋️' : '✕';
  };

  document.body.appendChild(btn);
  document.body.appendChild(frame);
})();
