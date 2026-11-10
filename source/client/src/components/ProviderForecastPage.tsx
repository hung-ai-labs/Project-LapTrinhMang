import { useEffect, useMemo, useState } from "react";
import { api, type City } from "../lib/api";
import { useDayPeriod } from "../hooks/useDayPeriod";
import "./provider-forecast.css";
import PageTabs from "./PageTabs";

interface Hour {
  time: string; temperature: number | null; humidity: number | null;
  wind_speed: number | null; precipitation: number | null; rain_probability: number | null;
}
interface Day {
  date: string; temperature_min: number | null; temperature_max: number | null;
  precipitation_sum: number | null; rain_probability_max: number | null; wind_speed_max: number | null;
}
interface Forecast {
  city: string; retrieved_at: string; hourly: Hour[]; daily: Day[];
}
const cities: { id: City; name: string }[] = [
  { id: "hanoi", name: "Hà Nội" }, { id: "danang", name: "Đà Nẵng" }, { id: "hcm", name: "TP. Hồ Chí Minh" },
];
const time = (value: string) => new Date(value).toLocaleString("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
});
const value = (n: number | null, unit: string) => n === null ? "—" : `${n.toLocaleString("vi-VN", { maximumFractionDigits: 1 })}${unit}`;

export default function ProviderForecastPage({ onNavigate, city, onCityChange }: {
  onNavigate: (path: string) => void; city: City; onCityChange: (city: City) => void;
}) {
  const [days, setDays] = useState(7);
  const [selected, setSelected] = useState("");
  const [data, setData] = useState<Forecast | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [now, setNow] = useState(Date.now());
  const period = useDayPeriod();
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(""); setData(null); setSelected("");
    const load = async () => {
      try {
        const result = await api<Forecast>(`/weather/${city}/provider-forecast?days=${days}`, controller.signal);
        if (!controller.signal.aborted) {
          setData(result); setError(""); setNow(Date.now());
        }
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Không lấy được dự báo.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    };
    void load();
    const timer = setInterval(() => { setNow(Date.now()); void load(); }, 900000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [city, days, retry]);
  const hourly = useMemo(() => (data?.hourly ?? []).filter(h => {
    const localDate = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(h.time));
    return selected ? localDate === selected : Date.parse(h.time) >= now;
  }).slice(0, 24), [data, selected, now]);
  const stale = data && now - Date.parse(data.retrieved_at) > 1800000;
  return <div className={`weather-app period-${period} scene-clear`}>
    <div className="weather-scene" aria-hidden="true"><div className="cloud cloud-one" /><div className="sky-light" /></div>
    <main className="provider-page">
      <header className="page-header"><a className="brand" href="/" onClick={e => { e.preventDefault(); onNavigate("/"); }}>☁ Weather Stream</a>
        <PageTabs onNavigate={onNavigate} /></header>
      <section className="heading"><div><p className="eyebrow">DỰ BÁO TỪ NHÀ CUNG CẤP</p><h1>Chuẩn bị cho những ngày tới.</h1><p>Nhiệt độ, độ ẩm, gió, lượng mưa và xác suất mưa.</p></div></section>
      <div className="forecast-controls">
        <label>Địa điểm<select value={city} onChange={e => onCityChange(e.target.value as City)}>{cities.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label>Khoảng dự báo<select value={days} onChange={e => setDays(Number(e.target.value))}>{[3, 7, 16].map(n => <option key={n} value={n}>{n} ngày</option>)}</select></label>
        <button className="forecast-refresh" disabled={loading} onClick={() => setRetry(n => n + 1)}>Tải lại</button>
      </div>
      <p className="provider-caption">Nguồn: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · Dữ liệu mô hình, không phải AI do nhóm huấn luyện. Thời gian theo UTC+7.</p>
      {data && <p className="provider-caption">Lấy từ nhà cung cấp lúc {time(data.retrieved_at)} · Kiểm tra lại mỗi 15 phút (không phải giờ phát hành mô hình).{stale && " Dữ liệu đã cũ."}</p>}
      {loading && <p className="notice" role="status">Đang lấy dự báo Open-Meteo…</p>}
      {error && <p className="notice" role="alert">{error} <button onClick={() => setRetry(n => n + 1)}>Thử lại</button>{data && " Đang giữ bản dự báo trước đó."}</p>}
      {data && <>
        <section aria-labelledby="daily-heading"><div className="section-heading"><h2 id="daily-heading">Tổng quan {data.daily.length} ngày</h2><span>Chọn ngày để xem chi tiết theo giờ</span></div>
          <div className="daily-grid">{data.daily.map(day => <button key={day.date} className={`glass day-card ${selected === day.date ? "selected" : ""}`} aria-pressed={selected === day.date} onClick={() => setSelected(day.date)}>
            <span className="day-date">{new Date(day.date + "T12:00:00+07:00").toLocaleDateString("vi-VN", { weekday: "short", day: "2-digit", month: "2-digit", timeZone: "Asia/Ho_Chi_Minh" })}</span>
            <strong>{value(day.temperature_max, "°")} <small>/{value(day.temperature_min, "°")}</small></strong>
            <span>Xác suất mưa cao nhất: {value(day.rain_probability_max, "%")}</span><span>Tổng mưa: {value(day.precipitation_sum, " mm")}</span><span>Gió cao nhất: {value(day.wind_speed_max, " km/h")}</span>
          </button>)}</div>
        </section>
        <section className="glass forecast-hours" aria-labelledby="hourly-heading"><div className="section-heading"><h2 id="hourly-heading">{selected ? `Theo giờ · ${selected.split("-").reverse().join("/")}` : "24 giờ dự báo sắp tới"}</h2>{selected && <button className="forecast-refresh" onClick={() => setSelected("")}>24 giờ sắp tới</button>}</div>
          <p className="provider-caption">Mưa theo giờ là lượng tích lũy trong giờ trước mốc hiển thị (mm); không phải tổng mưa cả ngày. “—” là dữ liệu chưa có.</p>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Bảng dự báo theo giờ"><table><thead><tr>{["Thời gian", "Nhiệt độ", "Độ ẩm", "Gió", "Lượng mưa / giờ", "Xác suất mưa"].map(h => <th key={h} scope="col">{h}</th>)}</tr></thead><tbody>
            {hourly.map(h => <tr key={h.time}><td>{time(h.time)}</td><td>{value(h.temperature, "°C")}</td><td>{value(h.humidity, "%")}</td><td>{value(h.wind_speed, " km/h")}</td><td>{value(h.precipitation, " mm")}</td><td><span className="rain-chance">{value(h.rain_probability, "%")}</span></td></tr>)}
            {!hourly.length && <tr><td colSpan={6}>Chưa có dữ liệu theo giờ trong khoảng này.</td></tr>}
          </tbody></table></div>
        </section>
      </>}
      <footer><p>Dự báo có thể thay đổi theo lần cập nhật mô hình; không phải cảnh báo khí tượng chính thức.</p><p>Weather data by <a href="https://open-meteo.com/">Open-Meteo</a> · <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a></p></footer>
    </main>
  </div>;
}
