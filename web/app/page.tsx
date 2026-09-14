"use client";

import { FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { BankPortal } from "./bank-portal";

type Role = "user" | "admin";
type View = "overview" | "transactions" | "gateways" | "routing" | "admin";
type RecordRow = Record<string, string | number | boolean | null>;
type Dashboard = {
  metrics: Record<string, number>;
  gateways: RecordRow[];
  trend: RecordRow[];
  alerts: RecordRow[];
  transactions: RecordRow[];
  total_transactions: number;
  source: string;
  simulation_version: string;
};
type AuditEvent = { action: string; transaction_id: string; actor: string; changed_at: string };

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const gatewayOptions = ["Gateway A", "Gateway B", "Gateway C", "Gateway D"];

function label(key: string) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function value(input: unknown) {
  return typeof input === "number"
    ? input.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : String(input ?? "—");
}

function metricValue(key: string, input: unknown) {
  if (key.includes("rate")) return `${(Number(input ?? 0) * 100).toFixed(1)}%`;
  return value(input);
}

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<Role | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [data, setData] = useState<Dashboard | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [gateway, setGateway] = useState("");
  const [page, setPage] = useState(1);
  const [view, setView] = useState<View>("overview");

  const headers = useMemo<Record<string, string>>(
    () => (token ? { Authorization: `Bearer ${token}` } : {} as Record<string, string>),
    [token],
  );

  async function loadDashboard() {
    if (!token) return;
    const query = new URLSearchParams({ page: String(page), page_size: "12" });
    if (gateway) query.set("gateways", gateway);
    const response = await fetch(`${api}/api/dashboard?${query}`, { headers });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? "Unable to load dashboard");
    setData(result);
  }

  async function loadAudit() {
    if (role !== "admin") return;
    const response = await fetch(`${api}/api/admin/audit`, { headers });
    const result = await response.json();
    if (response.ok) setAudit(result);
  }

  useEffect(() => {
    const savedToken = window.sessionStorage.getItem("payment-token");
    const savedRole = window.sessionStorage.getItem("payment-role") as Role | null;
    const savedEmail = window.sessionStorage.getItem("payment-email");
    if (savedToken && savedRole) {
      setToken(savedToken);
      setRole(savedRole);
      setEmail(savedEmail ?? "");
    }
  }, []);

  useEffect(() => {
    loadDashboard().catch((problem: Error) => setError(problem.message));
    // Loading depends on an authenticated session and query state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, gateway, page]);

  useEffect(() => {
    if (view === "admin") loadAudit().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, role, token]);

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setError("");
    const response = await fetch(`${api}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.detail ?? "Unable to sign in");
      return;
    }
    window.sessionStorage.setItem("payment-token", result.access_token);
    window.sessionStorage.setItem("payment-role", result.role);
    window.sessionStorage.setItem("payment-email", email);
    setToken(result.access_token);
    setRole(result.role);
    setPassword("");
  }

  function signOut() {
    window.sessionStorage.clear();
    setToken(null);
    setRole(null);
    setData(null);
    setAudit([]);
    setView("overview");
  }

  async function deleteTransaction(transactionId: string) {
    if (!window.confirm(`Delete ${transactionId}? This action is recorded in the audit log.`)) return;
    const response = await fetch(`${api}/api/admin/transactions/${encodeURIComponent(transactionId)}`, {
      method: "DELETE",
      headers,
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.detail ?? "Unable to delete transaction");
      return;
    }
    setMessage(`${transactionId} deleted.`);
    await Promise.all([loadDashboard(), loadAudit()]);
  }

  async function updateTransaction(transactionId: string, currentStatus: unknown) {
    const status = window.prompt("New status: Success or Failed", String(currentStatus));
    if (!status || !["Success", "Failed"].includes(status)) {
      setError("Update cancelled. Status must be Success or Failed.");
      return;
    }
    const response = await fetch(`${api}/api/admin/transactions/${encodeURIComponent(transactionId)}`, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ values: { "Transaction Status": status } }),
    });
    const result = await response.json();
    if (!response.ok) {
      setError(result.detail ?? "Unable to update transaction");
      return;
    }
    setMessage(`${transactionId} updated to ${status}.`);
    await Promise.all([loadDashboard(), loadAudit()]);
  }

  async function resetDemo() {
    const response = await fetch(`${api}/api/admin/demo/reset`, { method: "POST", headers });
    const result = await response.json();
    if (!response.ok) {
      setError(result.detail ?? "Unable to reset demo data");
      return;
    }
    setMessage("Demo data reset successfully.");
    await Promise.all([loadDashboard(), loadAudit()]);
  }

  if (!token || !role) {
    return <main className="login-shell"><section className="hero"><p className="eyebrow">FLOWLINE / PAYMENTS</p><h1>Every payment decision, clear at a glance.</h1><p>Monitor synthetic payment performance, identify reliability issues, and act on routing intelligence.</p><div className="orb orb-one" /><div className="orb orb-two" /></section><section className="login-card"><div><p className="eyebrow">SECURE ACCESS</p><h2>Welcome back</h2><p className="muted">Customer access validates against the MongoDB customer directory.</p></div><form onSubmit={signIn}><label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" required /></label><label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" required /></label>{error && <p className="error">{error}</p>}<button>Sign in <span>→</span></button></form><p className="demo-note">Use a customer account issued from MongoDB.<br />Admin: admin@payments.local / demo-admin</p></section></main>;
  }

  const columns = data?.transactions[0] ? Object.keys(data.transactions[0]).slice(0, 7) : [];
  const admin = role === "admin";
  if (!admin) {
    return <BankPortal email={email} headers={headers} onSignOut={signOut} />;
  }
  const title = view === "admin" ? "Governance, under control." : view === "gateways" ? "Gateway performance, compared." : view === "routing" ? "Routing intelligence, explained." : view === "transactions" ? "Transactions, searchable." : "Payment health, in focus.";

  const metrics = <section className="metrics">{Object.entries(data?.metrics ?? {}).slice(0, 4).map(([key, item], index) => <article className={`metric metric-${index}`} key={key}><p>{label(key)}</p><strong>{metricValue(key, item)}</strong><span>{index === 0 ? "Updated just now" : "Current period"}</span></article>)}</section>;
  const workspace = view === "admin" ? <AdminConsole source={data?.source ?? "demo"} audit={audit} onReset={resetDemo} onManageTransactions={() => setView("transactions")} />
    : view === "overview" ? <OverviewPanel data={data} metrics={metrics} />
      : view === "transactions" ? <TransactionsPanel columns={columns} data={data} page={page} setPage={setPage} onDelete={deleteTransaction} onUpdate={updateTransaction} gateway={gateway} setGateway={setGateway} />
        : view === "gateways" ? <GatewayPerformancePanel data={data} metrics={metrics} gateway={gateway} setGateway={setGateway} />
          : <>{metrics}<RoutingPanel data={data} /></>;

  return <main className="app-shell"><aside><div className="brand"><span>F</span> flowline</div><nav>{(["overview", "transactions", "gateways", "routing"] as View[]).map((item) => <button className={view === item ? "active" : ""} key={item} onClick={() => setView(item)}>{({ overview: "⌘ Overview", transactions: "◌ Transactions", gateways: "◈ Gateways", routing: "↗ Routing lab" } as Record<string, string>)[item]}</button>)}<button className={view === "admin" ? "active" : ""} onClick={() => setView("admin")}>⚙ Admin console</button></nav><div className="account"><div className="avatar">{email.slice(0, 1).toUpperCase()}</div><div><strong>{email || "Operations"}</strong><small>Administrator</small></div><button className="icon-button" onClick={signOut} aria-label="Sign out">↪</button></div></aside><section className="content"><header><div><p className="eyebrow">{view === "admin" ? "ADMINISTRATOR WORKSPACE" : "OPERATIONS CENTER"}</p><h1>{title.split(", ")[0]}, <em>{title.split(", ")[1]}</em></h1></div><div className="source"><i /> {data?.source === "live" ? "Live data" : "Demo data"}</div></header>{error && <p className="error">{error}</p>}{message && <p className="success-message">{message}</p>}{workspace}</section></main>;
}

function OverviewPanel({ data, metrics }: { data: Dashboard | null; metrics: ReactNode }) {
  const latest = data?.trend.slice(-12).reverse() ?? [];
  return <>{metrics}<section className="overview-grid"><article className="trend-card"><div className="section-title"><div><h2>Payment trend</h2><p>Latest 12 fifteen-minute windows</p></div><b>{data?.total_transactions.toLocaleString() ?? "0"} total</b></div><div className="trend-bars">{latest.map((row) => <div key={String(row.Timestamp)}><i style={{ height: `${Math.max(8, Number(row.success_rate ?? 0) * 100)}%` }} /><span>{(Number(row.success_rate ?? 0) * 100).toFixed(0)}%</span></div>)}</div></article><GatewayCards data={data} /></section></>;
}

function TransactionsPanel({ columns, data, page, setPage, onDelete, onUpdate, gateway, setGateway }: { columns: string[]; data: Dashboard | null; page: number; setPage: (page: number) => void; onDelete: (transactionId: string) => void; onUpdate: (transactionId: string, status: unknown) => void; gateway: string; setGateway: (value: string) => void }) {
  return <><section className="workspace-head"><div><p className="eyebrow">RECORD MANAGEMENT</p><h2>Transaction ledger</h2><p className="muted">Update status or delete records. Every change creates an audit entry.</p></div><label className="select-label">Gateway<select value={gateway} onChange={(event) => { setGateway(event.target.value); setPage(1); }}><option value="">All gateways</option>{gatewayOptions.map((item) => <option key={item}>{item}</option>)}</select></label></section><TransactionTable columns={columns} data={data} page={page} setPage={setPage} canDelete onDelete={onDelete} canEdit onUpdate={onUpdate} /></>;
}

function GatewayPerformancePanel({ data, metrics, gateway, setGateway }: { data: Dashboard | null; metrics: ReactNode; gateway: string; setGateway: (value: string) => void }) {
  return <>{metrics}<section className="workspace-head"><div><p className="eyebrow">RELIABILITY ANALYTICS</p><h2>Gateway performance</h2><p className="muted">Compare volume, success rate, and latency by processor.</p></div><label className="select-label">Focus gateway<select value={gateway} onChange={(event) => setGateway(event.target.value)}><option value="">All gateways</option>{gatewayOptions.map((item) => <option key={item}>{item}</option>)}</select></label></section><section className="gateway-grid">{data?.gateways.map((row) => <article className="gateway-stat" key={String(row["Bank Gateway"])}><p>{String(row["Bank Gateway"])}</p><strong>{(Number(row.success_rate ?? 0) * 100).toFixed(1)}%</strong><span>Success rate</span><dl><div><dt>Volume</dt><dd>{value(row.transaction_count)}</dd></div><div><dt>Latency</dt><dd>{value(row.average_latency_ms)} ms</dd></div></dl></article>)}</section></>;
}

function TransactionTable({ columns, data, page, setPage, canDelete, onDelete, canEdit = false, onUpdate }: { columns: string[]; data: Dashboard | null; page: number; setPage: (page: number) => void; canDelete: boolean; onDelete: (transactionId: string) => void; canEdit?: boolean; onUpdate?: (transactionId: string, status: unknown) => void }) {
  return <section className="table-card"><div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}{(canDelete || canEdit) && <th>Actions</th>}</tr></thead><tbody>{data?.transactions.map((row, index) => <tr key={`${row["Transaction ID"]}-${index}`}>{columns.map((column) => <td key={column} className={column === "Transaction Status" ? String(row[column]).toLowerCase() : ""}>{value(row[column])}</td>)}{(canDelete || canEdit) && <td className="row-actions">{canEdit && <button className="edit" onClick={() => onUpdate?.(String(row["Transaction ID"]), row["Transaction Status"])}>Update</button>}{canDelete && <button className="delete" onClick={() => onDelete(String(row["Transaction ID"]))}>Delete</button>}</td>}</tr>)}</tbody></table></div><footer><span>{data?.total_transactions.toLocaleString()} matching transactions</span><div><button className="pager" disabled={page === 1} onClick={() => setPage(page - 1)}>←</button><span>Page {page}</span><button className="pager" disabled={(data?.transactions.length ?? 0) < 12} onClick={() => setPage(page + 1)}>→</button></div></footer></section>;
}

function GatewayCards({ data }: { data: Dashboard | null }) {
  return <section className="lower-grid"><article className="gateway-card"><div><h2>Gateway scorecard</h2><span>Success rate and volume</span></div>{data?.gateways.slice(0, 4).map((row, index) => <div className="gateway-row" key={String(row["Bank Gateway"])}><b>{row["Bank Gateway"]}</b><div className="bar"><i style={{ width: `${Math.min(Number(row.success_rate ?? 0) * 100, 100)}%`, background: ["#8b5cf6", "#22c55e", "#f59e0b", "#38bdf8"][index] }} /></div><strong>{(Number(row.success_rate ?? 0) * 100).toFixed(1)}%</strong></div>)}</article><article className="notice"><p className="eyebrow">DATA GOVERNANCE</p><h2>Academic simulation</h2><p>Gateway outcomes and routing recommendations are controlled synthetic results, not real bank performance.</p><small>{data?.simulation_version}</small></article></section>;
}

function RoutingPanel({ data }: { data: Dashboard | null }) {
  const best = [...(data?.gateways ?? [])].sort((left, right) => Number(right.success_rate ?? 0) - Number(left.success_rate ?? 0))[0];
  return <section className="routing-panel"><p className="eyebrow">ROUTING LAB</p><h2>Choose payment route with confidence</h2><p>This screen compares gateway reliability. Start with highest success rate, then verify latency and transaction volume before routing more traffic.</p><div className="routing-grid"><span>Recommended gateway <b>{best ? String(best["Bank Gateway"]) : "No data"}</b></span><span>Why it leads <b>{best ? `${(Number(best.success_rate ?? 0) * 100).toFixed(1)}% success` : "—"}</b></span><span>Data source <b>{data?.source === "live" ? "Live MongoDB" : "Demo data"}</b></span></div><ol className="routing-steps"><li>Compare success rate. Higher means fewer failed payments.</li><li>Check latency. Lower means faster payment completion.</li><li>Move traffic gradually. Watch results before changing more routes.</li></ol></section>;
}

function AdminConsole({ source, audit, onReset, onManageTransactions }: { source: string; audit: AuditEvent[]; onReset: () => void; onManageTransactions: () => void }) {
  return <><section className="admin-card"><p className="eyebrow">ROLE-PROTECTED CONTROLS</p><h2>Administrator workspace</h2><p>Manage transaction records here. Update status or delete a record in Transaction ledger. Every action is audited.</p><div className="admin-status"><span>Audit logging</span><b>Enabled</b><span>Data changes</span><b>{source === "live" ? "MongoDB connected" : "Demo enabled"}</b></div><div className="admin-actions"><button onClick={onManageTransactions}>Update transaction</button><button className="danger-action" onClick={onManageTransactions}>Delete transaction</button></div>{source === "demo" && <button onClick={onReset}>Reset demo data</button>}</section><section className="audit-card"><div><h2>Recent audit activity</h2><span>Latest protected changes</span></div>{audit.length ? <ul>{audit.map((event) => <li key={`${event.changed_at}-${event.transaction_id}`}><b>{event.action}</b><span>{event.transaction_id}</span><small>{event.actor} · {new Date(event.changed_at).toLocaleString()}</small></li>)}</ul> : <p className="muted">No changes recorded yet. Use Transaction ledger to update or delete a record.</p>}</section></>;
}
