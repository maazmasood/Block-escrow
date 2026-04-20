import time
import json
import os
from web3 import Web3
from eth_account import Account

# --- Configurations ---
ETH_RPC = "http://127.0.0.1:8545"
BNB_RPC = "http://127.0.0.1:8546"

RELAYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
relayer_account = Account.from_key(RELAYER_KEY)

w3_eth = Web3(Web3.HTTPProvider(ETH_RPC))
w3_bnb = Web3(Web3.HTTPProvider(BNB_RPC))

print(f"Relayer Active: {relayer_account.address}")
print(f"ETH Connected: {w3_eth.is_connected()}")
print(f"BNB Connected: {w3_bnb.is_connected()}")

# --- Load ABIs from Hardhat Artifacts ---
def load_abi(name):
    # Read from Hardhat's generated artifacts
    artifact_path = f"artifacts/static/contract/{name}.sol/{name}.json"
    if not os.path.exists(artifact_path):
        # Depending on how hardhat was configured, sometimes it is just "contract" or another folder.
        # Fallback to searching if we can't find it directly (Hardhat default):
        import glob
        matches = glob.glob(f"artifacts/**/{name}.sol/{name}.json", recursive=True)
        if matches:
            artifact_path = matches[0]

    try:
        with open(artifact_path, "r") as f:
            return json.load(f)["abi"]
    except Exception as e:
        print(f"Warning: ABI for {name} not found. Ensure contracts are compiled.")
        return []

# --- Contract Instances ---
# Load Addresses from config
def load_config():
    try:
        with open("static/contract/multichain_config.json", "r") as f:
            return json.load(f)
    except: return {}

config = load_config()
SOURCE_ADDRESS = config.get("ETH_SOURCE", "")
MIRROR_ADDRESS = config.get("BNB_MIRROR", "")
WETH_BNB = config.get("WETH_BNB", "0x0000000000000000000000000000000000000000")

def get_contracts():
    source_abi = load_abi("SupplyChainSource")
    mirror_abi = load_abi("SupplyChainMirror")
    
    source = w3_eth.eth.contract(address=SOURCE_ADDRESS, abi=source_abi) if SOURCE_ADDRESS else None
    mirror = w3_bnb.eth.contract(address=MIRROR_ADDRESS, abi=mirror_abi) if MIRROR_ADDRESS else None
    return source, mirror

def handle_eth_event(event):
    """When Buyer creates a multichain order on ETH, sync to BNB."""
    args = event['args']
    if not args['isMultichain']:
        return # Skip single-chain orders

    print(f"Detected Multichain Order on ETH: ID {args['id']}")
    
    source, mirror = get_contracts()
    if not mirror: return

    # --- ASSET TRANSLATION ---
    # If the user paid Native ETH (address 0), we want them to receive WETH on BNB.
    token_to_use = args['tokenAddress']
    if token_to_use == "0x0000000000000000000000000000000000000000":
        print(f"Translating Native ETH -> Wrapped ETH on BNB Chain...")
        token_to_use = WETH_BNB
    if not mirror: return

    # Sync to BNB
    nonce = w3_bnb.eth.get_transaction_count(relayer_account.address)
    tx = mirror.functions.syncFromETH(
        args['id'], args['buyer'], args['seller'], args['agent'], token_to_use, args['amount']
    ).build_transaction({
        'from': relayer_account.address,
        'nonce': nonce,
        'gas': 500000,
        'gasPrice': w3_bnb.eth.gas_price
    })
    
    try:
        signed = w3_bnb.eth.account.sign_transaction(tx, RELAYER_KEY)
        tx_hash = w3_bnb.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Synced to BNB Mirror: {tx_hash.hex()}")
    except Exception as e:
        print(f"Error syncing to BNB: {e}")

def handle_bnb_event(event, event_name):
    """When order completes or resolves on BNB, close the ETH Source record."""
    args = event['args']
    print(f"Detected {event_name} on BNB: Mirror ID {args['id']}")
    
    source, mirror = get_contracts()
    if not source: return

    # Since we unified IDs, args['id'] from BNB is identical to the eth_id
    eth_id = args['id']
    
    nonce = w3_eth.eth.get_transaction_count(relayer_account.address)
    tx = source.functions.relayerMarkBridged(eth_id).build_transaction({
        'from': relayer_account.address,
        'nonce': nonce,
        'gas': 200000,
        'gasPrice': w3_eth.eth.gas_price
    })
    
    try:
        signed = w3_eth.eth.account.sign_transaction(tx, RELAYER_KEY)
        tx_hash = w3_eth.eth.send_raw_transaction(signed.raw_transaction)
        print(f"ETH Record Closed via Bridging: {tx_hash.hex()}")
    except Exception as e:
        print(f"Error closing record on ETH: {e}")

# Maintain last synced blocks
last_synced_eth = 0
last_synced_bnb = 0

def main():
    global SOURCE_ADDRESS, MIRROR_ADDRESS, last_synced_eth, last_synced_bnb
    
    # Initialize block numbers on startup
    try:
        last_synced_eth = w3_eth.eth.block_number
        last_synced_bnb = w3_bnb.eth.block_number
    except: pass
    print("Relayer Monitoring...")
    while True:
        try:
            if not SOURCE_ADDRESS or not MIRROR_ADDRESS:
                try:
                    with open("static/contract/multichain_config.json", "r") as f:
                        config = json.load(f)
                        SOURCE_ADDRESS = config.get("ETH_SOURCE")
                        MIRROR_ADDRESS = config.get("BNB_MIRROR")
                    if not SOURCE_ADDRESS or not MIRROR_ADDRESS:
                        time.sleep(5)
                        continue
                except:
                    time.sleep(5)
                    continue

            source, mirror = get_contracts()
            
            # Use real block numbers to avoid missing events between polling
            current_eth = w3_eth.eth.block_number
            if current_eth > last_synced_eth:
                created_events = source.events.OrderCreated.get_logs(from_block=last_synced_eth+1, to_block=current_eth)
                for event in created_events:
                    handle_eth_event(event)
                last_synced_eth = current_eth

            current_bnb = w3_bnb.eth.block_number
            if current_bnb > last_synced_bnb:
                completed_events = mirror.events.OrderCompleted.get_logs(from_block=last_synced_bnb+1, to_block=current_bnb)
                for event in completed_events:
                    handle_bnb_event(event, "OrderCompleted")

                resolved_events = mirror.events.OrderResolved.get_logs(from_block=last_synced_bnb+1, to_block=current_bnb)
                for event in resolved_events:
                    handle_bnb_event(event, "OrderResolved")

                last_synced_bnb = current_bnb

            time.sleep(5)
        except Exception as e:
            print(f"Relayer Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
