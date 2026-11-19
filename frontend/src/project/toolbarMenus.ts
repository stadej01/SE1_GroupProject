// Dropdown panels in the graph toolbar: only one stays open at a time.

const SCREEN_MARGIN = 8;

// How far left a panel must move to stay on screen.
export function panelShift(left: number, width: number, screenWidth: number, margin = SCREEN_MARGIN): number {
  const overflow = left + width - (screenWidth - margin);
  return overflow > 0 ? Math.min(overflow, Math.max(0, left - margin)) : 0;
}

export function mountToolbarMenus(toolbar: HTMLElement): void {
  const menus = [...toolbar.querySelectorAll<HTMLDetailsElement>("details.toolbar-menu")];

  function keepOnScreen(menu: HTMLDetailsElement) {
    const panel = menu.querySelector<HTMLElement>(".toolbar-panel")!;
    panel.style.removeProperty("left");
    const box = panel.getBoundingClientRect();
    panel.style.left = `${-panelShift(box.left, box.width, document.documentElement.clientWidth)}px`;
  }

  for (const menu of menus) {
    menu.addEventListener("toggle", () => {
      if (!menu.open) return;
      for (const other of menus) if (other !== menu) other.open = false;
      keepOnScreen(menu);
    });
  }
  // Capture runs first because the graph canvas can stop pointer events.
  document.addEventListener("pointerdown", event => {
    for (const menu of menus) if (menu.open && !menu.contains(event.target as Node)) menu.open = false;
  }, true);
  document.addEventListener("keydown", event => {
    if (event.key !== "Escape") return;
    const menu = menus.find(item => item.open);
    if (!menu) return;
    menu.open = false;
    menu.querySelector("summary")!.focus();
  });
  window.addEventListener("resize", () => {
    const menu = menus.find(item => item.open);
    if (menu) keepOnScreen(menu);
  });
}
