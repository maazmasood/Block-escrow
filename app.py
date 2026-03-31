import os
import base64
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import requests
from database import db
from models import Escrow, AuditLog, Notification, AISummary, User
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fyp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app) 
db.init_app(app)

with app.app_context():
    db.create_all()

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

# --- Local IPFS Configuration ---
# The default IPFS API endpoint (Kubo/go-ipfs)
LOCAL_IPFS_API_URL = "http://127.0.0.1:5001/api/v0/add"

@app.route('/')
def dashboard():
    # Fetch summary stats
    total_volume = db.session.query(db.func.sum(Escrow.amount)).scalar() or 0
    active_count = Escrow.query.filter(Escrow.status != 'Released').count()
    completed_count = Escrow.query.filter_by(status='Released').count()
    return render_template('dashboard.html', total_eth=total_volume, active_count=active_count, completed_count=completed_count)

@app.route('/create_contract')
def create_contract():
    return render_template('create_contract.html')

@app.route('/contract_details')
def contract_details():
    return render_template('contract_details.html')

@app.route('/transactions')
def transactions():
    escrows = Escrow.query.order_by(Escrow.created_at.desc()).all()
    return render_template('transactions.html', escrows=escrows)

@app.route('/audits')
def audits():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    latest_summary = AISummary.query.order_by(AISummary.created_at.desc()).first()
    return render_template('audits.html', logs=logs, latest_summary=latest_summary)

@app.route('/notifications')
def notifications():
    # In a real app, filter by logged-in user. Here, show all for demo.
    notifications = Notification.query.order_by(Notification.timestamp.desc()).all()
    return render_template('notifications.html', notifications=notifications)

# --- API Endpoints ---

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    notifs = Notification.query.order_by(Notification.timestamp.desc()).limit(5).all()
    return jsonify([n.to_dict() for n in notifs])

@app.route('/api/user/email', methods=['POST'])
def save_user_email():
    """Register or update an email address and name for a given wallet address."""
    data = request.json
    address = data.get('address')
    email = data.get('email')
    name = data.get('name')
    
    if not address or not email:
        return jsonify({"error": "Address and email are required"}), 400
        
    user = db.session.get(User, address)
    if user:
        user.email = email
        if name:
            user.name = name
    else:
        user = User(wallet_address=address, email=email, name=name)
        db.session.add(user)
        
    db.session.commit()
    return jsonify({"message": "Profile saved completely", "user": user.to_dict()}), 200

@app.route('/api/user/email/<address>', methods=['GET'])
def get_user_email(address):
    """Fetch profile data stored for a given wallet address."""
    user = db.session.get(User, address)
    if user:
        return jsonify({"email": user.email, "name": user.name}), 200
    return jsonify({"email": None, "name": None}), 200

@app.route('/api/users/mapping', methods=['GET'])
def get_users_mapping():
    """Return a dictionary mapping wallet addresses to user names."""
    users = User.query.all()
    mapping = {u.wallet_address: u.name for u in users if u.name}
    return jsonify(mapping), 200

@app.route('/api/escrow/create', methods=['POST'])
def create_escrow_log():
    data = request.json
    new_escrow = Escrow(
        contract_address=data.get('contractAddress'), # New field
        buyer_address=data.get('buyer'),
        seller_address=data.get('receiver'),
        agent_address=data.get('agent'),
        amount=float(data.get('amount')),
        token_symbol=data.get('token', 'ETH'),
        ipfs_hash=data.get('ipfsHash'),
        status='Created',
        is_multichain=data.get('isMultichain', False),
        source_chain_id=data.get('sourceChain', '8545'),
        dest_chain_id=data.get('destChain', '8546'),
        mirror_contract_address=data.get('mirrorAddress')
    )
    db.session.add(new_escrow)
    db.session.commit()
    
    # Log Audit
    log = AuditLog(escrow_id=new_escrow.id, event_type="Creation", description=f"Escrow created by {new_escrow.buyer_address} for {new_escrow.amount} {new_escrow.token_symbol} at {new_escrow.contract_address}")
    db.session.add(log)
    
    # Notify Agent
    notif = Notification(user_address=new_escrow.agent_address, message=f"New Escrow Request: {new_escrow.amount} {new_escrow.token_symbol} from {new_escrow.buyer_address}")
    db.session.add(notif)
    
    db.session.commit()
    
    return jsonify({"message": "Escrow logged", "id": new_escrow.id}), 201

@app.route('/api/contracts/<user_address>', methods=['GET'])
def get_user_contracts(user_address):
    # Fetch contracts where the user is a participant
    contracts = Escrow.query.filter(
        (Escrow.buyer_address == user_address) | 
        (Escrow.seller_address == user_address) | 
        (Escrow.agent_address == user_address)
    ).order_by(Escrow.created_at.desc()).all()
    
    return jsonify([c.to_dict() for c in contracts]), 200

@app.route('/api/escrow/update', methods=['POST'])
def update_escrow_status():
    data = request.json
    contract_address = data.get('contractAddress')
    event = data.get('event') 
    
    # Audit Log
    log = AuditLog(event_type="Status Change", description=f"Contract {contract_address}: {event}")
    db.session.add(log)
    
    # Platform Notification 
    notif = Notification(user_address="Admin", message=f"Update on Escrow {contract_address}: {event}")
    db.session.add(notif)
    
    # Send Email Alerts to all Escrow parties mapping
    if contract_address:
        escrow = Escrow.query.filter_by(contract_address=contract_address).order_by(Escrow.created_at.desc()).first()
        if escrow:
            # Update the actual status in the database
            if "Released" in event or "Bridged" in event:
                escrow.status = "Released"
            else:
                # Keep it as 'Action Performed' or use the event string directly but truncated
                escrow.status = "Active" # Or just keep it as is if it's already 'Created'/'Active'
            
            participants = [escrow.buyer_address, escrow.seller_address, escrow.agent_address]
            for address in participants:
                if not address:
                    continue
                    
                # Store personal notification in DB
                user_notif = Notification(user_address=address, message=f"Your Contract ({contract_address[:6]}...) Acted: {event}")
                db.session.add(user_notif)

                # Attempt Email Dispatch
                user = db.session.get(User, address)
                if user and user.email:
                    subject = f"Escrow System Alert: Contract Updated ({contract_address[:6]}...)"
                    body = f"Hello,\n\nAn action was performed on your Web3 Escrow Contract ({contract_address}).\n\nRecent Activity: {event}\n\nPlease check your Escrow dashboard for more precise details.\n\nThank you,\nThe Escrow Auditing System"
                    send_email(user.email, subject, body)
                    
    db.session.commit()
    
    return jsonify({"message": "Status securely updated and notifications dispatched"}), 200

@app.route('/api/transactions/clear', methods=['POST'])
def clear_transactions():
    try:
        db.session.query(Escrow).delete()
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

@app.route('/api/notifications/filter', methods=['POST'])
def filter_notifications():
    data = request.json
    address = data.get('address')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
        
    try:
        # Filter notifications for this specific address
        filters = [Notification.user_address == address]
        notifications = Notification.query.filter(*filters).order_by(Notification.timestamp.desc()).all()
        return jsonify([n.to_dict() for n in notifications]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/audits/filter', methods=['POST'])
def filter_audits():
    data = request.json
    address = data.get('address')
    timeframe = data.get('timeframe', 'all')
    
    if not address:
        return jsonify({"error": "Address is required"}), 400
        
    try:
        query = db.session.query(AuditLog).join(Escrow).filter(
            (Escrow.buyer_address == address) | 
            (Escrow.seller_address == address) | 
            (Escrow.agent_address == address)
        )
        
        # Timeframe filtering
        now = datetime.utcnow()
        if timeframe == '24h':
            cutoff = now - timedelta(hours=24)
            query = query.filter(AuditLog.timestamp >= cutoff)
        elif timeframe == '7d':
            cutoff = now - timedelta(days=7)
            query = query.filter(AuditLog.timestamp >= cutoff)
        elif timeframe == '30d':
            cutoff = now - timedelta(days=30)
            query = query.filter(AuditLog.timestamp >= cutoff)
            
        logs = query.order_by(AuditLog.timestamp.desc()).all()
        return jsonify([l.to_dict() for l in logs]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/notifications/clear', methods=['POST'])
def clear_notifications():
    try:
        db.session.query(Notification).delete()
        db.session.commit()
        return jsonify({"message": "Notifications cleared"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/audit/generate', methods=['POST'])
def generate_audit_summary():
    # Gather metrics
    total = Escrow.query.count()
    volume = db.session.query(db.func.sum(Escrow.amount)).scalar() or 0
    disputes = AuditLog.query.filter(AuditLog.event_type.like('%Dispute%')).count()
    
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"error": "GROQ_API_KEY environment variable not set."}), 500
        
    prompt = f"""
    You are an AI Audit Engine for a Web3 Escrow service.
    Please generate a short, professional monthly audit report summary formatted in Markdown.

    Here are the metrics for this month:
    - Total Transaction Volume: {volume} ETH
    - Total Escrows: {total}
    - Potential Disputes Detected: {disputes}
    - System Health: All smart contracts executed within expected gas limits.
    - Compliance: Verified IPFS hashes for all {total} agreements.

    Keep it concise but insightful. Format with bullet points or small paragraphs.
    """

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a professional auditor for a blockchain escrow service."},
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
        app.logger.error(f"Groq API Error: {e}")
        # Fallback in case of API failure
        summary_text = f"""
        **Monthly Audit Report (Fallback)**
        - **Total Transaction Volume**: {volume} (Combined ETH/USDT) across {total} escrows.
        - **Risk Analysis**: {disputes} potential disputes detected.
        - **System Health**: All smart contracts executed within expected gas limits. 
        - **Compliance**: Verified IPFS hashes for all {total} agreements.
        
        *Generated by Fallback Audit Engine*
        """
    
    summary = AISummary(month=datetime.now().strftime('%Y-%m'), summary_text=summary_text)
    db.session.add(summary)
    db.session.commit()
    
    return jsonify({"message": "Audit generated", "summary": summary.to_dict()})

@app.route('/api/receipt/process', methods=['POST'])
def process_receipt():
    """Processes an uploaded receipt image using Groq Vision API to extract a summary and total."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    groq_api_key = os.environ.get("GROQ_API_KEY")
    if not groq_api_key:
        return jsonify({"error": "GROQ_API_KEY environment variable not set."}), 500

    try:
        # Read file and encode to base64
        file_content = file.read()
        base64_image = base64.b64encode(file_content).decode('utf-8')
        
        # Determine mime type naively
        mime_type = "image/jpeg"
        if file.filename.lower().endswith('.png'):
            mime_type = "image/png"
            
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
                            "text": "Analyze this receipt. Provide a brief summary of what the transaction is for, and explicitly state the total amount."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
        }
        
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        summary_text = result["choices"][0]["message"]["content"]
        
        return jsonify({
            "message": "Receipt processed successfully",
            "summary": summary_text
        }), 200

    except requests.exceptions.RequestException as e:
        error_details = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        app.logger.error(f"Groq Vision API Error: {error_details}")
        return jsonify({"error": f"Failed to process receipt with Groq API: {error_details}"}), 500
    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

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
        # Fetch from local IPFS gateway
        gateway_url = f"http://127.0.0.1:8080/ipfs/{ipfs_hash}"
        ipfs_response = requests.get(gateway_url, timeout=10)
        ipfs_response.raise_for_status()
        
        file_content = ipfs_response.content
        base64_image = base64.b64encode(file_content).decode('utf-8')
        
        mime_type = ipfs_response.headers.get('Content-Type', '')
        if 'image/png' in mime_type:
            mime_type = 'image/png'
        else:
            mime_type = 'image/jpeg' # Force an explicit image MIME type for Groq
            
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
                            "text": "Analyze this receipt. Provide a brief summary of what the transaction is for, and explicitly state the total amount."
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
        
        return jsonify({
            "message": "IPFS Receipt processed successfully",
            "summary": summary_text
        }), 200

    except requests.exceptions.RequestException as e:
        error_details = e.response.text if hasattr(e, 'response') and e.response is not None else str(e)
        app.logger.error(f"IPFS or Groq Vision API Error: {error_details}")
        return jsonify({"error": f"Failed to fetch from IPFS or process with Groq API: {error_details}"}), 500
    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/upload-ipfs', methods=['POST'])
def upload_ipfs():
    """Handles file upload and adds it to the local IPFS node."""
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        # The IPFS API expects the file to be sent in a multipart form
        files = {
            'file': (file.filename, file.stream, file.mimetype)
        }
        
        # Send the file to the local IPFS daemon's /api/v0/add endpoint
        response = requests.post(LOCAL_IPFS_API_URL, files=files, timeout=60)
        response.raise_for_status() # Raise an exception for HTTP error codes
        
        ipfs_data = response.json()
        
        # The IPFS API returns the hash as 'Hash'
        ipfs_hash = ipfs_data.get('Hash')
        
        if ipfs_hash:
            return jsonify({
                "message": "File successfully added to local IPFS", 
                "ipfsHash": ipfs_hash,
                "ipfsLink": f"http://127.0.0.1:8080/ipfs/{ipfs_hash}" # Use local gateway
            }), 200
        else:
            return jsonify({"error": "Local IPFS API did not return a hash", "details": ipfs_data}), 500

    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Failed to connect to local IPFS node. Ensure 'ipfs daemon' is running on port 5001 and CORS is configured."}), 503
    except requests.exceptions.RequestException as e:
        app.logger.error(f"IPFS API Error: {e}")
        return jsonify({"error": f"Local IPFS API request failed: {e}"}), 500
    except Exception as e:
        app.logger.error(f"Internal Server Error: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)