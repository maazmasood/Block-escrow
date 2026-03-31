from datetime import datetime
from database import db

class Escrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_address = db.Column(db.String(42), nullable=True) # Might be null initially
    buyer_address = db.Column(db.String(42), nullable=False)
    seller_address = db.Column(db.String(42), nullable=False)
    agent_address = db.Column(db.String(42), nullable=False)
    amount = db.Column(db.Float, nullable=False) # Supporting both ETH and USDT
    token_symbol = db.Column(db.String(10), default='ETH') # Default to ETH
    ipfs_hash = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='Created')
    
    # Multichain Fields
    is_multichain = db.Column(db.Boolean, default=False)
    source_chain_id = db.Column(db.String(20), default='8545')
    dest_chain_id = db.Column(db.String(20), default='8546')
    mirror_contract_address = db.Column(db.String(42), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'contract_address': self.contract_address,
            'buyer': self.buyer_address,
            'seller': self.seller_address,
            'agent': self.agent_address,
            'amount': self.amount,
            'token': self.token_symbol,
            'ipfs_hash': self.ipfs_hash,
            'status': self.status,
            'is_multichain': self.is_multichain,
            'source_chain': self.source_chain_id,
            'dest_chain': self.dest_chain_id,
            'mirror_address': self.mirror_contract_address,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escrow_id = db.Column(db.Integer, db.ForeignKey('escrow.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False) # e.g., "Funds Deposited", "Dispute Raised"
    description = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'escrow_id': self.escrow_id,
            'event_type': self.event_type,
            'description': self.description,
            'timestamp': self.timestamp.isoformat()
        }

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_address = db.Column(db.String(42), nullable=False) # Address of the user to notify
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user': self.user_address,
            'message': self.message,
            'is_read': self.is_read,
            'timestamp': self.timestamp.isoformat()
        }

class AISummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), nullable=False) # YYYY-MM
    summary_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'month': self.month,
            'summary': self.summary_text,
            'created_at': self.created_at.isoformat()
        }

class User(db.Model):
    wallet_address = db.Column(db.String(42), primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'wallet_address': self.wallet_address,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat()
        }
