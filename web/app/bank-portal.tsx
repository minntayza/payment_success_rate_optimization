"use client";

import { FormEvent, useEffect, useState } from "react";

type BankView = "home" | "accounts" | "payments" | "cards";

type Account = {
  name: string;
  number: string;
  balance: number;
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
  beneficiaries: Beneficiary[];
  activity: Activity[];
  notifications: number;
};

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const navItems: { id: BankView; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "accounts", label: "Accounts" },
  { id: "payments", label: "Payments" },
  { id: "cards", label: "Cards" },
];

function lastFour(number: string) {
  const digits = number.replace(/\D/g, "");
  return (digits || number).slice(-4);
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
  const [recipient, setRecipient] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [amount, setAmount] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    const response = await fetch(`${api}/api/customer/overview`, { headers });
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.detail ?? "Unable to load your account.");
    }
    setOverview(result);
  }

  useEffect(() => {
    load().catch((problem: Error) => setNotice(problem.message));
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
      }),
    });
    const result = await response.json();
    if (!response.ok) {
      setNotice(result.detail);
      return;
    }
    setNotice(`Transfer scheduled. Reference: ${String(result.reference).slice(0, 8)}`);
    setRecipient("");
    setAccountNumber("");
    setAmount("");
    await load();
  }

  function chooseBeneficiary(person: Beneficiary) {
    setRecipient(person.name);
    setAccountNumber(person.account_number.replace("•••• ", ""));
    setView("payments");
  }

  const cards =
    overview?.accounts.map((account, index) => ({
      label: index === 0 ? "Everyday debit" : "Savings card",
      network: index === 0 ? "Visa" : "Mastercard",
      holder: overview.customer_name,
      last4: lastFour(account.number),
      linked: account.name,
      expires: "09/28",
    })) ?? [];

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
              onClick={() => {
                setNotice("");
                setView(item.id);
              }}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div>
          <button
            type="button"
            className="bell"
            onClick={() =>
              setNotice(
                overview
                  ? `You have ${overview.notifications} notification${overview.notifications === 1 ? "" : "s"}.`
                  : "Notifications will appear after your account loads.",
              )
            }
          >
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
            <p className="bank-subtitle">Here is your financial snapshot for today.</p>
            <AccountGrid
              accounts={overview?.accounts}
              onOpenAccount={() => {
                setNotice("This academic demo cannot open a live bank account.");
                setView("accounts");
              }}
            />
            <section className="bank-grid">
              <ActivityCard
                activity={overview?.activity}
                onViewAll={() => setView("payments")}
              />
              <TransferCard
                recipient={recipient}
                accountNumber={accountNumber}
                amount={amount}
                notice={notice}
                setRecipient={setRecipient}
                setAccountNumber={setAccountNumber}
                setAmount={setAmount}
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
            <p className="bank-subtitle">
              Everyday and savings accounts from your MongoDB customer profile.
            </p>
            <AccountGrid
              accounts={overview?.accounts}
              onOpenAccount={() =>
                setNotice("This academic demo cannot open a live bank account.")
              }
            />
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
            <h1>Send and review transfers.</h1>
            <p className="bank-subtitle">
              Simulated transfers update the signed-in customer balance and activity feed.
            </p>
            <section className="bank-grid">
              <ActivityCard activity={overview?.activity} />
              <TransferCard
                recipient={recipient}
                accountNumber={accountNumber}
                amount={amount}
                notice={notice}
                setRecipient={setRecipient}
                setAccountNumber={setAccountNumber}
                setAmount={setAmount}
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
            <h1>Cards linked to your accounts.</h1>
            <p className="bank-subtitle">
              These are synthetic demo cards derived from your account numbers, not real
              payment cards.
            </p>
            <section className="card-grid">
              {cards.map((card) => (
                <article className="virtual-card" key={card.last4}>
                  <span>{card.network}</span>
                  <strong>•••• {card.last4}</strong>
                  <small>{card.label}</small>
                  <p>
                    {card.holder}
                    <b>Exp {card.expires}</b>
                  </p>
                  <em>Linked to {card.linked}</em>
                </article>
              ))}
            </section>
          </>
        )}
        {notice && view !== "home" && view !== "payments" && (
          <p className="transfer-notice">{notice}</p>
        )}
      </section>
    </main>
  );
}

function AccountGrid({
  accounts,
  onOpenAccount,
}: {
  accounts: Account[] | undefined;
  onOpenAccount: () => void;
}) {
  return (
    <section className="account-grid">
      {accounts?.map((account, index) => (
        <article className={`account-card card-${index}`} key={account.number}>
          <span>{account.name}</span>
          <strong>
            {account.currency}{" "}
            {account.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </strong>
          <small>{account.number}</small>
        </article>
      ))}
      <button type="button" className="new-account" onClick={onOpenAccount}>
        ＋
        <br />
        <span>Open an account</span>
      </button>
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
            {item.amount < 0 ? "−" : "+"}${Math.abs(item.amount).toFixed(2)}
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
  notice,
  setRecipient,
  setAccountNumber,
  setAmount,
  onSubmit,
}: {
  recipient: string;
  accountNumber: string;
  amount: string;
  notice: string;
  setRecipient: (value: string) => void;
  setAccountNumber: (value: string) => void;
  setAmount: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <article className="transfer-card">
      <p className="eyebrow">QUICK TRANSFER</p>
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
        <button type="submit">Continue transfer →</button>
      </form>
      {notice && <p className="transfer-notice">{notice}</p>}
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
