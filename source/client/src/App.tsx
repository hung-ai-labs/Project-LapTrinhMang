import { useEffect, useState } from "react";
import { auth, getAuthSession, restoreAuthSession } from "./lib/auth";
import PageTabs from "./components/PageTabs";
import ProviderForecastPage from "./components/ProviderForecastPage";
import type { City } from "./lib/api";
import AuthPage from "./components/AuthPage";
import { useDayPeriod } from "./hooks/useDayPeriod";
import { useWeather } from "./hooks/useWeather";
import { useLocations } from "./hooks/useLocations";

const time = (value: string) => new Date(value).toLocaleTimeString("vi-VN", {
  timeZone: "Asia/Ho_Chi_Minh", hour: "2-digit", minute: "2-digit",
});

export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [forecastCity, setForecastCity] = useState<City>("hanoi");
  const locations = useLocations();
  useEffect(() => {
    const sync = () => setPath(window.location.pathname);
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  const navigate = (next: string) => {
    window.history.pushState({}, "", next);
    setPath(window.location.pathname);
    window.scrollTo({ top: 0, behavior: "instant" });
  };
  if (path === "/login" || path === "/register") {
    return <AuthPage onGuest={() => navigate("/")} />;
  }
  if (path === "/forecast") return <ProviderForecastPage onNavigate={navigate} city={forecastCity} onCityChange={setForecastCity} />;
  return <Dashboard onNavigate={navigate} locations={locations} view={path} />;
}

function Dashboard({ onNavigate, locations, view }: {
  onNavigate: (path: string) => void; locations: ReturnType<typeof useLocations>; view: string;
}) {
  const [account, setAccount] = useState(getAuthSession);
  useEffect(() => {
    const expired = () => { setAccount(null); setLogoutError("Phiên đăng nhập đã hết hạn."); };
    let disposed = false;
    const validate = () => {
      void restoreAuthSession().then(restored => { if (!disposed) setAccount(restored); });
    };
    window.addEventListener("auth-expired", expired);
    window.addEventListener("focus", validate);
    validate();
    return () => {
      disposed = true;
      window.removeEventListener("auth-expired", expired);
      window.removeEventListener("focus", validate);
    };
  }, []);
  const [logoutError, setLogoutError] = useState("");
  const { event, forecast, forecastError,
    forecastLoading, forecastStale, requestForecast, status, error, stale, offline } = useWeather(
    locations.effectiveWardId,
  );
  const disconnected = offline || locations.offline || !locations.online;
  const period = useDayPeriod();
  const current = event?.observation;
  // Scenes illustrate observations because the API does not expose condition codes.
  const scene = !current ? "waiting" : current.rainfall > 0 ? "rain" : current.wind_speed >= 30 ? "wind" : current.humidity >= 80 ? "cloud" : "clear";
  const condition = { waiting: "Đang chờ dữ liệu", rain: "Có mưa", wind: "Gió mạnh", cloud: "Độ ẩm cao", clear: "Không ghi nhận mưa" }[scene];
  const source = !current ? "Chưa có dữ liệu" : current.source === "simulator" ? "Dữ liệu mô phỏng" : current.source === "provider" ? "Open-Meteo · dữ liệu mô hình" : `Nguồn: ${current.source}`;

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
          <PageTabs onNavigate={onNavigate} />
          <div className="account-actions">
            {account ? <>
              <span>{account.user.name}</span>
              <button onClick={async () => {
                try { await auth.logout(); setAccount(null); setLogoutError(""); }
                catch { setLogoutError("Không thể đăng xuất. Vui lòng thử lại."); }
              }}>Đăng xuất</button>
            </> : <>
              <a href="/login" onClick={(event) => { event.preventDefault(); onNavigate("/login"); }}>Đăng nhập</a>
              <a href="/register" onClick={(event) => { event.preventDefault(); onNavigate("/register"); }}>Đăng ký</a>
            </>}
            <span className={`connection ${status === "Đang trực tuyến" ? "online" : ""}`}>● {status}</span>
          </div>
        </header>
        <section className="heading">
          <div>
            <p className="eyebrow">QUAN SÁT · DỰ BÁO · CẢNH BÁO</p>
            <h1>{view === "/alerts" ? "Cảnh báo thời tiết." : "Thời tiết trong tầm mắt."}</h1>
            <p>Dữ liệu liên tục, cập nhật qua từng bản tin.</p>
          </div>
          <div className="location-filters" aria-label="Chọn địa điểm theo dõi">
            <label className="location-field">
              <span>Tỉnh / Thành phố</span>
              <select value={locations.provinceId ?? ""}
                onChange={(event) => locations.selectProvince(event.target.value)}
                disabled={locations.provinceLoading}>
                <option value="">{locations.provinceLoading ? "Đang tải tỉnh/thành…" : "Chọn tỉnh/thành phố"}</option>
                {locations.provinces.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>
            <label className="location-field">
              <span>Phường / Xã</span>
              <select value={locations.selectedWardId ?? ""}
                onChange={(event) => locations.selectWard(event.target.value)}
                disabled={!locations.provinceId || locations.wardLoading || !locations.wards.length}>
                <option value="">{locations.wardLoading ? "Đang tải phường/xã…" :
                  !locations.provinceId ? "Chọn tỉnh/thành trước" :
                  locations.wards.length ? `Mặc định: ${locations.wards[0].name} — chưa chọn thủ công${locations.catalogFromCache ? " (bộ nhớ đệm)" : ""}` : "Chưa có phường/xã"}</option>
                {locations.wards.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>
          </div>
        </section>
        {logoutError && <p role="alert">{logoutError}</p>}
        {disconnected && <p className="notice" role="status">
          Mất kết nối — đang thử lại tự động. Số liệu đang hiển thị là bản gần nhất.
        </p>}
        {locations.error && <p className="notice" role="alert">{locations.error}{" "}
          <button type="button" className="catalog-retry" onClick={locations.reload}>Thử lại</button>
        </p>}
        {!locations.provinceLoading && !locations.error && !locations.provinces.length &&
          <p className="notice" role="status">Chưa có danh mục tỉnh/thành phố.</p>}
        {error && <p className="notice" role="status">{error}</p>}
        <div className={`dashboard ${view === "/alerts" ? "single-page" : ""}`}>
          {view !== "/alerts" && <>
          <section className="glass current" aria-label="Thời tiết hiện tại">
            <div className="section-heading">
              <h2 className="city-name">{locations.effectiveWard?.name ?? "Chọn phường/xã"}</h2>
              <span className="tag">{source}</span>
            </div>
            {locations.province && <p className="location-context">{locations.province.name}</p>}
            <div className="temperature">
              {current ? Math.round(current.temperature) : "—"}<span>°C</span>
              <span className="condition-icon" aria-hidden="true">{scene === "rain" ? "☂" : scene === "wind" ? "≋" : scene === "clear" ? (period === "night" ? "☾" : "☀") : "☁"}</span>
            </div>
            <p className="condition-label">{condition}</p>
            <p className="updated">{current ? `Cập nhật ${time(current.observed_at)} · giờ Việt Nam${stale ? " · dữ liệu cũ" : ""}` : locations.effectiveWardId ? "Chưa có dữ liệu thời tiết cho phường/xã này" : "Chọn tỉnh/thành và phường/xã để xem thời tiết"}</p>
            <div className="metrics">
              <div><small>Độ ẩm</small><strong>{current?.humidity ?? "—"}<em>%</em></strong></div>
              <div><small>Tốc độ gió</small><strong>{current?.wind_speed ?? "—"}<em>km/h</em></strong></div>
              <div><small>Lượng mưa</small><strong>{current?.rainfall ?? "—"}<em>mm/h</em></strong></div>
            </div>
          </section>
          <section className="glass forecast">
            <h2><span aria-hidden="true">◷</span> {forecast ? `Dự báo ${time(forecast.target_at)}` : "Dự báo giờ kế tiếp"}</h2>
            <div className="forecast-line"><strong>{forecast?.predicted_temperature ?? "—"}<span>°C</span></strong><span className="forecast-symbol" aria-hidden="true">☁</span></div>
            {forecast ? <>
              <p>Độ ẩm {forecast.predicted_humidity}% · Gió {forecast.predicted_wind_speed} km/h</p>
              <p>Giáng thủy giờ kết thúc lúc {time(forecast.target_at)}: {forecast.precipitation_mm} mm</p>
              <small>Open-Meteo · Dự báo mô hình · Lấy lúc {time(forecast.fetched_at)} · Giờ Việt Nam{forecastStale ? " · dự báo cũ" : ""}</small>
            </> : <p role="status">{forecastLoading ? "Đang lấy dự báo…" : forecastError ||
              (locations.effectiveWardId ? "Chưa có dự báo." : "Chọn địa điểm để xem dự báo.")}</p>}
            <button type="button" className="catalog-retry forecast-refresh"
              disabled={!locations.effectiveWardId || forecastLoading} onClick={requestForecast}>
              {forecastLoading ? "Đang lấy dự báo…" : "Làm mới dự báo"}
            </button>
          </section>
          </>}
          <section className="glass alerts" aria-live="polite">
            <h2><span aria-hidden="true">⚠</span> Cảnh báo thời tiết</h2>
            {!event ? <p>Chưa có dữ liệu để đánh giá.</p> : !event.alerts.length ? <p>Chưa ghi nhận chỉ số vượt ngưỡng.</p> : event.alerts.map((alert) => <p className="alert" key={alert.code}>{alert.message}</p>)}
            <small>Ngưỡng demo · Không thay thế cảnh báo khí tượng chính thức</small>
          </section>
        </div>
        <footer><p>Nguồn: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> · <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> · Mưa quy đổi theo kỳ tích lũy sang mm/h.</p><p>Weather Stream · Giờ Việt Nam (UTC+7)</p><p>Nền minh họa theo thời tiết và giờ Việt Nam · Không phải ảnh trực tiếp</p></footer>
      </main>
    </div>
  );
}
