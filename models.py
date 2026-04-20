from datetime import datetime
from database import db

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contract_address = db.Column(db.String(42), nullable=False)
    order_id_onchain = db.Column(db.Integer, nullable=False)
    
    # Parties
    buyer_address = db.Column(db.String(42), nullable=False)
    seller_address = db.Column(db.String(42), nullable=False)
    agent_address = db.Column(db.String(42), nullable=False)
    
    # Order details
    product_description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    token_symbol = db.Column(db.String(10), default='ETH') # Support ETH and USDT
    
    is_multichain = db.Column(db.Boolean, default=False)
    mirror_address = db.Column(db.String(42), nullable=True)

    status = db.Column(db.String(20), default='Created')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    shipped_at = db.Column(db.DateTime, nullable=True)
    in_transit_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Blockchain sync fields
    last_tx_hash = db.Column(db.String(66), nullable=True)
    last_synced_block = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'contract_address': self.contract_address,
            'order_id_onchain': self.order_id_onchain,
            'buyer': self.buyer_address,
            'seller': self.seller_address,
            'agent': self.agent_address,
            'product_description': self.product_description,
            'amount': self.amount,
            'token_symbol': self.token_symbol,
            'is_multichain': self.is_multichain,
            'mirror_address': self.mirror_address,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'confirmed_at': self.confirmed_at.isoformat() if self.confirmed_at else None,
            'shipped_at': self.shipped_at.isoformat() if self.shipped_at else None,
            'in_transit_at': self.in_transit_at.isoformat() if self.in_transit_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_tx_hash': self.last_tx_hash
        }

class OrderDocument(db.Model):
    """Stores IPFS document references for each order stage"""
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    stage = db.Column(db.String(20), nullable=False)  # created, confirmed, shipped, etc.
    ipfs_hash = db.Column(db.String(100), nullable=False)
    doc_type = db.Column(db.String(20), default='receipt')  # receipt, photo, tracking
    filename = db.Column(db.String(255), nullable=True)
    uploaded_by = db.Column(db.String(42), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    ocr_result = db.Column(db.Text, nullable=True) # AI Extracted data

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'stage': self.stage,
            'ipfs_hash': self.ipfs_hash,
            'doc_type': self.doc_type,
            'filename': self.filename,
            'uploaded_by': self.uploaded_by,
            'uploaded_at': self.uploaded_at.isoformat(),
            'ocr_result': self.ocr_result
        }

class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False) 
    description = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tx_hash = db.Column(db.String(66), nullable=True)
    block_number = db.Column(db.Integer, nullable=True)
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'order_id': self.order_id,
            'event_type': self.event_type,
            'description': self.description,
            'timestamp': self.timestamp.isoformat(),
            'tx_hash': self.tx_hash,
            'from_status': self.from_status,
            'to_status': self.to_status
        }

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_address = db.Column(db.String(42), nullable=False)
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
    user_address = db.Column(db.String(42), nullable=True) # Linked to a user
    month = db.Column(db.String(7), nullable=False) 
    summary_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_address': self.user_address,
            'month': self.month,
            'summary': self.summary_text,
            'created_at': self.created_at.isoformat()
        }

class User(db.Model):
    wallet_address = db.Column(db.String(42), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), default='buyer') # buyer, seller, agent, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'wallet_address': self.wallet_address,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }
