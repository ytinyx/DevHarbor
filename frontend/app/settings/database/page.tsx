import { useEffect, useState, type FormEvent } from "react";
import { LoaderCircle, RotateCcw } from "lucide-react";
import { Link } from "react-router-dom";

import { apiGet, apiPost, apiPut } from "@/lib/api";
import styles from "../settings.module.css";

const endpoint = "/api/settings/desktop-database";
const modeLabels = { sqlite: "本机 SQLite", postgresql: "PostgreSQL" };

type DatabaseMode = keyof typeof modeLabels;
type DatabaseSettings = {
  active_mode: DatabaseMode;
  configured_mode: DatabaseMode;
  has_postgresql_url: boolean;
  restart_required: boolean;
  warning: string | null;
};
type ConnectionTest = { ready: boolean; pgvector_available: boolean; message: string };

export default function DatabaseSettingsPage() {
  const [settings, setSettings] = useState<DatabaseSettings | null>(null);
  const [mode, setMode] = useState<DatabaseMode>("sqlite");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState<"test" | "save" | "restart" | null>(null);
  const [test, setTest] = useState<ConnectionTest | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let disposed = false;
    apiGet<DatabaseSettings>(endpoint).then((data) => {
      if (disposed) return;
      setSettings(data);
      setMode(data.configured_mode);
    }).catch(() => {
      if (!disposed) setError("无法读取数据库配置，请重新打开设置后重试。");
    });
    return () => { disposed = true; };
  }, []);

  const postgres = mode === "postgresql";
  const hasSavedPostgres = Boolean(settings?.has_postgresql_url);
  const candidate = url.trim();
  const canTest = postgres && Boolean(candidate || hasSavedPostgres);
  const changed = mode !== settings?.configured_mode || (postgres && Boolean(candidate));

  function clearFeedback() {
    setError("");
    setNotice("");
    setTest(null);
  }

  async function testConnection() {
    if (!canTest || busy) return;
    setBusy("test");
    clearFeedback();
    try {
      setTest(await apiPost<ConnectionTest>(`${endpoint}/test`, candidate ? { url: candidate } : {}));
    } catch {
      setError("连接测试未完成，请稍后重试。");
    } finally {
      setBusy(null);
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !changed || (postgres && !canTest)) return;
    setBusy("save");
    setError("");
    setNotice("");
    try {
      const saved = await apiPut<DatabaseSettings>(endpoint, {
        mode,
        ...(postgres && candidate ? { url: candidate } : {}),
      });
      setSettings(saved);
      setMode(saved.configured_mode);
      setUrl("");
      if (!saved.restart_required) setNotice("数据库配置已保存。");
    } catch {
      setError("未能保存数据库配置。请检查连接串，或先测试连接。");
    } finally {
      setBusy(null);
    }
  }

  async function restart() {
    const desktop = window.devharborDesktop;
    if (busy || changed || !settings?.restart_required) return;
    if (!desktop?.restart) {
      setError("请退出并重新打开应用，以启用已保存的数据库配置。");
      return;
    }
    setBusy("restart");
    setError("");
    try {
      await desktop.restart();
    } catch {
      setBusy(null);
      setError("自动重启失败，请退出并重新打开应用。");
    }
  }

  return <section className={styles.content} aria-labelledby="database-settings-heading">
    <header className={styles.pageHeader}>
      <h2 id="database-settings-heading">数据库连接</h2>
      <p>切换后，应用会读取所选数据库中的项目、会话和知识库。选回本机 SQLite 即可访问原来的本地数据。</p>
    </header>
    {!settings && !error && <p role="status" className={styles.loading}><LoaderCircle size={16} className="animate-spin" />正在读取配置…</p>}
    {settings?.warning && <div role="alert" className={styles.error}>{settings.warning}</div>}
    {settings && <>
      <div className={styles.currentModel}>
        <div><span>当前连接</span><p>{modeLabels[settings.active_mode]}</p></div>
        {settings.active_mode !== settings.configured_mode && <div><span>已保存的连接方式</span><p>{modeLabels[settings.configured_mode]}</p></div>}
      </div>
      <form onSubmit={save}>
        <fieldset className={styles.fields} disabled={busy !== null}>
          <div className={styles.settingRow}>
            <label className={styles.label} htmlFor="database-mode">连接方式</label>
            <select id="database-mode" className={styles.input} value={mode} onChange={(event) => {
              setMode(event.target.value as DatabaseMode);
              setUrl("");
              clearFeedback();
            }}>
              <option value="sqlite">{modeLabels.sqlite}</option>
              <option value="postgresql">{modeLabels.postgresql}</option>
            </select>
          </div>
          {postgres && <div className={styles.settingRow}>
            <div className={styles.label}>
              <label htmlFor="database-url">PostgreSQL 连接串</label>
              <p id="database-url-hint">{hasSavedPostgres ? "已保存连接串，留空可使用现有配置。" : "填写连接串后，可以先测试连接再保存。"}</p>
            </div>
            <div className={styles.control}>
              <input id="database-url" type="password" className={styles.input} aria-describedby="database-url-hint" autoComplete="new-password" spellCheck={false} required={!hasSavedPostgres} value={url} onChange={(event) => {
                setUrl(event.target.value);
                clearFeedback();
              }} placeholder="postgresql://用户:密码@主机:5432/库名?sslmode=require" />
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" className={styles.button} disabled={!canTest} onClick={() => void testConnection()}>
                  {busy === "test" && <LoaderCircle size={14} className="animate-spin" />}
                  {busy === "test" ? "正在测试…" : "测试连接"}
                </button>
                <p className={styles.hint}><Link to="/settings/retrieval">设置 pgvector 向量存储</Link></p>
              </div>
              {test && <div className={test.ready ? styles.notice : styles.error} role={test.ready ? "status" : "alert"}>
                <div>
                  <p>{test.message}</p>
                  {test.ready && <p>{test.pgvector_available ? "pgvector 可用" : "pgvector 不可用"}</p>}
                </div>
              </div>}
            </div>
          </div>}
        </fieldset>
        {settings.restart_required && <p role="status" className={styles.notice}>数据库配置已保存，重启应用后生效。</p>}
        {notice && <p role="status" className={styles.notice}>{notice}</p>}
        {error && <p role="alert" className={styles.error}>{error}</p>}
        <div className={styles.formFooter}>
          <div>
            {settings.restart_required && <button type="button" className={styles.button} disabled={busy !== null || changed} onClick={() => void restart()}>
              {busy === "restart" ? <LoaderCircle size={14} className="animate-spin" /> : <RotateCcw size={14} />}
              {busy === "restart" ? "正在重启…" : "重启应用"}
            </button>}
            <button type="submit" className={styles.primaryButton} disabled={busy !== null || !changed || (postgres && !canTest)}>{busy === "save" ? "正在保存…" : "保存配置"}</button>
          </div>
        </div>
      </form>
    </>}
    {!settings && error && <p role="alert" className={styles.error}>{error}</p>}
  </section>;
}
