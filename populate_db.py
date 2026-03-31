from app import app
from database import db
from models import Escrow, AuditLog, User, AISummary
from datetime import datetime, timedelta

# Hardhat Accounts from User
ACCOUNTS = [
    "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266", # 0
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8", # 1
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC", # 2
    "0x90F79bf6EB2c4f870365E785982E1f101E93b906", # 3
    "0x15d34AAf54267DB7D7C367839AAf71A00a2C6A65", # 4
    "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc", # 5
    "0x976ea74026E726554dB657fa54763abd0c3a0aa9", # 6
    "0x14dC79964da2C08b23698B3D3cc7Ca32193d9955"  # 7
]

def populate():
    with app.app_context():
        print("Populating database...")
        
        # 1. Create Users
        users = [
            User(wallet_address=ACCOUNTS[0], name="Alice Alpha", email="alice@example.com"),
            User(wallet_address=ACCOUNTS[1], name="Bob Beta", email="bob@example.com"),
            User(wallet_address=ACCOUNTS[2], name="Charlie Agent", email="charlie@trusted-agent.com"),
            User(wallet_address=ACCOUNTS[3], name="David Delta", email="david@example.com"),
            User(wallet_address=ACCOUNTS[4], name="Eve Echo", email="eve@secret.com")
        ]
        for u in users:
            if not db.session.get(User, u.wallet_address):
                db.session.add(u)
        
        # 2. Create Sample Escrows
        escrows = [
            # Active Escrow
            Escrow(
                contract_address="0x1111111111111111111111111111111111111111",
                buyer_address=ACCOUNTS[0],
                seller_address=ACCOUNTS[1],
                agent_address=ACCOUNTS[2],
                amount_eth=2.5,
                ipfs_hash="QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
                status="Created"
            ),
            # Completed Escrow
            Escrow(
                contract_address="0x2222222222222222222222222222222222222222",
                buyer_address=ACCOUNTS[3],
                seller_address=ACCOUNTS[4],
                agent_address=ACCOUNTS[2],
                amount_eth=10.0,
                ipfs_hash="QmT78zSuB9fG82Z8EQu96aB1a8D9f1f1f1f1f1f1f1f1f",
                status="Released"
            ),
            # Dispute Escrow (Simulated)
            Escrow(
                contract_address="0x3333333333333333333333333333333333333333",
                buyer_address=ACCOUNTS[0],
                seller_address=ACCOUNTS[4],
                agent_address=ACCOUNTS[2],
                amount_eth=1.2,
                ipfs_hash="QmYwAP7iODf9uS7Ldf5ND7yv9tJ7L9yv9tJ7L9yv9tJ",
                status="Disputed"
            )
        ]
        db.session.add_all(escrows)
        db.session.flush() # Get IDs
        
        # 3. Create Audit Logs
        logs = [
            AuditLog(escrow_id=escrows[0].id, event_type="Creation", description="Escrow created for Development Services"),
            AuditLog(escrow_id=escrows[1].id, event_type="Creation", description="Escrow created for Luxury Watch"),
            AuditLog(escrow_id=escrows[1].id, event_type="Status Change", description="Funds released to seller after inspection"),
            AuditLog(escrow_id=escrows[2].id, event_type="Dispute", description="Buyer raised dispute: Item not as described")
        ]
        db.session.add_all(logs)
        
        # 4. Create AI Summary
        summary = AISummary(
            month=datetime.now().strftime("%Y-%m"),
            summary_text="""### Monthly Audit Executive Summary
- **Volume**: 13.7 ETH processed this month.
- **Activity**: 3 NEW contracts established.
- **Security**: 1 Dispute flagged for manual review; all other protocols verified.
- **Trust Score**: 98% successful resolution rate maintained.
            """
        )
        db.session.add(summary)
        
        db.session.commit()
        print("Database populated with sample data!")

if __name__ == "__main__":
    populate()
