"use client";

import { FormEvent, useEffect, useState } from "react";

type BankView = "home" | "accounts" | "payments" | "cards";

type Account = {
  name: string;
  number: string;
  balance: number;
  currency: string;
};

type Card = {
  network: string;
  product: string;
  pan: string;
  holder: string;
  expires: string;
  cvv: string;
  linked: string;
  available: number;
  currency: string;
};

type Beneficiary = {
  name: string;
  initials: string;
  account_number: string;
};

type Activity = {
  id: string;
  name: string;
  category: string;
  amount: number;
  date: string;
  icon: string;
};

type Overview = {
  customer_name: string;
  accounts: Account[];
  cards?: Card[];
  beneficiaries: Beneficiary[];
  activity: Activity[];
  notifications: number;
};

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const gateways = ["Gateway A", "Gateway B", "Gateway C", "Gateway D"] as const;
const navItems: { id: BankView; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "accounts", label: "Accounts" },
  { id: "payments", label: "Payments" },
  { id: "cards", label: "Cards" },
];

function errorMessage(result: { detail?: unknown }) {
  const detail = result.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === "object" && detail[0] !== null && "msg" in detail[0]) {
    return String((detail[0] as { msg: string }).msg);
  }
  return "Unable to send payment.";
}

export function BankPortal({
  email,
  headers,
  onSignOut,
}: {
  email: string;
  headers: Record<string, string>;
  onSignOut: () => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [view, setView] = useState<BankView>("home");
  const [recipient, setRecipient] = useState("Alex Morgan");
  const [accountNumber, setAccountNumber] = useState("88241903");
  const [amount, setAmount] = useState("25.00");
  const [gateway, setGateway] = useState<(typeof gateways)[number]>("Gateway A");
  const [notice, setNotice] = useState("");
  const [noticeKind, setNoticeKind] = useState<"ok" | "bad">("ok");

  async function load() {
    const response = await fetch(`${api}/api/customer/overview`, { headers });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(errorMessage(result));
    }
    setOverview(result);
  }

  useEffect(() => {
    load().catch((problem: Error) => {
      setNoticeKind("bad");
      setNotice(problem.message);
    });
    // Overview is loaded once the signed-in session headers are available.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [headers]);

  async function transfer(event: FormEvent) {
    event.preventDefault();
    const response = await fetch(`${api}/api/customer/transfers`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient,
        account_number: accountNumber,
        amount: Number(amount),
        gateway,
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setNoticeKind("bad");
      setNotice(errorMessage(result));
      return;
    }
    setOverview((current) =>
      current
        ? {
            ...current,
            accounts: result.accounts ?? current.accounts,
            cards: result.cards ?? current.cards,
            activity: result.activity ?? current.activity,
          }
        : result,
    );
    setNoticeKind(result.status === "success" ? "ok" : "bad");
    setNotice(String(result.receipt ?? "Payment processed."));
    setAmount("25.00");
  }

  function chooseBeneficiary(person: Beneficiary) {
    setRecipient(person.name);
    setAccountNumber(person.account_number.replaceAll("•", "").trim());
    setView("payments");
  }

  const cards = overview?.cards?.length
    ? overview.cards
    : [];

  return (
    <main className="bank-shell">
      <header className="bank-top">
        <button type="button" className="bank-brand" onClick={() => setView("home")}>
          <span>◒</span> union bank
        </button>
        <nav aria-label="Customer">
          {navItems.map((item) => (
            <button
              type="button"
              className={view === item.id ? "active" : ""}
              key={item.id}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div>
          <button type="button" className="bell">
            ● {overview?.notifications ?? 0}
          </button>
          <button type="button" className="profile" onClick={onSignOut} aria-label="Sign out">
            {email.slice(0, 1).toUpperCase()}
          </button>
        </div>
      </header>
      <section className="bank-content">
        {view === "home" && (
          <>
            <p className="eyebrow">GOOD MORNING</p>
            <h1>Hello, {overview?.customer_name ?? "there"}.</h1>
            <p className="bank-subtitle">Pay through Gateway A for the most reliable demo route.</p>
            <AccountGrid accounts={overview?.accounts} />
            <section className="bank-grid">
              <ActivityCard activity={overview?.activity} onViewAll={() => setView("payments")} />
              <TransferCard
                recipient={recipient}
                accountNumber={accountNumber}
                amount={amount}
                gateway={gateway}
                notice={notice}
                noticeKind={noticeKind}
                setRecipient={setRecipient}
                setAccountNumber={setAccountNumber}
                setAmount={setAmount}
                setGateway={setGateway}
                onSubmit={transfer}
              />
            </section>
            <BeneficiaryCard
              beneficiaries={overview?.beneficiaries}
              onManage={() => setView("payments")}
              onChoose={chooseBeneficiary}
            />
          </>
        )}
        {view === "accounts" && (
          <>
            <p className="eyebrow">YOUR ACCOUNTS</p>
            <h1>Balances, in one place.</h1>
            <p className="bank-subtitle">Everyday account is debited as soon as Gateway A approves a payment.</p>
            <AccountGrid accounts={overview?.accounts} />
            <section className="activity-card">
              <div className="section-title">
                <div>
                  <h2>Recent movements</h2>
                  <p>Activity across your accounts</p>
                </div>
              </div>
              <ActivityList activity={overview?.activity} />
            </section>
          </>
        )}
        {view === "payments" && (
          <>
            <p className="eyebrow">PAYMENTS</p>
            <h1>Send a card payment.</h1>
            <p className="bank-subtitle">
              Choose Gateway A, send $25, and watch the everyday balance drop immediately.
            </p>
            <section className="bank-grid">
              <ActivityCard activity={overview?.activity} />
              <TransferCard
                recipient={recipient}
                accountNumber={accountNumber}
                amount={amount}
                gateway={gateway}
                notice={notice}
                noticeKind={noticeKind}
                setRecipient={setRecipient}
                setAccountNumber={setAccountNumber}
                setAmount={setAmount}
                setGateway={setGateway}
                onSubmit={transfer}
              />
            </section>
            <BeneficiaryCard
              beneficiaries={overview?.beneficiaries}
              onChoose={chooseBeneficiary}
            />
          </>
        )}
        {view === "cards" && (
          <>
            <p className="eyebrow">CARDS</p>
            <h1>Your debit cards.</h1>
            <p className="bank-subtitle">
              These use official Visa/Mastercard test numbers. Available funds match the account
              balance after each payment.
            </p>
            <section className="card-grid">
              {cards.map((card) => (
                <article className={`plastic-card ${card.network.toLowerCase()}`} key={card.pan}>
                  <div className="plastic-top">
                    <i className="chip" aria-hidden="true" />
                    <span>{card.network} {card.product}</span>
                  </div>
                  <strong>{card.pan}</strong>
                  <div className="plastic-meta">
                    <p>
                      <small>Cardholder</small>
                      <b>{card.holder}</b>
                    </p>
                    <p>
                      <small>Valid thru</small>
                      <b>{card.expires}</b>
                    </p>
                    <p>
                      <small>CVV</small>
                      <b>{card.cvv}</b>
                    </p>
                  </div>
                  <em>
                    Available {card.currency}{" "}
                    {card.available.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </em>
                </article>
              ))}
            </section>
          </>
        )}
      </section>
    </main>
  );
}

function AccountGrid({ accounts }: { accounts: Account[] | undefined }) {
  return (
    <section className="account-grid">
      {accounts?.map((account, index) => (
        <article className={`account-card card-${index}`} key={`${account.number}-${account.balance}`}>
          <span>{account.name}</span>
          <strong>
            {account.currency}{" "}
            {account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </strong>
          <small>{account.number}</small>
        </article>
      ))}
    </section>
  );
}

function ActivityList({ activity }: { activity: Activity[] | undefined }) {
  return (
    <>
      {activity?.map((item) => (
        <div className="activity" key={item.id}>
          <i>{item.icon}</i>
          <div>
            <b>{item.name}</b>
            <span>
              {item.category} · {item.date}
            </span>
          </div>
          <strong className={item.amount < 0 ? "debit" : "credit"}>
            {item.amount < 0 ? "−" : item.amount > 0 ? "+" : ""}
            {item.amount === 0 ? "Declined" : `$${Math.abs(item.amount).toFixed(2)}`}
          </strong>
        </div>
      ))}
    </>
  );
}

function ActivityCard({
  activity,
  onViewAll,
}: {
  activity: Activity[] | undefined;
  onViewAll?: () => void;
}) {
  return (
    <article className="activity-card">
      <div className="section-title">
        <div>
          <h2>Recent activity</h2>
          <p>Latest account movements</p>
        </div>
        {onViewAll && (
          <button type="button" className="link-button" onClick={onViewAll}>
            View all
          </button>
        )}
      </div>
      <ActivityList activity={activity} />
    </article>
  );
}

function TransferCard({
  recipient,
  accountNumber,
  amount,
  gateway,
  notice,
  noticeKind,
  setRecipient,
  setAccountNumber,
  setAmount,
  setGateway,
  onSubmit,
}: {
  recipient: string;
  accountNumber: string;
  amount: string;
  gateway: (typeof gateways)[number];
  notice: string;
  noticeKind: "ok" | "bad";
  setRecipient: (value: string) => void;
  setAccountNumber: (value: string) => void;
  setAmount: (value: string) => void;
  setGateway: (value: (typeof gateways)[number]) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <article className="transfer-card">
      <p className="eyebrow">CARD PAYMENT</p>
      <h2>Send money</h2>
      <form onSubmit={onSubmit}>
        <label>
          Recipient
          <input
            value={recipient}
            onChange={(event) => setRecipient(event.target.value)}
            placeholder="Recipient name"
            required
          />
        </label>
        <label>
          Account number
          <input
            value={accountNumber}
            onChange={(event) => setAccountNumber(event.target.value)}
            placeholder="Account number"
            required
          />
        </label>
        <label>
          Amount (USD)
          <input
            type="number"
            step="0.01"
            min="1"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            placeholder="0.00"
            required
          />
        </label>
        <label>
          Payment gateway
          <select
            value={gateway}
            onChange={(event) => setGateway(event.target.value as (typeof gateways)[number])}
          >
            {gateways.map((item) => (
              <option key={item} value={item}>
                {item}
                {item === "Gateway A" ? " — recommended, always succeeds" : ""}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">Pay with Visa debit →</button>
      </form>
      {notice && <p className={noticeKind === "bad" ? "transfer-error" : "transfer-notice"}>{notice}</p>}
    </article>
  );
}

function BeneficiaryCard({
  beneficiaries,
  onManage,
  onChoose,
}: {
  beneficiaries: Beneficiary[] | undefined;
  onManage?: () => void;
  onChoose: (person: Beneficiary) => void;
}) {
  return (
    <section className="beneficiary-card">
      <div className="section-title">
        <div>
          <h2>Send again</h2>
          <p>Your saved people</p>
        </div>
        {onManage && (
          <button type="button" className="link-button" onClick={onManage}>
            Manage
          </button>
        )}
      </div>
      <div className="beneficiaries">
        {beneficiaries?.map((person) => (
          <button type="button" key={person.account_number} onClick={() => onChoose(person)}>
            <i>{person.initials}</i>
            <b>{person.name}</b>
            <span>{person.account_number}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
