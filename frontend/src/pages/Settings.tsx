import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { apiClient } from "../api/client";

type Theme = "dark" | "light";

function Icon({ name }: { name: "arrow" | "check" }) {
  const path = name === "arrow" ? <><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></> : <path d="m5 12 4 4L19 6" />;
  return <svg className="odin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{path}</svg>;
}

export default function Settings() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<Theme>((localStorage.getItem("odin-theme") as Theme) || "dark");
  const [email, setEmail] = useState("your account");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("odin-theme", theme);
    window.dispatchEvent(new Event("odin-theme-change"));
  }, [theme]);

  useEffect(() => {
    apiClient
      .get("/auth/me")
      .then(({ data }) => setEmail(data.email))
      .catch(() => setError("Could not load account details."));
  }, []);

  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      await apiClient.post("/auth/change-password", { current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Your password was updated.");
    } catch (requestError) {
      setError(axios.isAxiosError(requestError) ? String(requestError.response?.data?.detail || "Could not update password.") : "Could not update password.");
    }
  };

  return (
    <div className={`settings-page ${theme === "dark" ? "is-dark" : "is-light"}`}>
      <aside className="settings-sidebar">
        <button className="brand-lockup" onClick={() => navigate("/")}><span className="odin-mark">✦</span><span>Odin</span></button>
        <p className="settings-kicker">Workspace</p>
        <button className="settings-back" onClick={() => navigate("/")}><Icon name="arrow" /> Back to advisor</button>
        <div className="settings-sidebar-spacer" />
        <div className="profile-mini"><div className="profile-avatar">O</div><div><strong>Odin user</strong><span>{email}</span></div></div>
      </aside>
      <main className="settings-main">
        <header className="settings-header"><div><p className="eyebrow">Control center</p><h1>Settings</h1><p>Shape Odin around the way you think and work.</p></div><div className="status-pill"><span /> All systems ready</div></header>
        <div className="settings-content">
          <section className="settings-section"><div className="section-title"><h2>Appearance</h2><p>Choose the atmosphere for your advisor workspace.</p></div><div className="theme-options">
            <button className={`theme-option ${theme === "dark" ? "selected" : ""}`} onClick={() => setTheme("dark")}><div className="theme-preview preview-dark"><span>✦</span><i /><i /><i /></div><div><strong>Dark mode</strong><span>Focused and easy on the eyes</span></div>{theme === "dark" && <b><Icon name="check" /></b>}</button>
            <button className={`theme-option ${theme === "light" ? "selected" : ""}`} onClick={() => setTheme("light")}><div className="theme-preview preview-light"><span>✦</span><i /><i /><i /></div><div><strong>Light mode</strong><span>Bright and open</span></div>{theme === "light" && <b><Icon name="check" /></b>}</button>
          </div></section>
          <section className="settings-section"><div className="section-title"><h2>Account & security</h2><p>Keep your account details protected.</p></div><div className="account-row"><div><span className="field-label">Email address</span><strong>{email}</strong></div><span className="verified">Verified</span></div><form className="password-form" onSubmit={changePassword}><h3>Change password</h3><div className="form-grid"><label>Current password<input type="password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label><label>New password<input type="password" required minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label></div><div className="form-actions"><span className={error ? "form-error" : "form-success"}>{error || message}</span><button className="primary-button" type="submit">Update password</button></div></form></section>
          <section className="settings-section"><div className="section-title"><h2>Advisor preferences</h2><p>Make every conversation feel more like yours.</p></div><div className="preference-list"><label><span><strong>Save conversation history</strong><small>Keep chats available in your sidebar for later.</small></span><input type="checkbox" defaultChecked /></label><label><span><strong>Helpful follow-ups</strong><small>Let Odin suggest useful next questions.</small></span><input type="checkbox" defaultChecked /></label><label><span><strong>Response sound</strong><small>Play a subtle sound when a response is ready.</small></span><input type="checkbox" /></label></div></section>
        </div>
      </main>
    </div>
  );
}