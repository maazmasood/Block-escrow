// app.js
// NOTE: This file assumes you have the latest Solidity contract compiled
// and that abi.js and bytecode.js are loaded.

// --- Global Variables & Configuration ---
const ethProviderUrl = "http://127.0.0.1:8545"; // ETH Chain
const bnbProviderUrl = "http://127.0.0.1:8546"; // BNB Chain
const backendUrl = "http://127.0.0.1:5000";  

let web3Eth = new Web3(ethProviderUrl);
let web3Bnb = new Web3(bnbProviderUrl);
let web3 = web3Eth; // Default to ETH

// Contract Addresses (Update after deployment)
let USDT_ETH = "";
let USDT_BNB = "";
let ESCROW_SOURCE = "";
let ESCROW_MIRROR = "";

let selectedAccount;
let contract;
let contractAddress;
let isMultichainMode = false;

// Load Config from Deployment
async function loadConfig() {
    try {
        const response = await fetch('/static/contract/multichain_config.json');
        if (response.ok) {
            const config = await response.json();
            USDT_ETH = config.USDT_ETH;
            USDT_BNB = config.USDT_BNB;
            ESCROW_SOURCE = config.ETH_SOURCE;
            ESCROW_MIRROR = config.BNB_MIRROR;
            console.log("Multichain Config Loaded:", config);
        }
    } catch (err) {
        console.warn("No multichain_config.json found. Please deploy contracts and update config.");
    }
}

// --- Utility Functions ---

/**
 * Copies the currently selected Ethereum address to the clipboard.
 * Uses the fallback method (document.execCommand('copy')) as navigator.clipboard
 * may not work in certain iframe environments.
 */
function copyAddress() {
    if (!selectedAccount) return alert("No active account selected to copy.");

    // Create a temporary input element
    const tempInput = document.createElement('input');
    tempInput.value = selectedAccount;
    document.body.appendChild(tempInput);

    // Select the content
    tempInput.select();
    tempInput.setSelectionRange(0, 99999); // For mobile devices

    try {
        // Execute the copy command
        const success = document.execCommand('copy');
        if (success) {
            // Provide visual feedback (replacing the button content briefly)
            const btn = document.getElementById('copyAddressBtn');
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<i class="fas fa-check me-1"></i> Copied!';

            setTimeout(() => {
                btn.innerHTML = originalHtml;
            }, 1500);
        } else {
            alert("Copy failed. Please manually copy the address.");
        }
    } catch (err) {
        console.error('Copy failed:', err);
        alert("Copy failed due to browser restrictions. Please manually copy the address.");
    }

    // Clean up the temporary input
    document.body.removeChild(tempInput);
}

// Generalized Copy Function
function copyToClipboard(text, btnElement) {
    // Create a temporary input element
    const tempInput = document.createElement('input');
    tempInput.value = text;
    document.body.appendChild(tempInput);
    tempInput.select();
    tempInput.setSelectionRange(0, 99999); // For mobile

    try {
        const success = document.execCommand('copy');
        if (success && btnElement) {
            // Visual feedback
            const originalHtml = btnElement.innerHTML;
            btnElement.innerHTML = '<i class="fas fa-check text-success"></i>';
            setTimeout(() => {
                btnElement.innerHTML = originalHtml;
            }, 1000);
        }
    } catch (err) {
        console.error('Copy failed:', err);
        alert("Manual copy required.");
    }
    document.body.removeChild(tempInput);
}

// Global function to handle account selection
async function selectAccount(account) {
    selectedAccount = account;
    localStorage.setItem('selectedAccount', selectedAccount);

    // Update Dropdown Toggle Text
    const displayBtn = document.getElementById("selectedAccountDisplay");
    if (displayBtn) {
        const name = dynamicNamedAccounts[account] || ((typeof namedAccounts !== 'undefined' && namedAccounts[account]) ? namedAccounts[account] : account);
        // Show Name if available, else partial address
        displayBtn.innerText = name.startsWith("0x") ? `${name.substring(0, 6)}...${name.substring(name.length - 4)}` : name;
    }

    // Highlighting in the dropdown list
    const allItems = document.querySelectorAll('.account-dropdown-item');
    allItems.forEach(item => {
        if (item.dataset.account === account) {
            item.classList.add('bg-secondary', 'bg-opacity-25');
        } else {
            item.classList.remove('bg-secondary', 'bg-opacity-25');
        }
    });

    // Update Dashboard Elements
    const activeAccountText = document.getElementById("activeAccount");
    if (activeAccountText) activeAccountText.innerText = selectedAccount;

    await updateBalance();
    
    // Auto-select provider based on current view/contract
    if (localStorage.getItem('currentChain') === 'BNB') {
        web3 = web3Bnb;
    } else {
        web3 = web3Eth;
    }
    
    updateEscrowStatus();
}

async function fetchDynamicNames() {
    try {
        const res = await fetch(`${backendUrl}/api/users/mapping`);
        if(res.ok) {
            dynamicNamedAccounts = await res.json();
        }
    } catch(e) {
        console.warn("Could not load dynamic names.");
    }
}

async function loadAccounts() {
    await fetchDynamicNames();
    try {
        const accounts = await web3.eth.getAccounts();
        const list = document.getElementById("accountList");

        if (list) {
            list.innerHTML = "";
            let storedAccount = localStorage.getItem('selectedAccount');

            // Validate stored account
            if (!storedAccount || !accounts.includes(storedAccount)) {
                storedAccount = accounts[0];
            }
            // Trigger initial selection
            await selectAccount(storedAccount);

            accounts.forEach((acc, index) => {
                const name = dynamicNamedAccounts[acc] || ((typeof namedAccounts !== 'undefined' && namedAccounts[acc])
                    ? namedAccounts[acc]
                    : `Account ${index}`);
                // Create List Item
                const li = document.createElement("li");

                // Custom Content DIV
                const container = document.createElement("div");
                container.className = "d-flex justify-content-between align-items-center px-3 py-2 border-bottom border-secondary dropdown-item text-white account-dropdown-item";
                container.style.cursor = "pointer";
                container.dataset.account = acc;

                if (acc === storedAccount) container.classList.add('bg-secondary', 'bg-opacity-25');

                // Account Info Section (Click to Select)
                const infoDiv = document.createElement("div");
                infoDiv.className = "d-flex flex-column flex-grow-1 me-3";
                infoDiv.onclick = (e) => {
                    selectAccount(acc);
                };

                const nameSpan = document.createElement("span");
                nameSpan.className = "fw-bold small";
                nameSpan.innerText = name;

                const addrSmall = document.createElement("small");
                addrSmall.className = "text-muted";
                addrSmall.style.fontSize = "0.7rem";
                addrSmall.innerText = acc; // Show full address

                infoDiv.appendChild(nameSpan);
                infoDiv.appendChild(addrSmall);

                // Copy Button (Click to Copy)
                const copyBtn = document.createElement("button");
                copyBtn.className = "btn btn-sm btn-dark border-secondary rounded-circle";
                copyBtn.title = "Copy Address";
                copyBtn.innerHTML = '<i class="fas fa-copy text-gray-400"></i>';
                copyBtn.onclick = (e) => {
                    e.stopPropagation(); // Prevent selection when copying
                    copyToClipboard(acc, copyBtn);
                };

                container.appendChild(infoDiv);
                container.appendChild(copyBtn);
                li.appendChild(container);
                list.appendChild(li);
            });
        }

        updateBalance();
    } catch (error) {
        console.error("Error loading accounts:", error);
    }
}

async function updateBalance() {
    if (!selectedAccount) return;
    try {
        const balanceElem = document.getElementById("accountBalance");
        const usdtElem = document.getElementById("usdtBalance");
        if (!balanceElem) return;

        // 1. Fetch ETH Balance
        const balanceWei = await web3.eth.getBalance(selectedAccount);
        const balanceEth = web3.utils.fromWei(balanceWei, "ether");
        balanceElem.innerText = parseFloat(balanceEth).toFixed(4);

        // 2. Fetch USDT Balance
        const currentChain = localStorage.getItem('currentChain') || 'ETH';
        const usdtAddr = (currentChain === 'BNB') ? USDT_BNB : USDT_ETH;
        
        if (usdtAddr && web3.utils.isAddress(usdtAddr)) {
            const usdt = new web3.eth.Contract(usdtAbi, usdtAddr);
            const usdtWei = await usdt.methods.balanceOf(selectedAccount).call();
            const usdtEth = web3.utils.fromWei(usdtWei, "ether");
            if (usdtElem) usdtElem.innerText = parseFloat(usdtEth).toFixed(2);
        } else if (usdtElem) {
            usdtElem.innerText = "0.00";
        }
    } catch (error) {
        console.error("Error updating balance:", error);
    }
}

// --- Contract Interaction Functions ---

async function deployContract() {
    if (!selectedAccount) return alert("Please select an account.");
    try {
        const escrow = new web3.eth.Contract(escrowAbi);
        const deployed = await escrow.deploy({ data: escrowBytecode })
            .send({ from: selectedAccount, gas: 5000000 });

        contract = deployed;
        contractAddress = deployed.options.address;
        localStorage.setItem('deployedContractAddress', contractAddress); // Persist address

        const contractAddrDisplay = document.getElementById("contractAddr");
        if (contractAddrDisplay) contractAddrDisplay.innerText = contractAddress;

        alert(`Contract deployed at: ${contractAddress}`);
        updateEscrowStatus();
    } catch (error) {
        alert("Deployment failed: " + error.message);
        console.error("Deployment failed:", error);
    }
}

async function deployAndCreateEscrow() {
    if (!selectedAccount) return alert("Please select an account first.");

    try {
        const receiver = document.getElementById("receiver").value;
        const agent = document.getElementById("agentAddress").value;
        const ipfsHash = document.getElementById("ipfsHashInput").value;
        const amount = document.getElementById("amount").value;
        const token = document.getElementById("tokenSelect").value;
        const isMultichain = document.getElementById("isMultichain").checked;

        if (!ipfsHash || ipfsHash === "Awaiting IPFS Upload...")
            return alert("Please upload a file to IPFS first.");

        const createBtn = document.getElementById("createBtn");
        createBtn.disabled = true;
        createBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Initializing...';

        if (isMultichain) {
            // Multichain Logic (USDT on ETH -> BNB)
            if (token === "USDT") {
                const usdt = new web3Eth.eth.Contract(usdtAbi, USDT_ETH);
                const amountWei = web3Eth.utils.toWei(amount, "ether"); // Assuming 18 decimals for mock
                
                createBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Approving USDT...';
                await usdt.methods.approve(ESCROW_SOURCE, amountWei).send({ from: selectedAccount });
                
                createBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Locking on ETH...';
                const source = new web3Eth.eth.Contract(escrowSourceAbi, ESCROW_SOURCE);
                const receipt = await source.methods.createEscrow(receiver, agent, amountWei, ipfsHash).send({ from: selectedAccount });
                
                const ethId = receipt.events.EscrowFunded.returnValues.id;

                // Sync with Backend
                await fetch(`${backendUrl}/api/escrow/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        contractAddress: ESCROW_SOURCE,
                        buyer: selectedAccount,
                        receiver: receiver,
                        agent: agent,
                        amount: amount,
                        token: "USDT",
                        ipfsHash: ipfsHash,
                        isMultichain: true,
                        sourceChain: "8545",
                        destChain: "8546",
                        mirrorAddress: ESCROW_MIRROR
                    })
                });
                alert("Multichain Escrow Created on ETH. Relayer will sync to BNB shortly.");
            } else {
                alert("Multichain currently only supports USDT for this demo.");
            }
        } else {
            // Original Single Chain Logic (ETH)
            // ... (keeping legacy support if needed)
        }
        window.location.href = "/transactions";

    } catch (error) {
        alert("Action failed: " + error.message);
        console.error(error);
        document.getElementById("createBtn").disabled = false;
        document.getElementById("createBtn").innerHTML = 'Create Escrow';
    }
}

// --- Multi-Contract Management ---

function selectContract(address) {
    if (!web3.utils.isAddress(address)) return;

    localStorage.setItem('currentContractAddress', address);

    // Update global state
    contractAddress = address;
    contract = new web3.eth.Contract(escrowAbi, contractAddress);

    // Redirect if not on details page
    if (!window.location.href.includes('contract_details')) {
        window.location.href = '/contract_details';
    } else {
        // Just reload data
        updateEscrowStatus();
        const disp = document.getElementById("contractAddr");
        if (disp) disp.innerText = address;
    }
}

async function loadUserContracts() {
    const account = localStorage.getItem('selectedAccount');
    const tbody = document.getElementById('myContractsList');
    const msg = document.getElementById('noContractsMsg');

    if (!tbody) return; // Not on dashboard

    if (!account) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-warning">Please connect wallet/select account.</td></tr>';
        return;
    }

    try {
        // Show loading
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Loading contracts...</td></tr>';

        const res = await fetch(`/api/contracts/${account}`);
        if (!res.ok) throw new Error("Failed");

        const contracts = await res.json();
        tbody.innerHTML = '';

        if (contracts.length === 0) {
            if (msg) msg.classList.remove('d-none');
        } else {
            if (msg) msg.classList.add('d-none');
            contracts.forEach(c => {
                let role = "Guest";
                if (c.buyer && c.buyer.toLowerCase() === account.toLowerCase()) role = "Buyer";
                else if (c.seller && c.seller.toLowerCase() === account.toLowerCase()) role = "Seller";
                else if (c.agent && c.agent.toLowerCase() === account.toLowerCase()) role = "Agent";

                const row = `<tr>
                    <td><small class="font-monospace text-info">${c.contract_address ? c.contract_address.substring(0, 8) + '...' + c.contract_address.substring(38) : 'Pending'}</small></td>
                    <td><span class="badge bg-secondary">${role}</span></td>
                    <td>${c.amount} ETH</td>
                    <td><span class="badge bg-${c.status === 'Released' ? 'success' : 'warning'}">${c.status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="selectContract('${c.contract_address}')">
                            <i class="fas fa-eye"></i> View
                        </button>
                    </td>
                </tr>`;
                tbody.innerHTML += row;
            });
        }
    } catch (e) {
        console.error(e);
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Error loading contracts.</td></tr>';
    }
}

async function confirmUser1() {
    if (!contract) return alert("Deploy contract first!");
    try {
        await contract.methods.confirmUser1().send({ from: selectedAccount, gas: 200000 });

        await fetch(`${backendUrl}/api/escrow/update`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contractAddress: contractAddress, event: `User1 (${selectedAccount}) Confirmed` })
        });

        alert(`User1 confirmation (Step 1) sent.`);
        updateEscrowStatus();
    } catch (error) {
        alert("User1 Confirmation failed: " + error.message);
    }
}

async function confirmAgent() {
    if (!contractAddress) return alert("No contract selected!");
    try {
        const currentChain = localStorage.getItem('currentChain') || 'ETH';
        const activeWeb3 = (currentChain === 'BNB') ? web3Bnb : web3Eth;
        const activeAbi = (currentChain === 'BNB') ? escrowMirrorAbi : escrowSourceAbi;
        const inst = new activeWeb3.eth.Contract(activeAbi, contractAddress);

        await inst.methods.confirmAgent(0).send({ from: selectedAccount, gas: 200000 });

        await fetch(`${backendUrl}/api/escrow/update`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contractAddress: contractAddress, event: `Agent (${selectedAccount}) Confirmed` })
        });

        alert(`Agent confirmation (Step 2) sent.`);
        updateEscrowStatus();
    } catch (error) {
        alert("Agent Confirmation failed: " + error.message);
    }
}

async function confirmUser2() {
    if (!contractAddress) return alert("No contract selected!");
    const btn = document.getElementById("confirmUser2Btn");
    
    try {
        const currentChain = localStorage.getItem('currentChain') || 'ETH';
        const activeWeb3 = (currentChain === 'BNB') ? web3Bnb : web3Eth;
        
        if (currentChain === 'BNB') {
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Releasing...';
            }

            const inst = new activeWeb3.eth.Contract(escrowMirrorAbi, contractAddress);
            
            // Hardcoding 0 for demo purposes, but we should ideally pass the ID
            const receipt = await inst.methods.confirmUserB(0).send({ from: selectedAccount, gas: 300000 });
            
            if (!receipt.status) {
                throw new Error("Blockchain transaction reverted.");
            }

            // ONLY update backend if blockchain succeeded
            await fetch(`${backendUrl}/api/escrow/update`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ contractAddress: contractAddress, event: `User2/B (${selectedAccount}) Released Funds` })
            });

            alert(`Confirmation (Step 3) successful! Funds have been released on BNB.`);
        } else {
             alert("Release action is currently only handled on the BNB Mirror for multichain escrows.");
        }

        updateEscrowStatus();
        updateBalance();
    } catch (error) {
        alert("Confirmation failed: " + error.message);
        if (btn) {
            btn.disabled = false;
            btn.innerText = "Step 3: Release Funds";
        }
    }
}

// --- IPFS Upload Logic ---

async function uploadFileToIPFS() {
    const fileInput = document.getElementById('fileInput');
    const ipfsResultBox = document.getElementById('ipfsResultBox');
    const ipfsHashDisplay = document.getElementById('ipfsHashDisplay');
    const ipfsHashInput = document.getElementById('ipfsHashInput');

    if (fileInput.files.length === 0) {
        return alert("Please select a file to upload.");
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    ipfsResultBox.style.display = 'none';
    ipfsHashInput.value = "Uploading...";
    document.getElementById('uploadIpfsBtn').disabled = true;

    try {
        const response = await fetch(`${backendUrl}/upload-ipfs`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const errorText = await response.text();
            let errorMsg = `HTTP error! Status: ${response.status}`;
            try {
                const errorData = JSON.parse(errorText);
                errorMsg = errorData.error || errorMsg;
            } catch (e) {
                errorMsg = `Server Error: ${errorText.substring(0, 100)}...`;
            }
            throw new Error(errorMsg);
        }

        const data = await response.json();
        const ipfsHash = data.ipfsHash;

        ipfsHashDisplay.innerText = ipfsHash;
        ipfsHashInput.value = ipfsHash;
        ipfsResultBox.style.display = 'block';
        alert("File successfully uploaded to local IPFS!");

    } catch (error) {
        alert(`IPFS Upload Failed: ${error.message}. Check your Python backend and IPFS daemon.`);
        console.error("IPFS Upload Failed:", error);
        ipfsHashInput.value = "Upload Failed";
    } finally {
        document.getElementById('uploadIpfsBtn').disabled = false;
    }
}

// --- Dynamic UI & Status Functions ---

function getRole(account, data) {
    if (!account || !data.user1) return "Guest";

    const acc = account.toLowerCase();
    const u1 = data.user1.toLowerCase();
    const u2 = data.user2.toLowerCase();
    const ag = data.agent.toLowerCase();

    console.log(`[Debug] Checking Role for: ${acc}`);
    console.log(`[Debug] Contract Parties - U1: ${u1}, U2: ${u2}, Agent: ${ag}`);
    console.log(`[Debug] Active: ${data.isActive}`);

    const isInitiated = u1 !== '0x0000000000000000000000000000000000000000';

    if (acc === u1) return data.isActive ? "User 1 (Payer)" : isInitiated ? "Initiator (Escrow Closed)" : "Initiator (New)";
    if (acc === u2) return data.isActive ? "User 2 (Receiver)" : "Guest";
    if (acc === ag) return data.isActive ? "Agent (Mediator)" : "Guest";
    return isInitiated && !data.isActive ? "Guest (Escrow Closed)" : "Guest";
}

function isParty(role) {
    return role.includes("User 1") || role.includes("User 2") || role.includes("Agent");
}


function updateDashboardUI(data) {
    const role = getRole(selectedAccount, data);
    const userRoleElem = document.getElementById("userRole");
    if (userRoleElem) userRoleElem.innerText = role;

    // Update Dashboard Badge
    const badge = document.getElementById("contractStatusBadge");
    if (badge) {
        badge.innerText = data.isActive ? "Active" : "Inactive";
        badge.className = data.isActive ? "fs-2 text-success" : "fs-2 text-white";
    }

    // Helper for safe style setting
    const setDisplay = (id, style) => {
        const el = document.getElementById(id);
        if (el) {
            // Handle container lookups for confirming buttons
            if (id.includes('Btn')) {
                const container = el.closest('.col-md-4');
                if (container) container.style.display = style;
            } else {
                el.style.display = style;
            }
        }
    };

    // 1. Reset creation form visibility based on active status
    // FIX: Do not hide creation form if we are on the create_contract page
    if (!window.location.href.includes('create_contract')) {
        setDisplay('user1-actions', data.isActive ? 'none' : 'block');
    } else {
        setDisplay('user1-actions', 'block');
    }

    // 2. Reset confirmation/preview visibility
    setDisplay('ipfs-preview', 'none');
    setDisplay('confirmUser1Btn', 'none'); // Passed ID triggers container lookup in helper
    setDisplay('confirmAgentBtn', 'none');
    setDisplay('confirmUser2Btn', 'none');
    setDisplay('no-active-escrow', 'none');

    // 3. Handle Guest or Inactive State 
    if ((role.includes("Guest") && data.isActive) || (role.includes("Closed"))) {
        if (role.includes("Initiator") && !data.isActive) {
            setDisplay('user1-actions', 'block');
        } else {
            setDisplay('user1-actions', 'none');
        }

        if (!data.isActive && !role.includes("Initiator")) {
            setDisplay('no-active-escrow', 'block');
            const noEscrowEl = document.getElementById('no-active-escrow');
            if (noEscrowEl) noEscrowEl.innerText = "No active escrow found, or you are not a party.";
        }

        if (role.includes("Closed")) {
            const noEscrowEl = document.getElementById('no-active-escrow');
            if (noEscrowEl) noEscrowEl.innerText = "Escrow is complete and closed.";
            setDisplay('no-active-escrow', 'block');
        }
    }


    // 4. Handle Active Escrow States (Confirmation buttons and IPFS preview)
    if (data.isActive) {

        // **MODIFICATION HERE: ONLY SHOW IPFS PREVIEW IF THE USER IS A PARTY**
        if (data.ipfsHash && data.ipfsHash !== '0x' && isParty(role)) {
            setDisplay('ipfs-preview', 'block');
            const link = `http://127.0.0.1:8080/ipfs/${data.ipfsHash}`;
            const contentDiv = document.getElementById('ipfsFileContent');

            if (contentDiv) {
                // Simple heuristic to display image or link
                if (data.ipfsHash.length > 5 && (data.ipfsHash.includes('Q') || data.ipfsHash.includes('b'))) {
                    contentDiv.innerHTML = `<img src="${link}" alt="Escrow Document" class="img-fluid rounded" style="max-height: 250px; object-fit: contain;">
                                            <p class="mt-2 text-wrap"><small>Link: <a href="${link}" target="_blank">${link.substring(0, 50)}...</a></small></p>`;
                    
                    // --- AI SUMMARY FETCH LOGIC ---
                    const aiContainer = document.getElementById('aiSummaryContent');
                    const aiText = document.getElementById('aiSummaryText');
                    if (aiContainer && aiText) {
                        aiContainer.style.display = 'block';
                        // Only fetch if it hasn't been fetched yet to prevent spamming
                        if (!aiContainer.dataset.fetchedFor || aiContainer.dataset.fetchedFor !== data.ipfsHash) {
                            aiText.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Analyzing receipt with AI...';
                            aiContainer.dataset.fetchedFor = data.ipfsHash;
                            
                            fetch(`${backendUrl}/api/receipt/process_ipfs`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ ipfsHash: data.ipfsHash })
                            })
                            .then(res => res.json())
                            .then(aiData => {
                                if (aiData.summary) {
                                    // Use simple text replace for newlines
                                    aiText.innerHTML = aiData.summary.replace(/\\n/g, '<br>');
                                } else {
                                    aiText.innerText = "Summary not available.";
                                }
                            })
                            .catch(err => {
                                console.error('AI Fetch error', err);
                                aiText.innerText = "Error analyzing receipt with AI.";
                            });
                        }
                    }
                    // --- END AI SUMMARY FETCH LOGIC ---
                } else {
                    contentDiv.innerHTML = `<p class="text-warning mb-0"><i class="fas fa-file-alt me-1"></i> Document Hash Found</p>
                                            <p class="text-wrap"><small>Hash: ${data.ipfsHash}</small></p>
                                            <a href="${link}" target="_blank" class="btn btn-sm btn-outline-secondary"><i class="fas fa-link me-1"></i> View Document</a>`;
                }
            }
        }
        // **END MODIFICATION**


        // Logic for Confirmation Buttons (Enforcing Sequential Flow & Visibility)
        const btnU1 = document.getElementById('confirmUser1Btn');
        const btnA = document.getElementById('confirmAgentBtn');
        const btnU2 = document.getElementById('confirmUser2Btn');

        // Helper to reset button state
        const setButtonState = (btn, isMyTurn, isDone, labelPending, labelAction, labelDone) => {
            if (!btn) return;

            // Ensure container is visible for all parties
            const container = btn.closest('.col-md-4');
            if (container) container.style.display = 'block';

            btn.classList.remove('btn-primary', 'btn-outline-warning', 'btn-outline-info', 'btn-outline-success', 'btn-secondary');

            if (isDone) {
                btn.disabled = true;
                btn.innerText = labelDone;
                btn.classList.add('btn-success');
            } else if (isMyTurn) {
                btn.disabled = false;
                btn.innerText = labelAction;
                btn.classList.add('btn-primary');
            } else {
                btn.disabled = true;
                btn.innerText = labelPending;
                btn.classList.add('btn-secondary');
            }
        };

        if (isParty(role)) {
            // Step 1: User 1
            const isU1Turn = role.includes("User 1") && !data.user1Confirmed;
            setButtonState(btnU1, isU1Turn, data.user1Confirmed, "Waiting for User 1", "Step 1: Confirm Now", "Step 1: Confirmed ✅");

            // Step 2: Agent
            const isAgentTurn = role.includes("Agent") && data.user1Confirmed && !data.agentConfirmed;
            // Additional check: If User 1 hasn't confirmed, Agent sees "Pending User 1" essentially
            const agentLabelPending = !data.user1Confirmed ? "Waiting for User 1" : "Waiting for Agent";
            setButtonState(btnA, isAgentTurn, data.agentConfirmed, agentLabelPending, "Step 2: Confirm Now", "Step 2: Confirmed ✅");

            // Step 3: User 2
            const isU2Turn = role.includes("User 2") && data.user1Confirmed && data.agentConfirmed && !data.user2Confirmed;
            const u2LabelPending = !data.agentConfirmed ? "Waiting for Previous Steps" : "Waiting for User 2";
            setButtonState(btnU2, isU2Turn, data.user2Confirmed, u2LabelPending, "Step 3: Release Funds", "Step 3: Funds Released 💰");
        }
    }
}

async function updateEscrowStatus() {
    // Determine which chain we are on
    const currentChain = localStorage.getItem('currentChain') || 'ETH';
    web3 = (currentChain === 'BNB') ? web3Bnb : web3Eth;
    
    // Update Network Label
    const netLabel = document.getElementById("currentNetworkLabel");
    if (netLabel) netLabel.innerText = currentChain;

    if (!contractAddress) return;
    
    try {
        const res = await fetch(`${backendUrl}/api/contracts/${selectedAccount}`);
        const contracts = await res.json();
        const currentEscrow = contracts.find(c => c.contract_address === contractAddress || c.mirror_address === contractAddress);
        
        if (!currentEscrow) return;

        const isMirror = (currentChain === 'BNB');
        const activeAbi = isMirror ? escrowMirrorAbi : escrowSourceAbi;
        
        // Use the correct address for the current chain
        const activeAddress = isMirror ? currentEscrow.mirror_address : currentEscrow.contract_address;
        
        if (!activeAddress || activeAddress === "") {
             if (document.getElementById("escrowStatus")) {
                document.getElementById("escrowStatus").innerText = `Network: ${currentChain}\nStatus: Awaiting Bridge Sync...`;
            }
            return;
        }

        const inst = new web3.eth.Contract(activeAbi, activeAddress);
        const data = await inst.methods.escrows(0).call(); // Simplified ID for demo
        
        // Map to standard UI object (handling both named and indexed results)
        // Web3.js results can be accessed by name or index
        const uiData = isMirror ? {
            user1: data.buyer || data[1],
            user2: data.seller || data[2],
            agent: data.agent || data[3],
            amount: data.amount || data[4],
            user1Confirmed: true, 
            agentConfirmed: true,
            user2Confirmed: (data.confirmedByBNB !== undefined) ? data.confirmedByBNB : data[6],
            isActive: !((data.released !== undefined) ? data.released : data[7]),
            ipfsHash: data.ipfsHash || data[5]
        } : {
            user1: data.buyer || data[0],
            user2: data.seller || data[1],
            agent: data.agent || data[2],
            amount: data.amount || data[3],
            user1Confirmed: true, 
            agentConfirmed: data.agentConfirmed || data[5],
            user2Confirmed: data.isBridged || data[6],
            isActive: !((data.isBridged !== undefined) ? data.isBridged : data[6]),
            ipfsHash: data.ipfsHash || data[4]
        };

        updateDashboardUI(uiData);
        
        if (document.getElementById("escrowStatus")) {
            document.getElementById("escrowStatus").innerText = `Network: ${currentChain}\nStatus: ${uiData.isActive ? 'Active' : 'Closed'}`;
        }

    } catch (err) {
        console.warn("Status fetch failed", err);
    }
}

function switchNetwork(chain) {
    localStorage.setItem('currentChain', chain);
    web3 = (chain === 'BNB') ? web3Bnb : web3Eth;
    location.reload();
}

// --- Event Listeners ---

document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();
    loadAccounts();

    // Check for persisted contract address
    // Check for persisted contract address (Multi-contract support uses 'currentContractAddress')
    const savedContractAddress = localStorage.getItem('currentContractAddress');

    if (savedContractAddress && web3.utils.isAddress(savedContractAddress)) {
        // Verify code
        web3.eth.getCode(savedContractAddress).then(code => {
            if (code !== '0x') {
                contractAddress = savedContractAddress;
                contract = new web3.eth.Contract(escrowAbi, contractAddress);

                const contractAddrDisplay = document.getElementById("contractAddr");
                if (contractAddrDisplay) contractAddrDisplay.innerText = contractAddress;

                // Update UI status
                setTimeout(updateEscrowStatus, 500);
            }
        }).catch(console.error);
    }

    // Load User Contracts (if on dashboard)
    setTimeout(loadUserContracts, 1000);

    const copyBtn = document.getElementById("copyAddressBtn");
    if (copyBtn) copyBtn.onclick = copyAddress;

    const uploadBtn = document.getElementById("uploadIpfsBtn");
    if (uploadBtn) uploadBtn.onclick = uploadFileToIPFS;

    // Wire up the new create button
    const createBtn = document.getElementById("createBtn");
    if (createBtn) createBtn.onclick = deployAndCreateEscrow;

    const u1Btn = document.getElementById("confirmUser1Btn");
    if (u1Btn) u1Btn.onclick = confirmUser1;

    const agentBtn = document.getElementById("confirmAgentBtn");
    if (agentBtn) agentBtn.onclick = confirmAgent;

    const u2Btn = document.getElementById("confirmUser2Btn");
    if (u2Btn) u2Btn.onclick = confirmUser2;

    setInterval(() => {
        updateBalance();
        updateEscrowStatus();
    }, 5000);
});