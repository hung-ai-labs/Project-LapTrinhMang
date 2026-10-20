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
`src/lib/api.ts`: kiểu dữ liệu và REST wrapper.
`src/hooks/useWeather.ts`: WebSocket, reconnect/backoff, tải lại dữ liệu sau reconnect.
`src/App.tsx`: dashboard; `src/styles.css`: responsive styling.
Hướng dẫn đầy đủ và giới hạn tại [README chính](../../README.md).
