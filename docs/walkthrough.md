# Multichain USDT Escrow Walkthrough & Execution Guide

We have successfully transformed the single-chain escrow system into a multichain USDT bridge dApp. Below is the guide on how to set up, deploy, and execute the cross-chain flow.

## 🚀 Execution Guide

### 1. Environment Setup
You need to run two separate Hardhat nodes to simulate the ETH and BNB chains.

**Terminal 1 (ETH - Port 8545)**:
```bash
npx hardhat node --port 8545
```

**Terminal 2 (BNB - Port 8546)**:
```bash
npx hardhat node --port 8546
```

---

### 2. Smart Contract Deployment
1. **Deploy USDT & Escrow on ETH**:
   - Deploy `MockUSDT.sol` to Port 8545.
   - Deploy `EscrowSource.sol` to Port 8545 (passing the USDT address).
2. **Deploy USDT & Escrow on BNB**:
   - Deploy `MockUSDT.sol` to Port 8546.
   - Deploy `EscrowMirror.sol` to Port 8546 (passing the local USDT address).

> [!TIP]
> After deployment, update the manual addresses in `static/script.js`:
> ```javascript
> let USDT_ETH = "0x..."; 
> let ESCROW_SOURCE = "0x...";
> let USDT_BNB = "0x...";
> let ESCROW_MIRROR = "0x...";
> ```

---

### 3. Start the Relayer
In a new terminal, start the Python relayer to bridge the chains:
```bash
python relayer.py
```
*Ensure you have `web3.py` installed: `pip install web3`*

---

### 4. Running the DApp
1. Start the Flask backend: `python app.py`.
2. Open the dashboard in your browser.
3. **The Workflow**:
   - **Step 1 (ETH)**: Select the **ETH Network** in the top bar. Go to "Create Contract".
   - **Step 2 (Funding)**: Select **USDT** and check **Enable Multichain Bridge**. Click "Create Escrow".
     - This will trigger a USDT `approve` and then the `createEscrow` on ETH.
   - **Step 3 (Relay)**: Watch the `relayer.py` logs. It will detect the ETH funding and initialize the mirror on BNB.
   - **Step 4 (Confirmation)**: Switch the network to **BNB** in the top bar.
   - **Step 5 (User B)**: As User B (Receiver), click "Confirm Receiver" on the BNB side.
   - **Step 6 (Release)**: The BNB contract will release USDT to User B on the BNB chain. The Relayer will then notify the ETH side to close the record.

---

## 🛠️ Changes Implemented

### Smart Contracts
- **[MockUSDT](file:///c:/Users/HP/Desktop/FYP/FYP-2.1%20(multichain)/static/contract/MockUSDT.sol)**: Standard ERC20 for local testing.
- **[EscrowSource](file:///c:/Users/HP/Desktop/FYP/FYP-2.1%20(multichain)/static/contract/EscrowSource.sol)**: ETH-side logic for locking USDT.
- **[EscrowMirror](file:///c:/Users/HP/Desktop/FYP/FYP-2.1%20(multichain)/static/contract/EscrowMirror.sol)**: BNB-side logic for cross-chain confirmation and release.

### Infrastructure
- **[Relayer](file:///c:/Users/HP/Desktop/FYP/FYP-2.1%20(multichain)/relayer.py)**: A Python script using event listeners to bridge state between 8545 and 8546.
- **Network Switcher**: New UI component in `layout.html` to toggle between chain views.

### Backend & Database
- Updated **[models.py](file:///c:/Users/HP/Desktop/FYP/FYP-2.1%20(multichain)/models.py)** with `is_multichain`, `source_chain_id`, and `dest_chain_id` fields.
- Refactored **[app.py](file:///c:/Users/HP/Desktop/FYP/FYP-2.1%20(multichain)/app.py)** APIs to track multichain metadata.

> [!IMPORTANT]
> Since this is a local development environment, make sure to **provide liquidity** to the `EscrowMirror` on BNB (send it some MockUSDT) so it has funds to payout the receiver!
