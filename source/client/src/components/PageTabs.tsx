import type { MouseEvent } from "react";

export const pageTabs = [
  { href: "/", label: "Tổng quan" },
  { href: "/history", label: "Lịch sử" },
  { href: "/alerts", label: "Cảnh báo" },
  { href: "/forecast", label: "Dự báo" },
];

export default function PageTabs({ onNavigate }: { onNavigate: (path: string) => void }) {
  const path = window.location.pathname;
  const follow = (event: MouseEvent<HTMLAnchorElement>, href: string) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onNavigate(href);
  };
  return <nav className="page-tabs" aria-label="Điều hướng thời tiết">
    {pageTabs.map(tab => <a key={tab.href} href={tab.href}
      aria-current={path === tab.href ? "page" : undefined}
      onClick={event => follow(event, tab.href)}>{tab.label}</a>)}
  </nav>;
}
