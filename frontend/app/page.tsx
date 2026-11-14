import { Navigate, useLocation } from "react-router-dom";

export default function WorkspaceEntryPage() {
  const { search, hash } = useLocation();
  return <Navigate to={{ pathname: "/workspace", search, hash }} replace />;
}
