from app import app
from database import db
from models import Order, AuditLog, User, AISummary, OrderDocument
from datetime import datetime, timedelta

# Hardhat Accounts from standard list (Lowercased for DB consistency)
ACCOUNTS = [
    "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266".lower(), # 0: Buyer
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8".lower(), # 1: Buyer
    "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC".lower(), # 2: Seller
    "0x90F79bf6EB2c4f870365E785982E1f101E93b906".lower(), # 3: Seller
    "0x15d34AAf54267DB7D7C367839AAf71A00a2C6A65".lower(), # 4: Agent
    "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc".lower(), # 5: Agent
    "0x976ea74026E726554dB657fa54763abd0c3a0aa9".lower(), # 6: Admin
]

def populate():
    with app.app_context():
        print("Populating database...")
        
        # 1. Create Users
        users = [
            User(wallet_address=ACCOUNTS[1], name="GlobalRetail Inc.", email="retail@example.com", role="buyer"),
            User(wallet_address=ACCOUNTS[2], name="MegaSupply Ltd.", email="megasupply@trusted-agent.com", role="seller"),
            User(wallet_address=ACCOUNTS[3], name="PrimeGoods Co.", email="prime@example.com", role="seller"),
            User(wallet_address=ACCOUNTS[4], name="FastTrack Logistics", email="fasttrack@secret.com", role="agent"),
            User(wallet_address=ACCOUNTS[5], name="Port Authority Customs", email="customs@port.gov", role="agent"),
            User(wallet_address=ACCOUNTS[0], name="System Admin", email="admin@chaintrack.com", role="admin")
        ]
        for u in users:
            if not db.session.get(User, u.wallet_address):
                db.session.add(u)
        
        # 2. Create Sample Orders
        orders = [
            # Active Order (Shipped)
            Order(
                contract_address="0x1111111111111111111111111111111111111111",
                order_id_onchain=0,
                buyer_address=ACCOUNTS[0],
                seller_address=ACCOUNTS[2],
                agent_address=ACCOUNTS[4],
                product_description="100x Industrial Sensors",
                amount=2.5,
                token_symbol="ETH",
                is_multichain=False,
                status="Shipped"
            ),
            # Completed Order
            Order(
                contract_address="0x2222222222222222222222222222222222222222",
                order_id_onchain=1,
                buyer_address=ACCOUNTS[1],
                seller_address=ACCOUNTS[3],
                agent_address=ACCOUNTS[5],
                product_description="Luxury Watches Batch",
                amount=10.0,
                token_symbol="ETH",
                is_multichain=True,
                status="Completed"
            ),
            # Disputed Order
            Order(
                contract_address="0x3333333333333333333333333333333333333333",
                order_id_onchain=2,
                buyer_address=ACCOUNTS[0],
                seller_address=ACCOUNTS[3],
                agent_address=ACCOUNTS[4],
                product_description="Faulty PCB Boards",
                amount=1.2,
                token_symbol="USDT",
                is_multichain=True,
                status="Disputed"
            )
        ]
        db.session.add_all(orders)
        db.session.flush() # Get IDs
        
        # 3. Create Order Documents
        docs = [
            OrderDocument(order_id=orders[0].id, stage="Created", ipfs_hash="QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco", doc_type="receipt", uploaded_by=ACCOUNTS[0]),
            OrderDocument(order_id=orders[0].id, stage="Shipped", ipfs_hash="QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDD", doc_type="photo", uploaded_by=ACCOUNTS[2]),
            OrderDocument(order_id=orders[1].id, stage="Created", ipfs_hash="QmT78zSuB9fG82Z8EQu96aB1a8D9f1f1f1f1f1f1f1f1f", doc_type="receipt", uploaded_by=ACCOUNTS[1]),
            OrderDocument(order_id=orders[2].id, stage="Created", ipfs_hash="QmYwAP7iODf9uS7Ldf5ND7yv9tJ7L9yv9tJ7L9yv9tJ", doc_type="receipt", uploaded_by=ACCOUNTS[0]),
            OrderDocument(order_id=orders[2].id, stage="Disputed", ipfs_hash="QmYwAP7iODf9uS7Ldf5ND7yv9tJ7L9yv9tJ7L", doc_type="photo", uploaded_by=ACCOUNTS[0])
        ]
        db.session.add_all(docs)

        # 4. Create Audit Logs
        logs = [
            AuditLog(order_id=orders[0].id, event_type="OrderCreated", description="Order created for Industrial Sensors", tx_hash="0xabc123", block_number=1000, from_status=None, to_status="Created"),
            AuditLog(order_id=orders[0].id, event_type="OrderShipped", description="Items shipped by seller", tx_hash="0xabc124", block_number=1005, from_status="Created", to_status="Shipped"),
            AuditLog(order_id=orders[1].id, event_type="OrderCompleted", description="Funds released to seller after inspection", tx_hash="0xdef456", block_number=2000, from_status="Delivered", to_status="Completed"),
            AuditLog(order_id=orders[2].id, event_type="OrderDisputed", description="Buyer raised dispute: Item not as described", tx_hash="0xghi789", block_number=3000, from_status="Delivered", to_status="Disputed")
        ]
        db.session.add_all(logs)
        
        # 5. Create AI Summary
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
