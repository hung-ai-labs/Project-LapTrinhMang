import { useEffect, useState } from "react";

export function getTimeTheme(date = new Date()): "light" | "dark" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", hourCycle: "h23",
  }).format(date));
  return hour >= 6 && hour < 18 ? "light" : "dark";
}

export function useTimeTheme() {
  const [theme, setTheme] = useState(getTimeTheme);
  useEffect(() => {
    const update = () => setTheme(getTimeTheme());
    const timer = window.setInterval(update, 1000);
    window.addEventListener("focus", update);
    document.addEventListener("visibilitychange", update);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", update);
      document.removeEventListener("visibilitychange", update);
    };
  }, []);
  return theme;
}
