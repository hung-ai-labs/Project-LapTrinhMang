// A local UI estimate, not a breach check or a backend password policy.
export function estimatePasswordStrength(password: string) {
  if (!password) return { score: 0, label: "Chưa nhập", hint: "Sử dụng từ 8 đến 128 ký tự." };
  const common = /password|123456|qwerty|matkhau|admin|letmein/i.test(password);
  const repeated = /^(.)\1+$/.test(password) || /^(.{1,4})\1+$/.test(password);
  const variety = [/[a-z]/, /[A-Z]/, /\d/, /[^a-zA-Z0-9]/].filter((rule) => rule.test(password)).length;
  if (password.length < 8 || common || repeated) {
    return { score: 1, label: "Yếu", hint: "Tránh chuỗi phổ biến, lặp lại; thử mật khẩu dài hơn." };
  }
  if (password.length >= 16 || (password.length >= 12 && variety >= 3)) {
    return { score: 3, label: "Mạnh", hint: "" };
  }
  return { score: 2, label: "Trung bình", hint: "Thử ít nhất 12 ký tự và kết hợp nhiều loại ký tự." };
}
