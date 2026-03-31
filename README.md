# DBlock Escrow System | Web3 & AI-Powered

A professional, multimodal Web3 Escrow application featuring automated AI auditing and real-time email notifications.

## 🚀 Key Features
- **Smart Contract Escrow**: Secure, multi-signature style flow (Buyer, Seller, Agent).
- **Groq AI Auditing**: Automated "Monthly Executive Audits" based on live transaction statistics.
- **Vision AI Receipt Processing**: Dynamic analysis of IPFS-hosted receipts (vision-led).
- **Email Notifications**: Real-time SMTP alerts for all contract participants.
- **Named User Profiles**: Custom human-readable associations for Ethereum wallet addresses.

## 🛠️ Setup & Installation

### 1. Prerequisites
- **Python 3.10+**
- **Hardhat** (or your preferred local Ethereum node)
- **Groq API Key** (for AI features)
- **Local IPFS Node** (optional, for vision processing)

### 2. Install Dependencies
```bash
pip install flask flask-sqlalchemy flask-cors requests python-dotenv
```

### 2.1 Install Hardhat
```bash
npx hardhat
```

### 2.2 Install IPFS
```bash
npm install -g ipfs
```

### 3. Environment Configuration (`.env`)
Create a `.env` file in the root directory:
```text
GROQ_API_KEY=your_groq_key
SMTP_EMAIL=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

### 4. Database Setup
The application uses SQLite (`instance/fyp.db`). Use the utility scripts for management:
- **Clean Slate**: `python clear_db.py` (Resets everything).
- **Sample Data**: `python populate_db.py` (Seeds Hardhat accounts with names and history).

## 🖥️ Running the Application
1. **Start Hardhat Node**: `npx hardhat node`
2. **IPFS**: `ipfs daemon`
3. **Start Flask Server**: `python app.py`
4. **Open Dashboard**: Visit `http://127.0.0.1:5000`

## 📂 Project Structure
- `app.py`: Main Flask application core.
- `models.py`: Database schema for Users, Escrows, and Audits.
- `static/`: Frontend assets (script.js, styling).
- `templates/`: HTML structures (layout, dashboard, notifications).
- `clear_db.py` / `populate_db.py`: Internal database management.

---
*Created as part of the DBlock FYP Research Project.*
