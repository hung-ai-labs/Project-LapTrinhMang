import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { useTimeTheme } from "../hooks/useTimeTheme";
import { estimatePasswordStrength } from "../lib/password";
import "./auth.css";

export default function AuthPage({ onGuest }: { onGuest: () => void }) {
  const theme = useTimeTheme();
  const [register, setRegister] = useState(window.location.pathname === "/register");
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const strength = estimatePasswordStrength(password);
  const confirmationMatches = password.length > 0 && password === confirmation;

  function resetPasswordFeedback() {
    setPassword(""); setConfirmation("");
  }

  useEffect(() => {
    const sync = () => { setRegister(window.location.pathname === "/register"); setError(""); setShowPassword(false); resetPasswordFeedback(); };
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  function switchMode(next: boolean) {
    setRegister(next); setError(""); setShowPassword(false);
    resetPasswordFeedback();
    window.history.pushState({}, "", next ? "/register" : "/login");
  }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError("");
    const form = new FormData(event.currentTarget);
    if (register && !String(form.get("name") ?? "").trim()) { setError("Vui lòng nhập họ tên."); return; }
    if (register && form.get("password") !== form.get("confirmation")) { setError("Mật khẩu xác nhận chưa khớp."); return; }
    // Connect AuthAdapter here when the JWT backend is available.
  }

  return <main className={`auth-page ${theme}`}>
    <header className="auth-header">
      <a href="/" className="brand" onClick={(event) => { event.preventDefault(); onGuest(); }}><span aria-hidden="true">◉</span> Weather Stream</a>
      <a href="/" className="auth-back" onClick={(event) => { event.preventDefault(); onGuest(); }}>← Dashboard</a>
    </header>
    <section className="card auth-panel" aria-labelledby="auth-title">
        <div className="auth-weather-art" aria-hidden="true">
          <div className="auth-weather-orbit" />
          <div className="auth-weather-sun" />
          <div className="auth-weather-stars"><i /><i /><i /><i /></div>
          <div className="auth-weather-cloud auth-weather-cloud-back" />
          <div className="auth-weather-cloud auth-weather-cloud-front" />
          <svg className="auth-weather-waves" viewBox="0 0 440 130" fill="none" preserveAspectRatio="none">
            {[0, 18, 36, 54, 72].map((offset) => <path key={offset} d={`M-40 ${78 + offset} C100 ${-32 + offset} 250 ${170 + offset} 480 ${20 + offset}`} />)}
          </svg>
        </div>
        <div className="auth-panel-body">
        <h1 id="auth-title">{register ? "Đăng ký" : "Đăng nhập"}</h1>
        <button type="button" className="google-status google-action" disabled title="Đăng nhập Google chưa được kết nối"><span aria-hidden="true" className="google-g">G</span>Tiếp tục với Google</button>
        <div className="auth-divider"><span>hoặc dùng email</span></div>
        <form key={register ? "register" : "login"} onSubmit={submit}>
          <fieldset>
            {register && <div className="auth-field"><label htmlFor="name">Họ và tên</label><input id="name" name="name" autoComplete="name" placeholder="Nguyễn Minh Anh" required maxLength={100} /></div>}
            <div className="auth-field"><label htmlFor="email">Địa chỉ email</label><input id="email" name="email" type="email" autoComplete="email" placeholder="ban@example.com" required maxLength={254} /></div>
            <div className="auth-field"><label htmlFor="password">Mật khẩu</label><div className="password-field"><input id="password" name="password" value={password} onChange={(event) => { setPassword(event.target.value); setError(""); }} type={showPassword ? "text" : "password"} autoComplete={register ? "new-password" : "current-password"} placeholder={register ? "Ít nhất 8 ký tự" : "Nhập mật khẩu của bạn"} required minLength={8} maxLength={128} aria-describedby={register ? strength.hint ? "password-hint password-strength" : "password-strength" : undefined} /><button type="button" aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Ẩn" : "Hiện"}</button></div>{register && <div className="password-feedback" data-strength={strength.score}>
              <div className="password-strength-heading"><span>Độ mạnh ước tính</span><strong id="password-strength" aria-live="polite">{strength.label}</strong></div>
              <meter className="password-meter" min={0} max={3} value={strength.score} aria-label="Độ mạnh mật khẩu ước tính" aria-valuetext={strength.label} />
              {strength.hint && <small id="password-hint">{strength.hint}</small>}
            </div>}</div>
            {register && <div className="auth-field"><label htmlFor="confirmation">Xác nhận mật khẩu</label><input id="confirmation" name="confirmation" value={confirmation} onChange={(event) => { setConfirmation(event.target.value); setError(""); }} aria-describedby={confirmationMatches ? undefined : "confirmation-status"} aria-invalid={confirmation.length > 0 && !confirmationMatches} type={showPassword ? "text" : "password"} autoComplete="new-password" placeholder="Nhập lại mật khẩu" required minLength={8} maxLength={128} />
              {!confirmationMatches && <p id="confirmation-status" className={`confirmation-status ${confirmation ? confirmationMatches ? "is-match" : "is-mismatch" : ""}`} aria-live="polite" aria-atomic="true">
                {confirmation ? confirmationMatches ? "✓ Mật khẩu xác nhận trùng khớp." : "! Mật khẩu xác nhận chưa khớp." : "Nhập lại mật khẩu để kiểm tra."}
              </p>}
            </div>}
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" type="submit">{register ? "Tạo tài khoản" : "Đăng nhập"}</button>
          </fieldset>
        </form>
        <p className="auth-switch">{register ? "Đã có tài khoản?" : "Chưa có tài khoản?"} <button type="button" onClick={() => switchMode(!register)}>{register ? "Đăng nhập" : "Đăng ký ngay"}</button></p>
        </div>
    </section>
  </main>;
}
