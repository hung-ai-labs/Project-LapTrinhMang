import { useEffect, useState } from "react";

const hourFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Ho_Chi_Minh",
  hour: "2-digit",
  hourCycle: "h23",
});

export function getDayPeriod(date = new Date()) {
  const hour = Number(hourFormatter.format(date));
  if (hour >= 5 && hour < 7) return "dawn";
  if (hour >= 7 && hour < 17) return "day";
  if (hour >= 17 && hour < 19) return "dusk";
  return "night";
}

export function useDayPeriod() {
  const [period, setPeriod] = useState(() => getDayPeriod());

  useEffect(() => {
    const update = () => setPeriod(getDayPeriod());
    // Re-read the clock on resume, including after a suspended mobile tab.
    const timer = window.setInterval(update, 15_000);
    document.addEventListener("visibilitychange", update);
    window.addEventListener("focus", update);
    update();
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", update);
      window.removeEventListener("focus", update);
    };
  }, []);

  return period;
}
