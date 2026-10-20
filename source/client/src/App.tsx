import { useState } from "react";
import { useWeather } from "./hooks/useWeather";
import type { City } from "./lib/api";

const cities: { id: City; name: string }[] = [
  { id: "hanoi", name: "Hà Nội" },
  { id: "danang", name: "Đà Nẵng" },
  { id: "hcm", name: "TP. Hồ Chí Minh" },
];
const time = (value: string) =>
  new Date(value).toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

export default function App() {
  const [city, setCity] = useState<City>("hanoi");
  const { event, history, forecast, status, error } = useWeather(city);
  const current = event?.observation;
  const selected = cities.find((item) => item.id === city)!;
  return (
    <main>
      <header>
        <a className="brand" href="/">
          ◉{" "}
          <span>
            Weather Stream<small>TRẠM THỜI TIẾT TRỰC TUYẾN</small>
          </span>
        </a>
        <span
          className={`connection ${status === "Đang trực tuyến" ? "online" : ""}`}
        >
          ● {status}
        </span>
      </header>
      <section className="heading">
        <div>
          <p className="eyebrow">QUAN SÁT · DỰ BÁO · CẢNH BÁO</p>
          <h1>Thời tiết trong tầm mắt.</h1>
          <p>Dữ liệu liên tục, cập nhật qua từng bản tin.</p>
        </div>
        <label>
          Địa điểm theo dõi
          <select
            value={city}
            onChange={(e) => setCity(e.target.value as City)}
          >
            {cities.map((item) => (
              <option value={item.id} key={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </section>
      {error && (
        <p className="notice" role="status">
          {error}
        </p>
      )}
      <div className="dashboard">
        <section className="card current">
          <div className="row">
            <h2>{selected.name}</h2>
            <span className="tag">
              {current?.source === "provider"
                ? "Dữ liệu nhà cung cấp"
                : "Dữ liệu mô phỏng"}
            </span>
          </div>
          <div className="temperature">
            {current ? Math.round(current.temperature) : "—"}
            <span>°C</span>
            <span className="sun">☀</span>
          </div>
          <p className="muted">
            {current
              ? `Cập nhật ${time(current.observed_at)} · giờ Việt Nam`
              : "Đang chờ bản tin đầu tiên từ TCP publisher"}
          </p>
          <div className="metrics">
            <div>
              <small>Độ ẩm</small>
              <strong>
                {current?.humidity ?? "—"}
                <em>%</em>
              </strong>
            </div>
            <div>
              <small>Tốc độ gió</small>
              <strong>
                {current?.wind_speed ?? "—"}
                <em>km/h</em>
              </strong>
            </div>
            <div>
              <small>Lượng mưa</small>
              <strong>
                {current?.rainfall ?? "—"}
                <em>mm/h</em>
              </strong>
            </div>
          </div>
        </section>
        <section className="card forecast">
          <p className="eyebrow">DỰ BÁO 1 GIỜ TIẾP THEO</p>
          <h2>Khởi đầu từ baseline</h2>
          <div className="forecast-value">
            {forecast?.predicted_temperature ?? "—"}
            <span>°C</span>
          </div>
          <p>{forecast?.message ?? "Chờ dữ liệu để tạo dự báo cơ sở."}</p>
          <span className="tag">Chưa tích hợp AI</span>
        </section>
        <section className="card alerts" aria-live="polite">
          <div className="row">
            <h2>Cảnh báo thời tiết</h2>
            <span className="muted">Ngưỡng demo</span>
          </div>
          {!event ? (
            <p className="muted">Chưa có dữ liệu để đánh giá.</p>
          ) : !event.alerts.length ? (
            <p className="clear">✓ Chưa ghi nhận chỉ số vượt ngưỡng.</p>
          ) : (
            event.alerts.map((alert) => (
              <div className="alert" key={alert.code}>
                ⚠ {alert.message}
              </div>
            ))
          )}
        </section>
        <section className="card history">
          <div className="row">
            <h2>Dòng dữ liệu gần đây</h2>
            <span className="tag">{history.length} / 60 bản tin</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Thời gian</th>
                  <th>Nhiệt độ</th>
                  <th>Độ ẩm</th>
                  <th>Mưa</th>
                </tr>
              </thead>
              <tbody>
                {history.map((record) => (
                  <tr key={record.id}>
                    <td>{time(record.observed_at)}</td>
                    <td>{record.temperature}°C</td>
                    <td>{record.humidity}%</td>
                    <td>{record.rainfall} mm/h</td>
                  </tr>
                ))}
                {!history.length && (
                  <tr>
                    <td colSpan={4}>
                      Chạy simulator để xem dữ liệu streaming tại đây.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
      <footer>
        <span>Đồ án Lập trình mạng · FastAPI + React</span>
        <span>TCP → PostgreSQL → WebSocket</span>
      </footer>
    </main>
  );
}
