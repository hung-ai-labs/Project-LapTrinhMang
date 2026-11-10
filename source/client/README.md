# Client · React + TypeScript + Vite

Node.js 22.12+.

```bash
npm ci
npm run dev
```

Mở http://localhost:5173. Chạy server ở cổng 8000 trước.
Vite proxy `/api` và WebSocket về FastAPI. Bản Docker dùng Nginx proxy cùng origin,
không cần hardcode URL backend trong mã frontend.

```bash
npm run build
npm run preview
```

`preview` chỉ xem bản build; muốn gọi API dùng Vite dev server hoặc Docker/Nginx.
`src/lib/api.ts`: kiểu dữ liệu và REST wrapper (timeout 10 giây, thông báo lỗi mạng tiếng Việt).
`src/hooks/useWeather.ts`: WebSocket, reconnect/backoff, tải lại dữ liệu sau reconnect.
`src/hooks/useLocations.ts`: danh mục tỉnh/xã, nhớ bản cache và lựa chọn cuối.
`src/hooks/useConnection.ts`: trạng thái mạng và số lần mạng quay lại.
`src/lib/connection.ts`: bus sự kiện `online`/`offline` dùng chung cho cả app.
`src/lib/catalog.ts`: bộ nạp tài nguyên có cache offline, retry và làm mới tức thì.
`src/lib/realtime.ts`: chính sách backoff và ngưỡng heartbeat watchdog cho socket.
`src/App.tsx`: dashboard; `src/styles.css`: responsive styling.
Hướng dẫn đầy đủ và giới hạn tại [README chính](../../README.md).
