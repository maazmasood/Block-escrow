import time
import json
from web3 import Web3
from eth_account import Account

# --- Configurations ---
ETH_RPC = "http://127.0.0.1:8545"
BNB_RPC = "http://127.0.0.1:8546"

# For local Hardhat, account 0 is usually:
# 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
# Private key: 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80
RELAYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
relayer_account = Account.from_key(RELAYER_KEY)

w3_eth = Web3(Web3.HTTPProvider(ETH_RPC))
w3_bnb = Web3(Web3.HTTPProvider(BNB_RPC))

print(f"Relayer Active: {relayer_account.address}")
print(f"ETH Connected: {w3_eth.is_connected()}")
print(f"BNB Connected: {w3_bnb.is_connected()}")

# --- Load ABIs ---
def load_abi(name):
    # This assumes we will generate these files during deployment
    try:
        with open(f"static/contract/{name}_abi.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {name}_abi.json not found. Run deployment first.")
        return []

# --- Contract Instances ---
# Addresses will be updated after deployment
SOURCE_ADDRESS = "" 
MIRROR_ADDRESS = ""

def get_contracts():
    source_abi = load_abi("EscrowSource")
    mirror_abi = load_abi("EscrowMirror")
    
    source = w3_eth.eth.contract(address=SOURCE_ADDRESS, abi=source_abi) if SOURCE_ADDRESS else None
    mirror = w3_bnb.eth.contract(address=MIRROR_ADDRESS, abi=mirror_abi) if MIRROR_ADDRESS else None
    return source, mirror

def handle_eth_event(event):
    """When User A funds on ETH, initialize on BNB."""
    args = event['args']
    print(f"Detected Funding on ETH: ID {args['id']}")
    
    source, mirror = get_contracts()
    if not mirror: return

    # Sync to BNB
    nonce = w3_bnb.eth.get_transaction_count(relayer_account.address)
    tx = mirror.functions.syncFromETH(
        args['id'], args['buyer'], args['seller'], args['agent'], args['amount'], args['ipfsHash']
    ).build_transaction({
        'from': relayer_account.address,
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3_bnb.eth.gas_price
    })
    
    signed = w3_bnb.eth.account.sign_transaction(tx, RELAYER_KEY)
    tx_hash = w3_bnb.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Synced to BNB: {tx_hash.hex()}")

def handle_bnb_event(event):
    """When User B confirms on BNB, notify ETH."""
    args = event['args']
    print(f"Detected Confirmation on BNB: Mirror ID {args['id']}")
    
    source, mirror = get_contracts()
    if not source: return

    # In our simplified USDT flow, we release on BNB immediately. 
    # But we still notify ETH to "close" the source record.
    eth_id = mirror.functions.escrows(args['id']).call()[0]
    
    nonce = w3_eth.eth.get_transaction_count(relayer_account.address)
    tx = source.functions.relayerMarkBridged(eth_id).build_transaction({
        'from': relayer_account.address,
        'nonce': nonce,
        'gas': 200000,
        'gasPrice': w3_eth.eth.gas_price
    })
    
    signed = w3_eth.eth.account.sign_transaction(tx, RELAYER_KEY)
    tx_hash = w3_eth.eth.send_raw_transaction(signed.raw_transaction)
    print(f"ETH Record Closed: {tx_hash.hex()}")

def main():
    global SOURCE_ADDRESS, MIRROR_ADDRESS
    # In a real setup, load these from a config file updated by deployment
    # For now, we will wait for them to be set or manually entered
    
    print("Relayer Monitoring...")
    while True:
        try:
            # Check if addresses are set
            if not SOURCE_ADDRESS or not MIRROR_ADDRESS:
                # Try to load from a generated config
                try:
                    with open("static/contract/multichain_config.json", "r") as f:
                        config = json.load(f)
                        SOURCE_ADDRESS = config.get("ETH_SOURCE")
                        MIRROR_ADDRESS = config.get("BNB_MIRROR")
                except:
                    time.sleep(5)
                    continue

            source, mirror = get_contracts()
            
            # Poll for events (simplified for demo)
            # In production, use filters or WebSockets
            funded_events = source.events.EscrowFunded.get_logs(from_block='latest')
            for event in funded_events:
                handle_eth_event(event)

            confirmed_events = mirror.events.UserBConfirmed.get_logs(from_block='latest')
            for event in confirmed_events:
                handle_bnb_event(event)

            time.sleep(5)
        except Exception as e:
            print(f"Relayer Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
