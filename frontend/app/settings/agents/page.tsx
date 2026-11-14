import { AgentManagement } from "@/components/settings/agent-management";
import styles from "../settings.module.css";

export default function AgentSettingsPage() {
  return <section className={styles.content} aria-label="智能体管理"><AgentManagement /></section>;
}
