# BlockTrade AI — Full Working Demo

A runnable full-stack hackathon prototype with login/register, dashboard, token swap simulation, lending demo, reputation page, transaction history, profile, settings, and a privacy-conscious PAN verification *simulation*.

## Requirements
- Python 3.10+
- Internet is not required after dependencies are installed.

## Run on Windows
1. Extract the ZIP.
2. Open the extracted `BlockTradeAI_Full_Project` folder in VS Code.
3. Open Terminal in that folder and run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

4. Open http://127.0.0.1:8000

## Run on macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Included pages
- `/login` — sign in
- `/register` — create an account
- `/` — dashboard (requires login)
- `/swap` — simulated token swap and transaction record
- `/lending` — demo collateral/borrow/repay actions
- `/reputation` — illustrative demo score
- `/transactions` — transaction history
- `/profile` — account profile and PAN verification demo
- `/settings` — account settings

## Demo login
Create your own account from `/register`. No preloaded password is provided.

## PAN verification safety
The PAN flow is **mock verification only**. Use a dummy test value such as `ABCDE1234F`; do not submit a real PAN. The app validates the format, then returns a clearly labelled simulated result. It does not call an authorized PAN verification service, and it does not store the PAN value. Real PAN verification requires a compliant, authorized provider and appropriate consent, privacy notices, access controls, and data-retention policies. Never store full PAN/Aadhaar numbers, OTPs, or identity documents on-chain.

## Blockchain status
Swaps, lending and transaction IDs are locally simulated in SQLite. This demo does not connect MetaMask, deploy Solidity contracts, or move real funds. All prices and balances are illustrative. Do not use real funds or real identity data.
