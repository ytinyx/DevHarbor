import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, LoaderCircle, LockKeyhole, RefreshCw, Search, X } from "lucide-react";

import { agentSettingsError, loadAgentSettings, setAgentEnabled, type AgentCatalog, type AgentDefinition, type AgentGroup } from "@/lib/agent-settings";
import styles from "./agent-management.module.css";

const groups: Array<{ id: AgentGroup; name: string }> = [
  { id: "analysis", name: "专项分析" },
  { id: "coordination", name: "协作流程" },
  { id: "support", name: "辅助角色" },
];

const implementations: Record<AgentDefinition["implementation"], string> = {
  model: "模型分析",
  rules: "规则处理",
  tools: "工具调用",
  workflow: "流程编排",
};

export function AgentManagement() {
  const [catalog, setCatalog] = useState<AgentCatalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyAgent, setBusyAgent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [group, setGroup] = useState<AgentGroup | "all">("all");
  const [expanded, setExpanded] = useState<string | null>(null);
  const alive = useRef(true);
  const requestNumber = useRef(0);
  const requestInFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (requestInFlight.current) return;
    requestInFlight.current = true;
    const request = ++requestNumber.current;
    setLoading(true);
    setError("");
    try {
      const result = await loadAgentSettings();
      if (alive.current && request === requestNumber.current) setCatalog(result);
    } catch (reason) {
      if (alive.current && request === requestNumber.current) setError(agentSettingsError(reason));
    } finally {
      if (alive.current && request === requestNumber.current) {
        requestInFlight.current = false;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    void refresh();
    return () => {
      alive.current = false;
      requestNumber.current += 1;
      requestInFlight.current = false;
    };
  }, [refresh]);

  async function toggleAgent(agent: AgentDefinition) {
    if (requestInFlight.current || !agent.configurable || agent.required || agent.availability !== "available") return;
    requestInFlight.current = true;
    const request = ++requestNumber.current;
    setBusyAgent(agent.id);
    setError("");
    setNotice("");
    try {
      const updated = await setAgentEnabled(agent.id, !agent.enabled);
      if (!alive.current || request !== requestNumber.current) return;
      setCatalog((current) => current ? { ...current, agents: current.agents.map((item) => item.id === updated.id ? updated : item) } : current);
      setNotice(`已${updated.enabled ? "启用" : "停用"}“${updated.name}”，后续任务将按新设置执行。`);
    } catch (reason) {
      if (alive.current && request === requestNumber.current) setError(agentSettingsError(reason));
    } finally {
      if (alive.current && request === requestNumber.current) {
        requestInFlight.current = false;
        setBusyAgent(null);
      }
    }
  }

  const search = query.trim().toLocaleLowerCase();
  const agents = catalog?.agents ?? [];
  const filtered = agents.filter((agent) =>
    (group === "all" || agent.group === group) &&
    (!search || [agent.name, agent.description, agent.id, ...agent.capabilities, ...agent.used_in].join(" ").toLocaleLowerCase().includes(search))
  );
  const busy = loading || Boolean(busyAgent);

  return <div className={styles.management}>
    <header className={styles.header}>
      <h2>智能体管理</h2>
      <p>查看预设角色与协作流程，按需启用专项能力。</p>
    </header>

    <div className={styles.toolbar}>
      <div className={styles.search}>
        <Search size={16} aria-hidden="true" />
        <label htmlFor="agent-search" className="sr-only">搜索智能体</label>
        <input id="agent-search" type="search" placeholder="搜索名称或职责" value={query} onChange={(event) => setQuery(event.target.value)} autoComplete="off" />
        {query && <button type="button" onClick={() => setQuery("")} aria-label="清空搜索"><X size={14} /></button>}
      </div>
      <button type="button" onClick={() => void refresh()} disabled={busy} className={styles.iconButton} aria-label="刷新智能体列表" title="刷新智能体列表"><RefreshCw size={16} className={loading ? "animate-spin" : ""} /></button>
    </div>
    <div className={styles.filters} role="group" aria-label="智能体分类">
      <button type="button" aria-pressed={group === "all"} onClick={() => setGroup("all")}>全部</button>
      {groups.map((item) => <button key={item.id} type="button" aria-pressed={group === item.id} onClick={() => setGroup(item.id)}>{item.name}</button>)}
    </div>

    {error && <p role="alert" className={styles.error}>{error}{catalog && <span>当前仍显示上次读取的设置。</span>}</p>}
    {notice && <div role="status" className={styles.notice}><span>{notice}</span><button type="button" onClick={() => setNotice("")} className={styles.iconButton} aria-label="关闭智能体设置提示"><X size={15} /></button></div>}

    {loading && !catalog ? <p className={styles.empty} role="status"><LoaderCircle size={17} className="animate-spin" />正在读取智能体设置…</p> : catalog && <>
      {filtered.length === 0 ? <div className={styles.emptyState}>
        <p>{agents.length ? "没有找到符合条件的智能体。" : "暂时没有可管理的智能体。"}</p>
        {agents.length > 0 && <button type="button" onClick={() => { setQuery(""); setGroup("all"); }} className={styles.resetButton}>显示全部</button>}
      </div> : <div className={styles.groups}>
        {groups.map((section) => {
          const items = filtered.filter((agent) => agent.group === section.id);
          if (!items.length) return null;
          return <section key={section.id} className={styles.group} aria-labelledby={`agent-group-${section.id}`}>
            <h3 id={`agent-group-${section.id}`}>{section.name}<span>{items.length}</span></h3>
            <div className={styles.list}>{items.map((agent) => {
              const open = expanded === agent.id;
              const available = agent.availability === "available";
              const toggleable = available && agent.configurable && !agent.required;
              const detailsId = `agent-details-${agent.id}`;
              return <article key={agent.id} className={`${styles.agent} ${!available ? styles.unavailable : ""}`}>
                <div className={styles.row}>
                  <button type="button" className={styles.detailsButton} aria-expanded={open} aria-controls={detailsId} aria-label={`${agent.name}详情`} onClick={() => setExpanded(open ? null : agent.id)}>
                    <span className={styles.agentText}><strong>{agent.name}</strong><span title={agent.description}>{agent.description}</span></span>
                    <ChevronDown size={16} className={open ? styles.chevronOpen : styles.chevron} aria-hidden="true" />
                  </button>
                  <div className={styles.status}>
                    {!available ? <span className={styles.inactive}>未接入</span> : agent.required ? <span className={styles.required}><LockKeyhole size={12} aria-hidden="true" />系统必需</span> : toggleable ? <>
                      <span className={agent.enabled ? styles.enabled : styles.inactive}>{busyAgent === agent.id ? "保存中" : agent.enabled ? "已启用" : "已停用"}</span>
                      <button type="button" role="switch" aria-checked={agent.enabled} aria-label={`${agent.name}启用状态`} disabled={busy} onClick={() => void toggleAgent(agent)} className={styles.switch}>
                        <span>{busyAgent === agent.id && <LoaderCircle size={11} className="animate-spin" />}</span>
                      </button>
                    </> : <span className={styles.required}>由系统管理</span>}
                  </div>
                </div>
                <div id={detailsId} className={styles.details} hidden={!open}>
                  <dl>
                    <div><dt>职责</dt><dd>{agent.description}</dd></div>
                    <div><dt>运行方式</dt><dd>{implementations[agent.implementation] ?? "由系统管理"}</dd></div>
                    <div><dt>参与环节</dt><dd>{agent.used_in.length ? agent.used_in.join(" · ") : "尚未接入执行流程"}</dd></div>
                    <div><dt>可用能力</dt><dd>{agent.capabilities.length ? agent.capabilities.join(" · ") : "暂无"}</dd></div>
                  </dl>
                  {agent.note && <p className={styles.detailNote}>{agent.note}</p>}
                </div>
              </article>;
            })}</div>
          </section>;
        })}
      </div>}
      {agents.length > 0 && <p className={styles.footer}>设置会自动保存，并在后续任务中生效。系统必需的角色由应用统一管理。</p>}
    </>}
  </div>;
}
