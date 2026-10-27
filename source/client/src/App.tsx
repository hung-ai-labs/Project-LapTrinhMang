import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useDayPeriod } from "./hooks/useDayPeriod";
import { useWeather } from "./hooks/useWeather";
import type { City } from "./lib/api";

const cities: CityOption[] = [
  { id: "hanoi", name: "Hà Nội", region: "Miền Bắc" },
  { id: "danang", name: "Đà Nẵng", region: "Miền Trung" },
  { id: "hcm", name: "TP. Hồ Chí Minh", region: "Miền Nam" },
];
const time = (value: string) => new Date(value).toLocaleTimeString("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit",
});

type CityOption = { id: City; name: string; region: string };

interface CityPickerProps {
  value: City;
  options: CityOption[];
  onChange: (city: City) => void;
}

function CityPicker({ value, options, onChange }: CityPickerProps) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const search = useRef({ text: "", time: 0 });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const selectedIndex = options.findIndex((option) => option.id === value);
  const selected = options[selectedIndex];

  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);

  const show = () => {
    setActive(selectedIndex);
    setOpen(true);
  };
  const choose = (index: number) => {
    onChange(options[index].id);
    setOpen(false);
    trigger.current?.focus();
  };
  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    const { key } = event;
    if (key === "Escape") {
      if (open) event.preventDefault();
      setOpen(false);
    } else if (key === "ArrowDown" || key === "ArrowUp") {
      event.preventDefault();
      if (!open) show();
      else setActive((index) => (index + (key === "ArrowDown" ? 1 : -1) + options.length) % options.length);
    } else if (key === "Home" || key === "End") {
      event.preventDefault();
      setOpen(true);
      setActive(key === "Home" ? 0 : options.length - 1);
    } else if ((key === "Enter" || key === " ") && open) {
      event.preventDefault();
      choose(active);
    } else if (key.length === 1 && key !== " " && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const now = Date.now();
      const text = (now - search.current.time < 700 ? search.current.text : "") + key;
      search.current = { text, time: now };
      const normalize = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/gi, "d").toLowerCase();
      const index = options.findIndex((option) => normalize(option.name).startsWith(normalize(text)));
      if (index >= 0) {
        event.preventDefault();
        setActive(index);
        setOpen(true);
      }
    }
  };

  return (
    <div className="city-picker" ref={root} onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOpen(false);
    }}>
      <span className="picker-label" id={`${id}-label`}>Địa điểm theo dõi</span>
      <button
        ref={trigger}
        type="button"
        role="combobox"
        className="picker-trigger"
        aria-labelledby={`${id}-label ${id}-value`}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={open ? `${id}-list` : undefined}
        aria-activedescendant={open ? `${id}-option-${active}` : undefined}
        onClick={() => open ? setOpen(false) : show()}
        onKeyDown={handleKeyDown}
      >
        <span className="picker-value" id={`${id}-value`}>{selected.name}</span>
        <svg className={`picker-chevron ${open ? "is-open" : ""}`} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
      </button>
      {open && (
        <ul className="picker-list" id={`${id}-list`} role="listbox" aria-labelledby={`${id}-label`}>
          {options.map((option, index) => (
            <li
              key={option.id}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={value === option.id}
              className={`picker-option ${active === index ? "is-active" : ""}`}
              onPointerMove={() => setActive(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(index)}
            >
              <span>{option.name}<small>{option.region} · Việt Nam</small></span>
              {value === option.id && <span className="picker-check" aria-hidden="true">✓</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function App() {
  const [city, setCity] = useState<City>("hanoi");
  const { event, history, forecast, status, error } = useWeather(city);
  const period = useDayPeriod();
  const current = event?.observation;
  const selected = cities.find((item) => item.id === city)!;
  // Scenes illustrate observations because the API does not expose condition codes.
  const scene = !current ? "waiting" : current.rainfall > 0 ? "rain" : current.wind_speed >= 30 ? "wind" : current.humidity >= 80 ? "cloud" : "clear";
  const condition = { waiting: "Đang chờ dữ liệu", rain: "Có mưa", wind: "Gió mạnh", cloud: "Độ ẩm cao", clear: "Không ghi nhận mưa" }[scene];
  const source = !current ? "Chưa có dữ liệu" : current.source === "simulator" ? "Dữ liệu mô phỏng" : current.source === "provider" ? "Dữ liệu nhà cung cấp" : `Nguồn: ${current.source}`;

  return (
    <div className={`weather-app period-${period} scene-${scene}`}>
      <div className="weather-scene" aria-hidden="true">
        <div className="stars" /><div className="celestial-body" /><div className="sky-light" /><div className="cloud cloud-one" />
        <div className="cloud cloud-two" /><div className="cloud cloud-three" />
        <div className="rainfall" />
      </div>
      <main id="weather-content">
        <header className="page-header">
          <a className="brand" href="/">
            <span aria-hidden="true">☁</span>
            <span>Weather Stream<small>TRẠM THỜI TIẾT TRỰC TUYẾN</small></span>
          </a>
          <span className={`connection ${status === "Đang trực tuyến" ? "online" : ""}`}>● {status}</span>
        </header>
        <section className="heading">
          <div>
            <p className="eyebrow">QUAN SÁT · DỰ BÁO · CẢNH BÁO</p>
            <h1>Thời tiết trong tầm mắt.</h1>
            <p>Dữ liệu liên tục, cập nhật qua từng bản tin.</p>
          </div>
          <CityPicker value={city} options={cities} onChange={setCity} />
        </section>
        {error && <p className="notice" role="status">{error}</p>}
        <div className="dashboard">
          <section className="glass current" aria-label="Thời tiết hiện tại">
            <div className="section-heading">
              <h2 className="city-name">{selected.name}</h2>
              <span className="tag">{source}</span>
            </div>
            <div className="temperature">
              {current ? Math.round(current.temperature) : "—"}<span>°C</span>
              <span className="condition-icon" aria-hidden="true">{scene === "rain" ? "☂" : scene === "wind" ? "≋" : scene === "clear" ? (period === "night" ? "☾" : "☀") : "☁"}</span>
            </div>
            <p className="condition-label">{condition}</p>
            <p className="updated">{current ? `Cập nhật ${time(current.observed_at)} · giờ Việt Nam` : "Đang chờ bản tin thời tiết đầu tiên"}</p>
            <div className="metrics">
              <div><small>Độ ẩm</small><strong>{current?.humidity ?? "—"}<em>%</em></strong></div>
              <div><small>Tốc độ gió</small><strong>{current?.wind_speed ?? "—"}<em>km/h</em></strong></div>
              <div><small>Lượng mưa</small><strong>{current?.rainfall ?? "—"}<em>mm/h</em></strong></div>
            </div>
          </section>
          <section className="glass forecast">
            <h2><span aria-hidden="true">◷</span> Dự báo 1 giờ tới</h2>
            <div className="forecast-line"><strong>{forecast?.predicted_temperature ?? "—"}<span>°C</span></strong><span className="forecast-symbol" aria-hidden="true">☁</span></div>
            <p>{forecast?.message ?? "Chờ dữ liệu để tạo dự báo cơ sở."}</p>
            <small>Baseline persistence · Chưa tích hợp AI</small>
          </section>
          <section className="glass alerts" aria-live="polite">
            <h2><span aria-hidden="true">⚠</span> Cảnh báo thời tiết</h2>
            {!event ? <p>Chưa có dữ liệu để đánh giá.</p> : !event.alerts.length ? <p>Chưa ghi nhận chỉ số vượt ngưỡng.</p> : event.alerts.map((alert) => <p className="alert" key={alert.code}>{alert.message}</p>)}
            <small>Ngưỡng demo · Không thay thế cảnh báo khí tượng chính thức</small>
          </section>
          <section className="glass history">
            <div className="section-heading"><h2>Lịch sử quan sát</h2><span>{history.length} / 60 bản tin</span></div>
            <div className="table-wrap" tabIndex={0} role="region" aria-label="Bảng lịch sử thời tiết">
              <table><thead><tr><th scope="col">Thời gian</th><th scope="col">Nhiệt độ</th><th scope="col">Độ ẩm</th><th scope="col">Mưa</th></tr></thead><tbody>
                {history.map((record) => <tr key={record.id}><td>{time(record.observed_at)}</td><td>{record.temperature} °C</td><td>{record.humidity}%</td><td>{record.rainfall} mm/h</td></tr>)}
                {!history.length && <tr><td colSpan={4}>Chưa có lịch sử cho địa điểm này.</td></tr>}
              </tbody></table>
            </div>
          </section>
        </div>
        <footer><p>Weather Stream · Giờ Việt Nam (UTC+7)</p><p>Nền minh họa theo thời tiết và giờ Việt Nam · Không phải ảnh trực tiếp</p></footer>
      </main>
    </div>
  );
}
