import json
import time
from web3 import Web3
from eth_account import Account
from app import app
from database import db
from models import User

# --- Config & Setup ---
ETH_RPC = "http://127.0.0.1:8545"
BNB_RPC = "http://127.0.0.1:8546"
SOURCE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80" # Hardhat Account 0

w3_eth = Web3(Web3.HTTPProvider(ETH_RPC))
w3_bnb = Web3(Web3.HTTPProvider(BNB_RPC))
source_account = Account.from_key(SOURCE_KEY)

def load_config():
    with open("static/contract/multichain_config.json", "r") as f:
        return json.load(f)

config = load_config()
ERC20_ABI = [
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"transfer","outputs":[{"name":"","type":"bool"}],"type":"function"},
    {"inputs":[{"name":"to","type":"address"},{"name":"amount","type":"uint256"}],"name":"mint","outputs":[],"type":"function"}
]
ADMIN_ABI = [
    {"inputs":[{"name":"_admin","type":"address"},{"name":"_status","type":"bool"}],"name":"setAdminStatus","outputs":[],"type":"function"}
]

def fund_all():
    print(f"Starting funding & promotion run from {source_account.address}")
    
    with app.app_context():
        users = User.query.all()
        print(f"Found {len(users)} users to process.")
        
        for user in users:
            addr = Web3.to_checksum_address(user.wallet_address)
            print(f"\n--- Processing {user.name} ({addr}) - Role: {user.role} ---")
            
            # --- ADMIN PROMOTION ---
            if user.role == 'admin':
                try:
                    for chain_name, w3, cfg_key in [('ETH', w3_eth, 'ETH_SOURCE'), ('BNB', w3_bnb, 'BNB_MIRROR')]:
                        contract_addr = config.get(cfg_key)
                        if contract_addr:
                            contract = w3.eth.contract(address=contract_addr, abi=ADMIN_ABI)
                            nonce = w3.eth.get_transaction_count(source_account.address)
                            tx = contract.functions.setAdminStatus(addr, True).build_transaction({
                                'from': source_account.address, 'nonce': nonce,
                                'gas': 100000, 'gasPrice': w3.eth.gas_price
                            })
                            signed = w3.eth.account.sign_transaction(tx, SOURCE_KEY)
                            w3.eth.send_raw_transaction(signed.raw_transaction)
                            print(f"Promoted to On-Chain Admin on {chain_name}")
                except Exception as e: print(f"Admin Promo Fail: {e}")

            # 1. Native ETH (ETH Chain)
            try:
                tx = {'to': addr, 'value': w3_eth.to_wei(100, 'ether'), 'gas': 21000, 'gasPrice': w3_eth.eth.gas_price, 'nonce': w3_eth.eth.get_transaction_count(source_account.address)}
                signed = w3_eth.eth.account.sign_transaction(tx, SOURCE_KEY)
                w3_eth.eth.send_raw_transaction(signed.raw_transaction)
                print("Sent 100 Native ETH")
            except Exception as e: print(f"ETH Native Fail: {e}")

            # 2. Native BNB (BNB Chain)
            try:
                tx = {'to': addr, 'value': w3_bnb.to_wei(100, 'ether'), 'gas': 21000, 'gasPrice': w3_bnb.eth.gas_price, 'nonce': w3_bnb.eth.get_transaction_count(source_account.address)}
                signed = w3_bnb.eth.account.sign_transaction(tx, SOURCE_KEY)
                w3_bnb.eth.send_raw_transaction(signed.raw_transaction)
                print("Sent 100 Native BNB")
            except Exception as e: print(f"BNB Native Fail: {e}")

            # 3. USDT (Both)
            try:
                for chain_name, w3, token_key in [('ETH', w3_eth, 'USDT_ETH'), ('BNB', w3_bnb, 'USDT_BNB')]:
                    token_addr = config.get(token_key)
                    if token_addr:
                        contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
                        # Use MINT instead of transfer so we never run out of funds
                        tx = contract.functions.mint(addr, w3.to_wei(100, 'ether')).build_transaction({
                            'from': source_account.address, 'nonce': w3.eth.get_transaction_count(source_account.address),
                            'gas': 100000, 'gasPrice': w3.eth.gas_price
                        })
                        signed = w3.eth.account.sign_transaction(tx, SOURCE_KEY)
                        w3.eth.send_raw_transaction(signed.raw_transaction)
                        print(f"Minted 100 USDT on {chain_name}")
            except Exception as e: print(f"USDT Fail: {e}")

            # 4. WETH (BNB Chain)
            try:
                token_addr = config.get('WETH_BNB')
                if token_addr:
                    contract = w3_bnb.eth.contract(address=token_addr, abi=ERC20_ABI)
                    # Use MINT instead of transfer
                    tx = contract.functions.mint(addr, w3_bnb.to_wei(100, 'ether')).build_transaction({
                        'from': source_account.address, 'nonce': w3_bnb.eth.get_transaction_count(source_account.address),
                        'gas': 100000, 'gasPrice': w3_bnb.eth.gas_price
                    })
                    signed = w3_bnb.eth.account.sign_transaction(tx, SOURCE_KEY)
                    w3_bnb.eth.send_raw_transaction(signed.raw_transaction)
                    print(f"Minted 100 WETH on BNB Chain")
            except Exception as e: print(f"WETH Fail: {e}")

    print("\nFunding complete!")

if __name__ == "__main__":
    fund_all()
