# 🚀 Multichain Escrow Setup Guide

Follow these steps to run the full multichain USDT escrow environment locally. You will need **5 separate terminal windows** open.

---

### 1. Start Ethereum Node (ETH Chain)
In your first terminal, start the primary Hardhat node:
```powershell
npx hardhat node --port 8545
```
*Note: This will provide your test accounts and private keys.*

---

### 2. Start BNB Node (BNB Chain)
In your second terminal, start the second node simulating the BNB chain:
```powershell
npx hardhat node --port 8546
```

---

### 3. Deploy Smart Contracts
In a third terminal, run the deployment scripts for both chains. This will also update your `multichain_config.json` and ABIs automatically.

```powershell
# 1. Install dependencies
npm install

# 2. Compile contracts
npx hardhat compile

# 3. Deploy to ETH
npx hardhat run scripts/deploy_eth.js --network eth_chain

# 4. Deploy to BNB
npx hardhat run scripts/deploy_bnb.js --network bnb_chain
```

---

### 4. Start IPFS Daemon
In your fourth terminal, ensure your local IPFS node is running for file storage:
```powershell
ipfs daemon
```
*Ensure you have configured CORS for IPFS if you hit upload errors.*

---

### 5. Fund users and assign the admin role
python fund_users.py

### 6. Start Python Backend & Relayer
In your fifth terminal, start the Flask web server and the cross-chain relayer:

**Start the Flask App**:
```powershell
# Install python requirements if needed (Flask, SQLAlchemy, etc.)
pip install -r requirements.txt 
python app.py
```

**Start the Relayer (MUST be running to sync ETH -> BNB)**:
```powershell
# Open a new tab or terminal
python relayer.py
```

---

### 🌐 Accessing the DApp
Once everything is running, open your browser and navigate to:
**[http://127.0.0.1:5000](http://127.0.0.1:5000)**

### 💡 Testing Workflow
1.  **Select Wallet**: Use the dropdown to select a test account (e.g., Account 0).
2.  **Upload File**: Upload a receipt to IPFS on the "Create Escrow" page.
3.  **Create Multichain Escrow**: Select **USDT** and check **Multichain Bridge**.
4.  **Confirm on ETH**: As the Agent, switch to the ETH network and confirm.
5.  **Relayer Sync**: Watch the `relayer.py` terminal for the "Synced to BNB" message.
6.  **Confirm on BNB**: Switch the network toggle to **BNB**, select **User B's wallet**, and release the funds!
