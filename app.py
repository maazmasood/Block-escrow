import os
import base64
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, jsonify, render_template, redirect
from flask_cors import CORS
import requests
from database import db
from models import Order, AuditLog, Notification, AISummary, User, OrderDocument
from datetime import datetime, timedelta
from web3 import Web3
import json
from sqlalchemy import inspect, text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fyp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app) 
db.init_app(app)

with app.app_context():
    db.create_all()
    
    # Lightweight schema sync for existing SQLite databases.
    # This avoids forcing users to delete fyp.db when we add profile fields.
    try:
        existing_columns = {col['name'] for col in inspect(db.engine).get_columns('user')}
        user_column_migrations = [
            ('bio', 'TEXT'),
            ('profile_pic_base64', 'TEXT'),
            ('niche', 'VARCHAR(120)'),
            ('rate', 'VARCHAR(120)'),
            ('area_coverage', 'VARCHAR(200)')
        ]
        
        for col_name, col_type in user_column_migrations:
            if col_name not in existing_columns:
                db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {col_name} {col_type}'))
                
        # Order table migration
        order_columns = {col['name'] for col in inspect(db.engine).get_columns('order')}
        order_migrations = [
            ('city', 'VARCHAR(100)'),
            ('country', 'VARCHAR(100)'),
            ('phone', 'VARCHAR(50)')
        ]
        for col_name, col_type in order_migrations:
            if col_name not in order_columns:
                db.session.execute(text(f'ALTER TABLE "order" ADD COLUMN {col_name} {col_type}'))
                
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Schema sync skipped/failed: {e}")

# --- Email Service Setup ---
import smtplib
from email.message import EmailMessage

def send_email(to_email, subject, body):
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    
    if not smtp_email or not smtp_password:
        app.logger.warning(f"SMTP Credentials Missing. Mocking Email Delivery to {to_email}")
        app.logger.info(f"Subject: {subject}\nBody:\n{body}")
        return False
        
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = smtp_email
        msg['To'] = to_email
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False

def push_notification(user_address, message, subject="dBlock Escrow Alert"):
    """Saves a notification to the database and sends an email if the user has one registered."""
    try:
        user_address = user_address.lower()
        # 1. Save to DB
        notif = Notification(user_address=user_address, message=message)
        db.session.add(notif)
        db.session.commit()
        
        # 2. Check for Email
        user = db.session.get(User, user_address)
        if user and user.email:
            email_body = f"""
            Hello {user.name},
            
            You have a new update regarding your Supply Chain order:
            
            {message}
            
            View details on your dashboard: http://127.0.0.1:5000/dashboard
            
            Best regards,
            dBlock Escrow Audit Engine
            """
            send_email(user.email, subject, email_body)
        return True
    except Exception as e:
        app.logger.error(f"Error in push_notification: {e}")
        return False

def promote_to_onchain_admin(user_address):
    """Automatically whitelists an admin address on both ETH and BNB blockchains."""
    deployer_key = os.environ.get("DEPLOYER_PRIVATE_KEY")
    if not deployer_key:
        app.logger.error("DEPLOYER_PRIVATE_KEY is missing. Cannot promote admin on-chain.")
        return False

    # Load Config
    try:
        config_path = os.path.join(app.root_path, 'static', 'contract', 'multichain_config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        app.logger.error(f"Failed to load multichain config: {e}")
        return False

    # Minimal ABI for setAdminStatus
    abi = [{
        "inputs": [
            {"internalType": "address", "name": "_admin", "type": "address"},
            {"internalType": "bool", "name": "_status", "type": "bool"}
        ],
        "name": "setAdminStatus",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }]

    promoted_any = False
    
    # Chains to update
    networks = [
        {"url": "http://127.0.0.1:8545", "contract": config.get('ETH_SOURCE'), "name": "ETH"},
        {"url": "http://127.0.0.1:8546", "contract": config.get('BNB_MIRROR'), "name": "BNB"}
    ]

    for net in networks:
        if not net['contract']: continue
        try:
            w3 = Web3(Web3.HTTPProvider(net['url']))
            account = w3.eth.account.from_key(deployer_key)
            contract = w3.eth.contract(address=w3.to_checksum_address(net['contract']), abi=abi)
            
            nonce = w3.eth.get_transaction_count(account.address)
            tx = contract.functions.setAdminStatus(w3.to_checksum_address(user_address), True).build_transaction({
                'from': account.address,
                'nonce': nonce,
                'gas': 100000,
                'gasPrice': w3.eth.gas_price
            })
            
            signed_tx = w3.eth.account.sign_transaction(tx, deployer_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            app.logger.info(f"Promoted {user_address} to admin on {net['name']}. TX: {w3.to_hex(tx_hash)}")
            promoted_any = True
        except Exception as e:
            app.logger.error(f"Failed to promote admin on {net['name']}: {e}")

    return promoted_any

# --- Local IPFS Configuration ---
LOCAL_IPFS_API_URL = "http://127.0.0.1:5001/api/v0/add"

# --- Frontend Routes ---

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/')
def dashboard():
    total_volume = db.session.query(db.func.sum(Order.amount)).scalar() or 0
    active_count = Order.query.filter(Order.status != 'Completed').count()
    completed_count = Order.query.filter_by(status='Completed').count()
    return render_template('dashboard.html', total_eth=total_volume, active_count=active_count, completed_count=completed_count)

@app.route('/create_order')
def create_order():
    sellers = User.query.filter_by(role='seller').all()
    agents = User.query.filter_by(role='agent').all()
    return render_template('create_order.html', sellers=sellers, agents=agents)

@app.route('/order_tracking')
def order_tracking():
    return render_template('contract_details.html')

@app.route('/orders')
def orders():
    all_orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('transactions.html', escrows=all_orders)

@app.route('/audits')
def audits():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    latest_summary = AISummary.query.order_by(AISummary.created_at.desc()).first()
    return render_template('audits.html', logs=logs, latest_summary=latest_summary)

@app.route('/notifications')
def notifications():
    notifications = Notification.query.order_by(Notification.timestamp.desc()).all()
    return render_template('notifications.html', notifications=notifications)

@app.route('/sellers')
def sellers():
    seller_users = User.query.filter_by(role='seller').order_by(User.created_at.desc()).all()
    return render_template('sellers.html', sellers=seller_users)

@app.route('/agents')
def agents():
    agent_users = User.query.filter_by(role='agent').order_by(User.created_at.desc()).all()
    return render_template('agents.html', agents=agent_users)

@app.route('/edit_profile')
def edit_profile():
    return render_template('edit_profile.html')

@app.route('/admin_management')
def admin_management():
    return render_template('admin_management.html')

# --- API Endpoints: Auth ---

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json
    address = data.get('address')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400

    address = address.lower()
    user = db.session.get(User, address)
    if not user:
        return jsonify({"error": "User not registered. Please sign up first."}), 404
        
    return jsonify({"message": "Logged in", "user": user.to_dict()}), 200

@app.route('/api/user/email/<address>', methods=['GET'])
def get_user_email(address):
    user = db.session.get(User, address.lower())
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "email": user.email,
        "name": user.name,
        "bio": user.bio,
        "profile_pic_base64": user.profile_pic_base64,
        "niche": user.niche,
        "rate": user.rate,
        "area_coverage": user.area_coverage
    }), 200

@app.route('/api/user/email', methods=['POST'])
def update_user_email():
    data = request.json
    address = data.get('address')
    email = data.get('email')
    name = data.get('name')
    bio = data.get('bio')
    profile_pic_base64 = data.get('profile_pic_base64')
    niche = data.get('niche')
    rate = data.get('rate')
    area_coverage = data.get('area_coverage')
    
    if not address or not email:
        return jsonify({"error": "Address and email are required"}), 400
        
    user = db.session.get(User, address.lower())
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    user.email = email
    if name:
        user.name = name
    if bio is not None:
        user.bio = bio
    if profile_pic_base64 is not None:
        user.profile_pic_base64 = profile_pic_base64
    if niche is not None:
        user.niche = niche
    if rate is not None:
        user.rate = rate
    if area_coverage is not None:
        user.area_coverage = area_coverage
    db.session.commit()
    return jsonify({"message": "Profile updated", "user": user.to_dict()}), 200

@app.route('/api/user/profile/<address>', methods=['GET'])
def get_user_profile(address):
    user = db.session.get(User, address.lower())
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200

@app.route('/api/user/profile', methods=['POST'])
def update_user_profile():
    data = request.json or {}
    address = (data.get('address') or '').lower()
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    user = db.session.get(User, address)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    name = data.get('name')
    email = data.get('email')
    bio = data.get('bio')
    profile_pic_base64 = data.get('profile_pic_base64')
    niche = data.get('niche')
    rate = data.get('rate')
    area_coverage = data.get('area_coverage')
    
    if name is not None:
        user.name = name.strip()
    if email is not None:
        user.email = email.strip()
    if bio is not None:
        user.bio = bio.strip()
    if profile_pic_base64 is not None:
        user.profile_pic_base64 = profile_pic_base64
    if niche is not None:
        user.niche = niche.strip()
    if rate is not None:
        user.rate = rate.strip()
    if area_coverage is not None:
        user.area_coverage = area_coverage.strip()
    
    db.session.commit()
    return jsonify({"message": "Profile updated", "user": user.to_dict()}), 200

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json
    address = data.get('address')
    name = data.get('name')
    role = data.get('role')
    
    if not address or not name or not role:
        return jsonify({"error": "Address, name and role are required"}), 400

    address = address.lower()
    existing = db.session.get(User, address)
    if existing:
        return jsonify({"error": "User already registered"}), 409
        
    user = User(
        wallet_address=address,
        name=name,
        role=role,
        email="",
        bio="",
        profile_pic_base64="",
        niche="",
        rate="",
        area_coverage=""
    )
    db.session.add(user)
    db.session.commit()
    
    # If registering as admin, promote on-chain
    if role == 'admin':
        from threading import Thread
        Thread(target=promote_to_onchain_admin, args=(address,)).start()
    
    return jsonify({"message": "Account created successfully", "user": user.to_dict()}), 201

@app.route('/api/users/<role>', methods=['GET'])
def get_users_by_role(role):
    users = User.query.filter_by(role=role).all()
    return jsonify([u.to_dict() for u in users]), 200

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users]), 200

@app.route('/api/admin/users/<address>', methods=['DELETE'])
def delete_user(address):
    address = address.lower()
    user = db.session.get(User, address)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Optional: Prevent deleting the last admin or yourself
    # For now, let's just delete
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": f"User {address} deleted"}), 200

@app.route('/api/admin/users/<address>/role', methods=['POST'])
def update_user_role_admin(address):
    data = request.json
    new_role = data.get('role')
    if not new_role or new_role not in ['buyer', 'seller', 'agent', 'admin']:
        return jsonify({"error": "Invalid role"}), 400
    
    address = address.lower()
    user = db.session.get(User, address)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.role = new_role
    db.session.commit()
    
    # If promoted to admin, promote on-chain too
    if new_role == 'admin':
        from threading import Thread
        Thread(target=promote_to_onchain_admin, args=(address,)).start()
        
    return jsonify({"message": f"User {address} role updated to {new_role}"}), 200

# --- API Endpoints: Orders ---

@app.route('/api/order/create', methods=['POST'])
def create_order_log():
    data = request.json
    buyer_addr = data.get('buyer', '').lower()
    
    # Validation: Admin cannot create orders
    user = db.session.get(User, buyer_addr)
    if user and user.role == 'admin':
        return jsonify({"error": "Administrators are restricted from creating orders."}), 403

    new_order = Order(
        contract_address=data.get('contractAddress'),
        order_id_onchain=data.get('orderIdOnchain'),
        buyer_address=buyer_addr,
        seller_address=data.get('seller', '').lower(),
        agent_address=data.get('agent', '').lower(),
        amount=float(data.get('amount')),
        token_symbol=data.get('token', 'ETH'),
        is_multichain=data.get('isMultichain', False),
        mirror_address=data.get('mirrorAddress'),
        product_description=data.get('productDescription', 'Supply Chain Order'),
        city=data.get('city'),
        country=data.get('country'),
        phone=data.get('phone'),
        status='Created'
    )
    db.session.add(new_order)
    db.session.commit()
    
    # Store initial generic receipt/PO hash if passed
    ipfs_hash = data.get('ipfsHash')
    if ipfs_hash:
        doc = OrderDocument(order_id=new_order.id, stage='Created', ipfs_hash=ipfs_hash, doc_type='receipt', uploaded_by=new_order.buyer_address)
        db.session.add(doc)
    
    log = AuditLog(order_id=new_order.id, event_type="OrderCreated", description=f"Order #{new_order.order_id_onchain} created by buyer.", to_status="Created")
    db.session.add(log)
    
    # 3. Notify Seller
    push_notification(
        new_order.seller_address, 
        f"New Order Request: {new_order.amount} {new_order.token_symbol} for {new_order.product_description}",
        "New dBlock Escrow Order"
    )
    
    db.session.commit()
    
    # Trigger OCR if it is a receipt (PO)
    if ipfs_hash:
        from threading import Thread
        Thread(target=process_document_ocr, args=(doc.id,)).start()
        
    return jsonify({"message": "Order logged", "id": new_order.id}), 201

@app.route('/api/admin/dashboard_stats', methods=['GET'])
def get_admin_dashboard_stats():
    total_users = User.query.count()
    total_orders = Order.query.count()
    total_agents = User.query.filter_by(role='agent').count()
    total_sellers = User.query.filter_by(role='seller').count()
    total_volume = db.session.query(db.func.sum(Order.amount)).scalar() or 0
    return jsonify({
        "total_users": total_users,
        "total_orders": total_orders,
        "total_agents": total_agents,
        "total_sellers": total_sellers,
        "total_volume": total_volume
    }), 200

@app.route('/api/buyer/performance_stats', methods=['GET'])
def get_performance_stats():
    # Top Sellers based on total orders taken
    seller_stats = db.session.query(
        User.name, User.wallet_address, db.func.count(Order.id).label('total_orders')
    ).join(Order, Order.seller_address == User.wallet_address)\
     .filter(User.role == 'seller')\
     .group_by(User.wallet_address)\
     .order_by(db.text('total_orders DESC'))\
     .limit(5).all()

    # Top Agents based on total orders taken
    agent_stats = db.session.query(
        User.name, User.wallet_address, db.func.count(Order.id).label('total_orders')
    ).join(Order, Order.agent_address == User.wallet_address)\
     .filter(User.role == 'agent')\
     .group_by(User.wallet_address)\
     .order_by(db.text('total_orders DESC'))\
     .limit(5).all()

    return jsonify({
        "sellers": [{"name": s[0], "address": s[1], "count": s[2]} for s in seller_stats],
        "agents": [{"name": a[0], "address": a[1], "count": a[2]} for a in agent_stats]
    }), 200

@app.route('/api/agent/route_guide', methods=['POST'])
def agent_route_guide():
    data = request.json
    source = data.get('source')
    destination = data.get('destination')
    if not source or not destination:
        return jsonify({"error": "Source and destination are required"}), 400
        
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"error": "GROQ_API_KEY environment variable not set."}), 500
        
    prompt = f"What is the best shipping route for logistics between {source} and {destination}? Give a very short summary suitable for a dashboard."
    
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a helpful logistics assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 150
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        summary_text = result["choices"][0]["message"]["content"]
        return jsonify({"route_guide": summary_text}), 200
    except Exception as e:
        return jsonify({"route_guide": "Could not determine route at this time due to an error."}), 500

@app.route('/api/orders/user/<address>', methods=['GET'])
def get_user_orders(address):
    address = address.lower()
    user = db.session.get(User, address)
    if not user:
        return jsonify([]), 200
        
    if user.role == 'admin':
        orders = Order.query.order_by(Order.created_at.desc()).all()
    elif user.role == 'agent':
        orders = Order.query.filter_by(agent_address=address).order_by(Order.created_at.desc()).all()
    elif user.role == 'seller':
        orders = Order.query.filter_by(seller_address=address).order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.filter_by(buyer_address=address).order_by(Order.created_at.desc()).all()
        
    return jsonify([o.to_dict() for o in orders]), 200

@app.route('/api/order/sync', methods=['POST'])
def sync_order():
    data = request.json
    db_order_id = data.get('dbOrderId')
    order_id_onchain = data.get('orderIdOnchain') # From blockchain event
    
    event = data.get('event')
    tx_hash = data.get('txHash')
    block_num = data.get('blockNumber')
    ipfs_hash = data.get('proofHash')
    actor = data.get('actor', '').lower()
    
    # Prioritize lookup by unique DB primary key
    if db_order_id:
        order = db.session.get(Order, db_order_id)
    else:
        # Fallback to onchain Id (making sure we compare as correct types)
        order = Order.query.filter(Order.order_id_onchain == order_id_onchain).first()

    if not order:
        app.logger.error(f"Sync failed: Order NOT found (DB_ID: {db_order_id}, OnChain: {order_id_onchain})")
        return jsonify({"error": "Order not found"}), 404
        
    old_status = order.status
    timestamp = datetime.utcnow()
    
    if event == "OrderConfirmed":
        order.status = "Confirmed"
        order.confirmed_at = timestamp
        notif_target = order.buyer_address
        msg = f"Order #{order_id_onchain} confirmed by seller."
    elif event == "OrderShipped":
        order.status = "Shipped"
        order.shipped_at = timestamp
        notif_target = order.agent_address
        msg = f"Order #{order_id_onchain} shipped. Waiting for agent checkpoint."
    elif event == "AgentCheckpoint":
        order.status = "AtCheckpoint"
        order.in_transit_at = timestamp
        notif_target = order.buyer_address
        msg = f"Order #{order_id_onchain} arrived at Agent Checkpoint."
    elif event == "OrderDelivered":
        order.status = "Delivered"
        order.delivered_at = timestamp
        notif_target = order.buyer_address
        msg = f"Order #{order_id_onchain} delivered by seller! Please confirm receipt."
    elif event == "OrderCompleted":
        order.status = "Completed"
        order.completed_at = timestamp
        notif_target = order.seller_address
        msg = f"Order #{order_id_onchain} completed by buyer. Funds released!"
    elif event == "OrderDisputed":
        order.status = "Disputed"
        notif_target = "Admin" # Admins get this
        msg = f"Order #{order_id_onchain} has been DISPUTED. Admin intervention required."
        # Create notifs for all Admins
        admins = User.query.filter_by(role='admin').all()
        for a in admins:
            push_notification(a.wallet_address, msg, "Supply Chain Dispute!")
    elif event == "OrderResolved":
        order.status = "Completed"
        order.completed_at = timestamp
        notif_target = order.buyer_address
        msg = f"Order #{order_id_onchain} dispute resolved by Admin."
        push_notification(order.seller_address, msg, "Dispute Resolved")
    else:
        return jsonify({"message": "Event ignored"}), 200

    order.last_tx_hash = tx_hash
    order.last_synced_block = block_num
    
    if ipfs_hash and ipfs_hash != "":
        # Determine doc type based on event
        dt = "photo" if event in ["OrderShipped", "AgentCheckpoint", "OrderDelivered"] else "receipt"
        doc = OrderDocument(order_id=order.id, stage=order.status, ipfs_hash=ipfs_hash, doc_type=dt, uploaded_by=actor)
        db.session.add(doc)
        db.session.flush() # Get ID
        
        # Trigger OCR in background if it's a receipt
        if dt == 'receipt':
            from threading import Thread
            Thread(target=process_document_ocr, args=(doc.id,)).start()
    
    log = AuditLog(order_id=order.id, event_type=event, description=f"State changed via {tx_hash[:8]}...", tx_hash=tx_hash, block_number=block_num, from_status=old_status, to_status=order.status)
    db.session.add(log)
    
    if notif_target != "Admin":
        push_notification(notif_target, msg, f"Order Update: #{order_id_onchain}")
            
    db.session.commit()
    return jsonify({"message": "Sync successful"}), 200

@app.route('/api/order/<int:order_id>/documents', methods=['GET'])
def get_order_documents(order_id):
    docs = OrderDocument.query.filter_by(order_id=order_id).order_by(OrderDocument.uploaded_at.asc()).all()
    return jsonify([d.to_dict() for d in docs]), 200

@app.route('/api/transactions/clear', methods=['POST'])
def clear_transactions():
    try:
        db.session.query(OrderDocument).delete()
        db.session.query(Order).delete()
        db.session.query(AuditLog).delete()
        db.session.commit()
        return jsonify({"message": "Transactions cleared"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/audits/clear', methods=['POST'])
def clear_audits():
    try:
        db.session.query(AuditLog).delete()
        db.session.commit()
        return jsonify({"message": "Audit logs cleared"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/audits/filter', methods=['POST'])
def filter_audits():
    data = request.json
    address = data.get('address')
    timeframe = data.get('timeframe', 'all')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400

    address = address.lower()
    user = db.session.get(User, address)
    
    # Base query
    if user and user.role == 'admin':
        # Admins see everything
        query = db.session.query(AuditLog)
    else:
        # Regular users see logs for orders they are involved in
        query = db.session.query(AuditLog).join(Order, AuditLog.order_id == Order.id)
        query = query.filter(db.or_(
            Order.buyer_address == address,
            Order.seller_address == address,
            Order.agent_address == address
        ))
    
    # Timeframe filtering
    now = datetime.utcnow()
    if timeframe == '24h':
        query = query.filter(AuditLog.timestamp >= now - timedelta(hours=24))
    elif timeframe == '7d':
        query = query.filter(AuditLog.timestamp >= now - timedelta(days=7))
    elif timeframe == '30d':
        query = query.filter(AuditLog.timestamp >= now - timedelta(days=30))
        
    logs = query.order_by(AuditLog.timestamp.desc()).all()
    return jsonify([l.to_dict() for l in logs]), 200

@app.route('/api/notifications/filter', methods=['POST'])
def filter_notifications():
    data = request.json
    address = data.get('address')
    if not address:
        return jsonify({"error": "Address is required"}), 400
    try:
        notifications = Notification.query.filter_by(user_address=address).order_by(Notification.timestamp.desc()).limit(15).all()
        return jsonify([n.to_dict() for n in notifications]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/clear', methods=['POST'])
def clear_notifications():
    try:
        address = request.json.get('address')
        if address:
            db.session.query(Notification).filter_by(user_address=address).delete()
        else:
            db.session.query(Notification).delete()
        db.session.commit()
        return jsonify({"message": "Notifications cleared"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# --- Audit & Groq IPFS Process (From existing logic) ---

@app.route('/api/audit/generate', methods=['POST'])
def generate_audit_summary():
    data = request.json
    address = data.get('address')
    if not address:
        return jsonify({"error": "Address is required"}), 400
    
    address = address.lower()
    
    # User-specific metrics
    orders_query = Order.query.filter(db.or_(
        Order.buyer_address == address,
        Order.seller_address == address,
        Order.agent_address == address
    ))
    total = orders_query.count()
    volume = db.session.query(db.func.sum(Order.amount)).filter(db.or_(
        Order.buyer_address == address,
        Order.seller_address == address,
        Order.agent_address == address
    )).scalar() or 0
    disputes = orders_query.filter_by(status='Disputed').count()
    
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"error": "GROQ_API_KEY environment variable not set."}), 500
        
    prompt = f"""
    You are an AI Audit Engine for a Web3 Supply Chain platform named dBlock Supplychain Escrow.
    Please generate a short, professional monthly audit report summary for user {address} formatted in Markdown.

    Here are the user's specific metrics for this month:
    - total volume associated with this wallet: {volume}
    - total orders involved in: {total}
    - disputes logged: {disputes}

    Keep it concise but insightful. Focus on their specific activity. Format with bullet points.
    """

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a professional auditor for a blockchain platform."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 512
    }

    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        summary_text = result["choices"][0]["message"]["content"]
    except Exception as e:
        summary_text = f"**User Audit Report (Fallback)**\n- **Activity Volume**: {volume}\n- **Orders**: {total}\n- **Disputes**: {disputes}"
    
    summary = AISummary(user_address=address, month=datetime.now().strftime('%Y-%m'), summary_text=summary_text)
    db.session.add(summary)
    db.session.commit()
    
    return jsonify({"message": "Audit generated", "summary": summary.to_dict()})

@app.route('/api/audit/latest/<address>', methods=['GET'])
def get_latest_audit(address):
    summary = AISummary.query.filter_by(user_address=address.lower()).order_by(AISummary.created_at.desc()).first()
    if not summary:
        return jsonify({"error": "No report found"}), 404
    return jsonify(summary.to_dict()), 200

def process_document_ocr(doc_id):
    """Hardened OCR: Adds retries, status updates, and explicit error reporting."""
    import time
    with app.app_context():
        # Small delay to ensure the main thread has committed the doc record
        time.sleep(1.5)
        
        doc = db.session.get(OrderDocument, doc_id)
        if not doc or doc.doc_type != 'receipt':
            return

        # 1. Update status to 'Analyzing' so UI knows we are working
        doc.ocr_result = "🔍 AI is currently analyzing the document... Please refresh in a moment."
        db.session.commit()
        
        app.logger.info(f"Hardened OCR Start: doc {doc_id}")
        
        try:
            # 2. Fetch from IPFS with Retries (3 attempts)
            ipfs_content = None
            for attempt in range(1, 4):
                try:
                    gateway_url = f"http://127.0.0.1:8080/ipfs/{doc.ipfs_hash}"
                    app.logger.info(f"IPFS Fetch Attempt {attempt} for {doc.ipfs_hash}")
                    resp = requests.get(gateway_url, timeout=12)
                    if resp.ok:
                        ipfs_content = resp.content
                        break
                except Exception as e:
                    app.logger.warning(f"IPFS Attempt {attempt} failed: {e}")
                time.sleep(2) # Wait before retry

            if not ipfs_content:
                doc.ocr_result = "❌ ERROR: Document could not be retrieved from IPFS after 3 attempts. Please ensure your IPFS Desktop/Daemon is running."
                db.session.commit()
                return

            # 3. Encode & Prepare Payload
            base64_image = base64.b64encode(ipfs_content).decode('utf-8')
            
            headers = {
                "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Provide a concise, professional summary of this financial document. Include: 1. Merchant/Issuer, 2. Date, 3. Total Amount, 4. Key Items Purchased, and 5. A brief verdict on document validity. If it is NOT a financial document, return strictly 'NOT_A_RECEIPT_ALERT'."
                            },
                            {
                                "type": "image_url",
                                "image_url": { "url": f"data:image/jpeg;base64,{base64_image}" }
                            }
                        ]
                    }
                ],
                "temperature": 0.1
            }
            
            # 4. Call Groq with longer timeout
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=45)
            
            if r.ok:
                text = r.json()["choices"][0]["message"]["content"]
                if "NOT_A_RECEIPT_ALERT" in text:
                    doc.ocr_result = "⚠️ ALERT: This document does not appear to be a receipt or financial record."
                else:
                    doc.ocr_result = text
                app.logger.info(f"OCR Success for doc {doc_id}")
            else:
                raw_error = r.text
                try:
                    err_json = r.json()
                    error_msg = err_json.get('error', {}).get('message', 'Unknown AI Error')
                except:
                    error_msg = f"HTTP {r.status_code}: {raw_error[:100]}"
                
                doc.ocr_result = f"❌ AI ERROR: {error_msg}"
                app.logger.error(f"Groq API Error for doc {doc_id}: {error_msg}")
            
            db.session.commit()
        except Exception as e:
            app.logger.error(f"OCR Critical Crash: {e}")
            try:
                doc.ocr_result = f"🔥 SYSTEM ERROR: {str(e)}"
                db.session.commit()
            except: pass

@app.route('/api/receipt/process_ipfs', methods=['POST'])
def process_receipt_ipfs():
    """Fetches an image from local IPFS and processes it with Groq Vision."""
    data = request.json
    ipfs_hash = data.get('ipfsHash')
    
    if not ipfs_hash:
        return jsonify({"error": "No ipfsHash provided"}), 400
        
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"error": "GROQ_API_KEY environment variable not set."}), 500

    try:
        gateway_url = f"http://127.0.0.1:8080/ipfs/{ipfs_hash}"
        ipfs_response = requests.get(gateway_url, timeout=10)
        ipfs_response.raise_for_status()
        
        file_content = ipfs_response.content
        base64_image = base64.b64encode(file_content).decode('utf-8')
        mime_type = 'image/jpeg' 
            
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this image/document from a supply chain stage. Provide a brief visual summary of the item or receipt."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "temperature": 0.3,
            "max_tokens": 512
        }
        
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        summary_text = result["choices"][0]["message"]["content"]
        
        return jsonify({"message": "Processed successfully", "summary": summary_text}), 200

    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/upload-ipfs', methods=['POST'])
def upload_ipfs():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        files = {
            'file': (file.filename, file.stream, file.mimetype)
        }
        response = requests.post(LOCAL_IPFS_API_URL, files=files, timeout=60)
        response.raise_for_status() 
        ipfs_data = response.json()
        ipfs_hash = ipfs_data.get('Hash')
        
        if ipfs_hash:
            return jsonify({
                "message": "File added to local IPFS", 
                "ipfsHash": ipfs_hash,
                "ipfsLink": f"http://127.0.0.1:8080/ipfs/{ipfs_hash}" 
            }), 200
        else:
            return jsonify({"error": "Local IPFS API did not return a hash", "details": ipfs_data}), 500

    except Exception as e:
        app.logger.error(f"IPFS Error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)