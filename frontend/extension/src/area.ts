/**
 * Area selection overlay, injected into the page only when the user asks for it.
 *
 * Self-contained on purpose: content scripts cannot import modules. The overlay removes itself
 * before reporting the rectangle, so it is not part of the screenshot.
 */
(() => {
  const flag = '__clearContextArea';
  const scope = window as unknown as Record<string, boolean>;
  if (scope[flag]) return;
  scope[flag] = true;

  const overlay = document.createElement('div');
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-label', 'Select an area to check with Clear Context');
  Object.assign(overlay.style, {
    position: 'fixed',
    inset: '0',
    zIndex: '2147483647',
    cursor: 'crosshair',
    background: 'rgba(37, 44, 40, 0.35)',
  });
  const box = document.createElement('div');
  Object.assign(box.style, {
    position: 'fixed',
    border: '2px solid #a84315',
    background: 'rgba(255, 254, 250, 0.12)',
    boxShadow: '0 0 0 9999px rgba(37, 44, 40, 0.35)',
    display: 'none',
  });
  const hint = document.createElement('div');
  hint.textContent = 'Drag to select what to check · Esc to cancel';
  Object.assign(hint.style, {
    position: 'fixed',
    top: '16px',
    left: '50%',
    transform: 'translateX(-50%)',
    padding: '8px 14px',
    borderRadius: '8px',
    background: '#fffefa',
    color: '#252c28',
    font: '600 14px system-ui, sans-serif',
    boxShadow: '0 2px 10px rgba(0,0,0,0.2)',
  });
  overlay.append(box, hint);
  document.documentElement.append(overlay);

  let start: { x: number; y: number } | null = null;
  let current = { x: 0, y: 0, width: 0, height: 0 };

  function finish() {
    overlay.remove();
    document.removeEventListener('keydown', onKey, true);
    scope[flag] = false;
  }

  function onKey(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault();
      finish();
    }
  }

  overlay.addEventListener('mousedown', (event) => {
    event.preventDefault();
    start = { x: event.clientX, y: event.clientY };
    box.style.display = 'block';
    overlay.style.background = 'transparent';
  });
  overlay.addEventListener('mousemove', (event) => {
    if (!start) return;
    current = {
      x: Math.min(start.x, event.clientX),
      y: Math.min(start.y, event.clientY),
      width: Math.abs(event.clientX - start.x),
      height: Math.abs(event.clientY - start.y),
    };
    Object.assign(box.style, {
      left: `${current.x}px`,
      top: `${current.y}px`,
      width: `${current.width}px`,
      height: `${current.height}px`,
    });
  });
  overlay.addEventListener('mouseup', () => {
    if (!start) return;
    start = null;
    if (current.width < 12 || current.height < 12) {
      box.style.display = 'none';
      overlay.style.background = 'rgba(37, 44, 40, 0.35)';
      return;
    }
    const rect = current;
    finish();
    // Wait two frames so the page repaints without the overlay before the screenshot.
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        void chrome.runtime.sendMessage({
          type: 'clear-context-area',
          rect,
          viewportWidth: window.innerWidth,
        });
      }),
    );
  });
  document.addEventListener('keydown', onKey, true);
})();
