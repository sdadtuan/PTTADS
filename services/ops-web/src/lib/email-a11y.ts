/** Focus trap for email modals/dialogs (Wave 3 — pattern SEO a11y). */

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function trapFocus(container: HTMLElement): () => void {
  const focusables = () =>
    Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
      (el) => !el.hasAttribute('disabled') && el.offsetParent !== null,
    );

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key !== 'Tab') return;
    const items = focusables();
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  container.addEventListener('keydown', onKeyDown);
  const items = focusables();
  if (items[0]) items[0].focus();

  return () => container.removeEventListener('keydown', onKeyDown);
}
