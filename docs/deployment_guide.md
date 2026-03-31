# Multichain Deployment & Setup Guide

This guide describes how to deploy the USDT Escrow system onto your two local Hardhat nodes.

## 1. Network Configuration
Ensure your `hardhat.config.js` is set up to recognize both local RPC ports.

```javascript
// hardhat.config.js
module.exports = {
  solidity: "0.8.20",
  networks: {
    eth_chain: {
      url: "http://127.0.0.1:8545",
      accounts: ["0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"]
    },
    bnb_chain: {
      url: "http://127.0.0.1:8546",
      accounts: ["0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"]
    }
  }
};
```

---

## 2. Deployment Steps

### A. Deploy to ETH (Source)
You need to deploy the **Mock USDT** first, followed by the **EscrowSource**.

1.  **Terminal 1**: `npx hardhat node --port 8545`
2.  **Deployment**:
    ```bash
    npx hardhat run scripts/deploy_eth.js --network eth_chain
    ```
    *Ensure `EscrowSource` is initialized with the MockUSDT address on ETH.*

### B. Deploy to BNB (Mirror)
Similarly, deploy the **Mock USDT** on BNB (can be a separate deployment), followed by the **EscrowMirror**.

1.  **Terminal 2**: `npx hardhat node --port 8546`
2.  **Deployment**:
    ```bash
    npx hardhat run scripts/deploy_bnb.js --network bnb_chain
    ```
    *Ensure `EscrowMirror` is initialized with the MockUSDT address on BNB.*

---

## 3. Post-Deployment Linking

After deployment, update your **[`multichain_config.json`](file:///c:/Users/HP/Desktop/FYP/FYP-2.1 (multichain)/static/contract/multichain_config.json)**:

```json
{
  "USDT_ETH": "0x...",
  "ETH_SOURCE": "0x...",
  "USDT_BNB": "0x...",
  "BNB_MIRROR": "0x..."
}
```

> [!WARNING]
> Both the **Relayer (`relayer.py`)** and the **Dashboard (`script.js`)** rely on this config file. If the addresses are incorrect, your cross-chain messages will fail.

---

## 4. Final Verification
- **Test Funding**: Create an escrow on ETH. Watch the Python Relayer terminal for a "Synced to BNB" log.
- **Test Confirmation**: Switch to BNB in the UI. Confirm as User B. Watch the Relayer log "ETH Record Closed".
- **Balance Check**: Verify User B's balance on the BNB chain has increased by the escrow amount.

> [!TIP]
> **Mock Liquidity**: For the first run, the BNB Mirror contract will need USDT to payout User B. You can use the `mint` function in `MockUSDT` to send 100 USDT to the `EscrowMirror` contract address.
