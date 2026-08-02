# Customer Support Guide

This guide explains how to interpret the academic Payment Success Monitor
without making claims that the simulated data cannot support.

## Reading the dashboard

Use the Recent Transactions table to locate a transaction by transaction ID.
Before responding to a customer, record:

- Transaction status
- Simulated gateway
- Timestamp
- Transaction type and amount
- Device
- Latency
- Fraud flag

The displayed gateway and dashboard outcome are controlled synthetic academic
values. They are not evidence that a real bank processed the transaction.

## Failure interpretation

- High latency can indicate simulated network or gateway delay, but it does not
  prove the cause of a failure.
- `Fraud Flag = True` means the source record was flagged. It does not prove
  fraud or explain the transaction outcome by itself.
- Group failed deposits, withdrawals, and transfers by transaction type to find
  broad patterns.
- Compare device and latency-band breakdowns before describing a pattern.
- The source dataset does not contain explicit insufficient-balance, incorrect
  PIN, or incorrect OTP reasons. Do not claim any of these as the cause.

## Alert interpretation

An alert means the gateway's latest 50 active transactions are at least 10
percentage points below its success rate across the complete prepared dataset.

For example:

```text
Gateway baseline: 55%
Latest 50 rate:    43%
Drop:              12 percentage points
Result:            Alert
```

An alert is a demonstration signal, not evidence of a real bank outage. If the
dashboard shows `Insufficient history`, fewer than 50 active transactions exist
for that gateway.

Dashboard filters do not change alerts. This prevents a status filter such as
`Failed` from manufacturing a false gateway alert.

## Suggested response workflow

1. Find the transaction ID in Recent Transactions.
2. Record the status, timestamp, gateway, latency, device, transaction type, and
   fraud flag.
3. Check Gateway Health for an active alert or insufficient history.
4. Review failure charts for broader patterns.
5. Explain that the environment and gateway labels are simulated.
6. Escalate only as part of the classroom demonstration procedure.

## Safe example responses

### Failed transaction with no active alert

> The demonstration dashboard records this transaction as failed. There is no
> current gateway-level alert, and this dataset does not contain a definitive
> failure reason.

### Failed transaction during an active alert

> The demonstration dashboard shows that this simulated gateway's recent
> success rate is at least 10 percentage points below its baseline. This is an
> academic monitoring signal and does not confirm a real bank outage.

### Fraud-flagged transaction

> The source record is marked with a fraud flag. This indicates that it was
> flagged in the dataset, but it does not prove fraud or establish why the
> transaction succeeded or failed.

## Statements to avoid

Do not say:

- A real bank or gateway is down.
- The customer had insufficient balance.
- The customer entered an incorrect PIN or OTP.
- The transaction was fraudulent.
- The simulated alert is a production incident.

These conclusions are not supported by the source dataset or this academic MVP.
