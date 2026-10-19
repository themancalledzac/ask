# Data Warehouse & Metrics

Where the numbers come from when someone asks "how are we doing?"

- Product analytics → warehouse (nightly sync).
- Billing/usage → `ledger` exports daily.
- Growth dashboards pull from the warehouse, but a few are still hand-built in a
  spreadsheet that one person on Ops maintains.

If a dashboard and a spreadsheet disagree, nobody currently knows which is right.
This comes up more than you'd think.
