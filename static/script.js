// --- dBlock Supplychain Escrow Core JS ---

const Web3 = window.Web3;
let web3Local; // For signing 
let contractConfig = {};
let ABIs = {};

// Stage mapping to numeric values for timeline completion calculation
const STAGE_ORDER = {
    'Created': 0,
    'Confirmed': 1,
    'Shipped': 2,
    'AtCheckpoint': 3,
    'Delivered': 4,
    'Completed': 5,
    'Disputed': -1,
    'Resolved': 5
};

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Auth Check - Redirect if not logged in (unless on login page)
    const isAuthPage = window.location.pathname.includes('/login') || window.location.pathname.includes('/register');
    const pk = localStorage.getItem('privateKey');
    
    if (!pk && !isAuthPage) {
        window.location.href = '/login';
        return;
    }
    
    if (pk) {
        const activeChain = localStorage.getItem('selectedChain') || 'ETH';
        updateChainUI(activeChain);
        
        web3Local = new Web3(new Web3.providers.HttpProvider(activeChain === 'BNB' ? "http://127.0.0.1:8546" : "http://127.0.0.1:8545"));
        await setupUI();
        await loadConfig();
        await updateBalances();
        
        // Router
        const path = window.location.pathname;
        if (path === '/' || path.includes('/dashboard')) {
            loadDashboard();
        } else if (path.includes('/order_tracking')) {
            const targetId = localStorage.getItem('viewOrderTarget');
            if (targetId) {
                loadOrderTracking(targetId);
            }
        }
    }
});

async function setupUI() {
    const acc = localStorage.getItem('selectedAccount');
    const role = localStorage.getItem('userRole');
    const name = localStorage.getItem('userName');
    
    const els = {
        navUserName: document.getElementById('navUserName'),
        navUserRole: document.getElementById('navUserRole'),
        dashUserName: document.getElementById('dashUserName'),
        dashUserRole: document.getElementById('dashUserRole'),
        currentAccountHeader: document.getElementById('currentAccountHeader'),
        dropdownAccountFull: document.getElementById('dropdownAccountFull')
    };

    if (!acc) return;

    if (els.navUserName) els.navUserName.innerText = name || 'User';
    if (els.navUserRole) els.navUserRole.innerText = (role || 'guest').toUpperCase();
    if (els.dashUserName) els.dashUserName.innerText = name || 'User';
    if (els.dashUserRole) els.dashUserRole.innerText = (role || 'guest').toUpperCase();
    
    if (els.currentAccountHeader) els.currentAccountHeader.innerText = acc.substring(0,6) + '...' + acc.substring(acc.length-4);
    if (els.dropdownAccountFull) els.dropdownAccountFull.innerText = acc;
    
    document.querySelectorAll('.dashboard-buyer-only').forEach(e => e.style.display = role === 'buyer' ? (e.classList.contains('row') ? 'flex' : 'inline-block') : 'none');
    document.querySelectorAll('.dashboard-seller-only').forEach(e => e.style.display = role === 'seller' ? (e.classList.contains('row') ? 'flex' : 'inline-block') : 'none');
    document.querySelectorAll('.dashboard-admin-only').forEach(e => e.style.display = role === 'admin' ? (e.classList.contains('row') ? 'flex' : 'block') : 'none');
    document.querySelectorAll('.admin-only').forEach(e => e.style.display = role === 'admin' ? (e.classList.contains('row') ? 'flex' : 'block') : 'none');
    document.querySelectorAll('.dashboard-agent-only').forEach(e => e.style.display = role === 'agent' ? (e.classList.contains('row') ? 'flex' : 'block') : 'none');
    
    // Hide standard metrics and table for admin
    if (role === 'admin') {
        document.querySelectorAll('.dashboard-standard-metrics').forEach(e => e.style.display = 'none');
        const tbl = document.getElementById('dashboardOrderListContainer');
        if(tbl) tbl.style.display = 'none';
    }
    
    // Apply a deterministic color while profile loads or when no image exists.
    applyAvatarImage(null, acc);

    // Load saved profile image and apply globally (sidebar + header).
    try {
        const res = await fetch(`/api/user/profile/${acc}`);
        if (res.ok) {
            const data = await res.json();
            applyAvatarImage(data.profile_pic_base64 || null, acc);
        }
    } catch (e) {
        console.warn('Profile avatar fetch failed:', e);
    }
}

function applyAvatarImage(base64Data, address) {
    const avatarNodes = [
        { box: document.getElementById('sidebarAvatar'), fallback: document.getElementById('sidebarAvatarFallback') },
        { box: document.getElementById('headerAvatar'), fallback: document.getElementById('headerAvatarFallback') }
    ];

    avatarNodes.forEach(node => {
        if (!node.box) return;
        const defaultColor = '#' + address.substring(2, 8);
        if (base64Data) {
            node.box.style.backgroundColor = 'transparent';
            node.box.style.backgroundImage = `url(${base64Data})`;
            node.box.style.backgroundSize = 'cover';
            node.box.style.backgroundPosition = 'center';
            if (node.fallback) node.fallback.style.display = 'none';
        } else {
            node.box.style.backgroundColor = defaultColor;
            node.box.style.backgroundImage = 'none';
            if (node.fallback) node.fallback.style.display = 'inline-block';
        }
    });
}

async function loadConfig() {
    try {
        const res = await fetch('/static/contract/multichain_config.json');
        contractConfig = await res.json();
    } catch (e) {
        console.error("Config missing. Relies on hardhat deploy.");
    }
    
    // Fallback simple ABI fetch if generated by deploy script, otherwise we assume abi.js loaded
    if (typeof escrowSourceAbi !== 'undefined') {
        // Assume abi.js was loaded which actually has our updated SupplyChain ABI constants
        // Note: the backend deployment updates abi.js to be SupplyChainSource
        // Actually, let's just make sure we fetch the ABI from artifacts if possible.
        // For simplicity, we'll try to fetch it via API or assume the user has pasted the ABI in abi.js
        console.log("Config loaded:", contractConfig);
    }
}

// Fetch ABIs dynamically from Hardhat artifacts served statically (or just through simple fetch)
async function getContractInstance(chainType) {
    const web3 = new Web3(chainType === 'ETH' ? "http://127.0.0.1:8545" : "http://127.0.0.1:8546");
    
    // Hack: we will fetch the ABI JSON directly from the artifacts directory via the flask static handler if mapped, 
    // or we just define standard ABIs here if they aren't available. To be robust, let's load from /static/contract
    // Wait, the python code uses `api/contract/abi`. Let's build a quick fetcher if it exists.
    
    // Fallback: Just rely on abi.js which MUST be updated by the developer.
    // If not, we will throw.
    if (typeof escrowSourceAbi === 'undefined') throw new Error("ABIs not loaded via abi.js");
    
    // Map escrowSourceAbi to SupplyChainSource (assuming user replaced it in abi.js as instructed)
    const addr = chainType === 'ETH' ? contractConfig.ETH_SOURCE : contractConfig.BNB_MIRROR;
    const abi = chainType === 'ETH' ? escrowSourceAbi : escrowMirrorAbi; 
    
    return new web3.eth.Contract(abi, addr);
}

async function updateBalances() {
    const nativeEl = document.getElementById('balanceDisplay');
    const usdtEl = document.getElementById('usdtBalance');
    if (!nativeEl || !usdtEl) return;
    
    const acc = localStorage.getItem('selectedAccount');
    const chain = localStorage.getItem('selectedChain') || 'ETH';
    
    try {
        // 1. Primary Currency (ETH)
        const nativeWeb3 = new Web3(chain === 'BNB' ? "http://127.0.0.1:8546" : "http://127.0.0.1:8545");
        
        if (chain === 'BNB') {
            // On BNB, "ETH" is the WETH token
            if (contractConfig.WETH_BNB) {
                const wethContract = new nativeWeb3.eth.Contract(usdtAbi, contractConfig.WETH_BNB);
                const wBal = await wethContract.methods.balanceOf(acc).call();
                nativeEl.innerText = parseFloat(nativeWeb3.utils.fromWei(wBal, "ether")).toFixed(4);
            }
            // Also update the secondary gas balance
            const nBal = await nativeWeb3.eth.getBalance(acc);
            const gasEl = document.getElementById('gasBalance');
            if (gasEl) gasEl.innerText = parseFloat(nativeWeb3.utils.fromWei(nBal, "ether")).toFixed(4);
        } else {
            // On ETH, "ETH" is just native ETH
            const nBal = await nativeWeb3.eth.getBalance(acc);
            nativeEl.innerText = parseFloat(nativeWeb3.utils.fromWei(nBal, "ether")).toFixed(4);
        }
        
        // 2. USDT Balance
        const usdtAddr = chain === 'ETH' ? contractConfig.USDT_ETH : contractConfig.USDT_BNB;
        if (usdtAddr) {
            const usdtContract = new nativeWeb3.eth.Contract(usdtAbi, usdtAddr);
            const uBal = await usdtContract.methods.balanceOf(acc).call();
            usdtEl.innerText = parseFloat(nativeWeb3.utils.fromWei(uBal, "ether")).toFixed(2);
        }
    } catch(e) {
        console.error("Error fetching balances", e);
    }
}

function updateChainUI(chain) {
    const label = document.getElementById('activeChainLabel');
    if (label) {
        label.innerText = chain === 'ETH' ? 'ETH Source' : 'BSC Mirror';
    }
}

async function changeChain(chain) {
    localStorage.setItem('selectedChain', chain);
    updateChainUI(chain);
    
    // Update the local web3 instance for signing
    web3Local = new Web3(new Web3.providers.HttpProvider(chain === 'BNB' ? "http://127.0.0.1:8546" : "http://127.0.0.1:8545"));
    
    await updateBalances();
    
    // Refresh dashboard data if on home
    if (window.location.pathname === '/' || window.location.pathname.includes('/dashboard')) {
        loadDashboard();
    }
}

// --- API Helpers --- //

async function apiGet(route) {
    const res = await fetch('/api' + route);
    if (!res.ok) throw new Error("API Get Error: " + route);
    return await res.json();
}

async function apiPost(route, data) {
    const res = await fetch('/api' + route, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const dat = await res.json();
        throw new Error(dat.error || "API Post Error: " + route);
    }
    return await res.json();
}

async function uploadToIPFS(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/upload-ipfs', { method: 'POST', body: formData });
    if (!res.ok) throw new Error("IPFS upload failed");
    const data = await res.json();
    return data.ipfsHash;
}

function getWeb3AndAccount(chain) {
    const pk = localStorage.getItem('privateKey');
    const web3 = new Web3(chain === 'BNB' ? "http://127.0.0.1:8546" : "http://127.0.0.1:8545");
    const account = web3.eth.accounts.privateKeyToAccount(pk.startsWith('0x') ? pk : '0x'+pk);
    web3.eth.accounts.wallet.add(account);
    return { web3, account };
}

async function signAndSend(web3, account, txData, toAddress, value = "0") {
    const tx = {
        from: account.address,
        to: toAddress,
        data: txData,
        value: value,
        gas: 2000000,
        gasPrice: await web3.eth.getGasPrice()
    };
    const signed = await web3.eth.accounts.signTransaction(tx, account.privateKey);
    return await web3.eth.sendSignedTransaction(signed.rawTransaction);
}

// --- Dashboard --- //

async function loadDashboard() {
    const acc = localStorage.getItem('selectedAccount');
    const role = localStorage.getItem('userRole');
    const tbody = document.getElementById('dashboardOrderTable');
    
    // Admin Dashboard Logic
    if (role === 'admin') {
        try {
            const stats = await apiGet('/admin/dashboard_stats');
            document.getElementById('adminTotalUsers').innerText = stats.total_users;
            document.getElementById('adminTotalOrders').innerText = stats.total_orders;
            document.getElementById('adminTotalAgents').innerText = stats.total_agents;
            document.getElementById('adminTotalSellers').innerText = stats.total_sellers;
            document.getElementById('adminTotalVolume').innerText = parseFloat(stats.total_volume).toFixed(4) + ' ETH';
        } catch(e) { console.error("Error loading admin stats", e); }
        return; // Admin doesn't need the table logic
    }
    
    if (!tbody) return;
    
    try {
        const orders = await apiGet('/orders/user/' + acc);
        
        // Populate standard stats
        let active = orders.filter(o => o.status !== 'Completed').length;
        let completed = orders.filter(o => o.status === 'Completed').length;
        document.getElementById('statActive').innerText = active;
        document.getElementById('statCompleted').innerText = completed;

        // Agent specific logic: shipments by city
        if (role === 'agent') {
            const cityCount = {};
            orders.forEach(o => {
                const c = o.city || 'Unknown';
                cityCount[c] = (cityCount[c] || 0) + 1;
            });
            const cityList = document.getElementById('agentCityStats');
            cityList.innerHTML = '';
            for(const [c, count] of Object.entries(cityCount)) {
                cityList.innerHTML += `<li class="list-group-item d-flex justify-content-between align-items-center">
                    ${c} <span class="badge bg-primary rounded-pill">${count}</span>
                </li>`;
            }
            if(Object.keys(cityCount).length === 0) {
                cityList.innerHTML = '<li class="list-group-item text-muted">No shipments assigned yet.</li>';
            }
        }
        
        // Buyer performance stats logic
        if (role === 'buyer') {
            try {
                const perf = await apiGet('/buyer/performance_stats');
                const sList = document.getElementById('buyerSellerStats');
                const aList = document.getElementById('buyerAgentStats');
                
                if (sList) {
                    sList.innerHTML = perf.sellers.length > 0 ? '' : '<div class="p-4 text-center text-muted">No seller data available.</div>';
                    perf.sellers.forEach(s => {
                        const initials = s.name.substring(0,2).toUpperCase();
                        sList.innerHTML += `
                            <div class="list-group-item border-0 border-bottom d-flex justify-content-between align-items-center py-3 px-4 bg-transparent hover-light">
                                <div class="d-flex align-items-center">
                                    <div class="avatar-sm rounded-circle bg-warning bg-opacity-10 text-warning d-flex align-items-center justify-content-center fw-bold me-3" style="width: 40px; height: 40px;">${initials}</div>
                                    <div>
                                        <h6 class="mb-0 fw-bold text-dark">${s.name}</h6>
                                        <small class="text-muted font-monospace" style="font-size: 0.65rem; opacity: 0.8;">${s.address.substring(0,18)}...</small>
                                    </div>
                                </div>
                                <div class="text-end">
                                    <span class="badge bg-primary px-3 py-2 rounded-pill fw-bold" style="font-size: 0.7rem;">${s.count} Orders</span>
                                </div>
                            </div>
                        `;
                    });
                }
                
                if (aList) {
                    aList.innerHTML = perf.agents.length > 0 ? '' : '<div class="p-4 text-center text-muted">No agent data available.</div>';
                    perf.agents.forEach(a => {
                        const initials = a.name.substring(0,2).toUpperCase();
                        aList.innerHTML += `
                            <div class="list-group-item border-0 border-bottom d-flex justify-content-between align-items-center py-3 px-4 bg-transparent hover-light">
                                <div class="d-flex align-items-center">
                                    <div class="avatar-sm rounded-circle bg-success bg-opacity-10 text-success d-flex align-items-center justify-content-center fw-bold me-3" style="width: 40px; height: 40px;">${initials}</div>
                                    <div>
                                        <h6 class="mb-0 fw-bold text-dark">${a.name}</h6>
                                        <small class="text-muted font-monospace" style="font-size: 0.65rem; opacity: 0.8;">${a.address.substring(0,18)}...</small>
                                    </div>
                                </div>
                                <div class="text-end">
                                    <span class="badge bg-success px-3 py-2 rounded-pill fw-bold" style="font-size: 0.7rem; background: #059669 !important;">${a.count} Shipments</span>
                                </div>
                            </div>
                        `;
                    });
                }
            } catch(e) { console.error("Error loading performance stats", e); }
        }
        
        if (orders.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-muted">No active orders found.</td></tr>`;
            return;
        }
        
        tbody.innerHTML = '';
        orders.slice(0, 8).forEach(o => { // Show top 8
            tbody.innerHTML += `
                <tr>
                    <td class="ps-4 font-monospace text-secondary">#${o.order_id_onchain}</td>
                    <td class="fw-bold text-dark">${o.product_description}</td>
                    <td class="text-muted"><i class="fas fa-map-marker-alt me-1 text-danger"></i>${o.city || 'N/A'}</td>
                    <td class="text-primary fw-bold">${o.amount} <span class="fs-6 text-muted">${o.token_symbol}</span></td>
                    <td><span class="status-badge status-${o.status}">${o.status}</span></td>
                    <td class="text-end pe-4">
                        <button class="btn btn-sm btn-outline-primary" onclick="viewOrderTracking('${o.id}')">
                            <i class="fas fa-eye"></i> View
                        </button>
                    </td>
                </tr>
            `;
        });
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center py-4 text-danger">Failed to load orders.</td></tr>`;
    }
}

async function getRouteGuide() {
    const src = document.getElementById('routeSource').value;
    const dest = document.getElementById('routeDest').value;
    const resBox = document.getElementById('routeGuideResult');
    
    if(!src || !dest) {
        return alert("Please enter both source and destination.");
    }
    
    resBox.innerHTML = '<i class="fas fa-spinner fa-spin text-success me-2"></i> Fetching AI Route Guide...';
    
    try {
        const data = await apiPost('/agent/route_guide', { source: src, destination: dest });
        resBox.innerHTML = `<strong>Best Route (${src} &rarr; ${dest}):</strong><br/>${data.route_guide.replace(/\\n/g, '<br/>')}`;
    } catch(e) {
        resBox.innerHTML = `<span class="text-danger">Error: ${e.message}</span>`;
    }
}

function viewOrderTracking(dbId) {
    localStorage.setItem('viewOrderTarget', dbId);
    window.location.href = '/order_tracking';
}

// --- Create Order --- //

async function createSupplyChainOrder() {
    const btn = document.getElementById('submitOrderBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Submitting to Blockchain...';
    
    try {
        const { web3, account } = getWeb3AndAccount('ETH');
        const contract = await getContractInstance('ETH');
        
        const desc = document.getElementById('productDesc').value;
        const city = document.getElementById('cityInput')?.value || "";
        const country = document.getElementById('countryInput')?.value || "";
        const phone = document.getElementById('phoneInput')?.value || "";
        const seller = document.getElementById('sellerSelect').value;
        const agent = document.getElementById('agentSelect').value;
        const tokenType = document.getElementById('tokenSelect').value;
        const amountEth = document.getElementById('amountInput').value;
        const amountWei = web3.utils.toWei(amountEth, "ether");
        const isMulti = document.getElementById('multichainSelect').value === "true";
        
        let fileHash = "";
        const fileInput = document.getElementById('poFileUpload');
        if (fileInput.files.length > 0) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Uploading Document to IPFS...';
            fileHash = await uploadToIPFS(fileInput.files[0]);
        }
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Awaiting User Signature...';
        
        const tokenAddr = (tokenType === 'USDT' ? contractConfig.USDT_ETH : "0x0000000000000000000000000000000000000000").toLowerCase();
        
        // If USDT, we need to approve first
        if (tokenType === 'USDT') {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Approving USDT...';
            const usdtContract = new web3.eth.Contract(usdtAbi, tokenAddr);
            const approveData = usdtContract.methods.approve(contract.options.address, amountWei).encodeABI();
            await signAndSend(web3, account, approveData, tokenAddr);
        }
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Mining Transaction...';
        const txData = contract.methods.createOrder(
            seller.toLowerCase(), 
            agent.toLowerCase(), 
            tokenAddr.toLowerCase(), 
            amountWei, 
            fileHash, 
            isMulti
        ).encodeABI();
        const value = tokenType === 'ETH_NATIVE' || tokenType === 'ETH' ? amountWei : "0";
        
        const receipt = await signAndSend(web3, account, txData, contract.options.address, value);
        
        // Parse the event to get the exact onchain ID
        // Note: this depends on contract emitting OrderCreated event exactly
        let onchainId = 0;
        try {
            // Very simplified: just ask the contract for next ID and subtract 1
            const nextId = await contract.methods.nextOrderId().call();
            onchainId = Number(nextId) - 1;
        } catch(e) {}
        
        // Post to backend
        await apiPost('/order/create', {
            contractAddress: contract.options.address,
            orderIdOnchain: onchainId,
            buyer: account.address,
            seller: seller,
            agent: agent,
            amount: amountEth,
            token: tokenType,
            isMultichain: isMulti,
            productDescription: desc,
            ipfsHash: fileHash,
            city: city,
            country: country,
            phone: phone
        });
        
        alert("Order created successfully!");
        window.location.href = '/orders';
        
    } catch (e) {
        console.error(e);
        alert("Error: " + e.message);
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-lock me-2"></i> Lock Funds & Initiate Order';
    }
}

// --- Order Tracking --- //

let currentTrackingOrder = null;

async function loadOrderTracking(dbId) {
    document.getElementById('orderSelectContainer').style.display = 'none';
    document.getElementById('orderViewContainer').style.display = 'flex';
    
    const acc = localStorage.getItem('selectedAccount');
    
    // Fetch all for user and find the specific one (naive approach to reuse api)
    const orders = await apiGet('/orders/user/' + acc);
    currentTrackingOrder = orders.find(o => String(o.id) === String(dbId));
    
    if (!currentTrackingOrder) {
        // Maybe admin? Try to find it in the global list if they are admin
        if(localStorage.getItem('userRole') === 'admin') {
           const all = await apiGet('/orders/user/' + acc); // Server handles admin
           currentTrackingOrder = all.find(o => String(o.id) === String(dbId));
        }
        if(!currentTrackingOrder) return alert("Order not found or access denied.");
    }
    
    const o = currentTrackingOrder;
    
    // Populate details panel
    document.getElementById('detailOnchainId').innerText = o.order_id_onchain;
    document.getElementById('detailProduct').innerText = o.product_description;
    document.getElementById('detailAmount').innerText = o.amount;
    document.getElementById('detailToken').innerText = o.token_symbol;
    document.getElementById('detailBuyer').innerText = o.buyer;
    document.getElementById('detailSeller').innerText = o.seller;
    document.getElementById('detailAgent').innerText = o.agent;
    document.getElementById('detailNetwork').innerText = o.is_multichain ? "Multichain (ETH / BNB)" : "Single-Chain (ETH)";
    
    // New Fields
    document.getElementById('detailCity').innerText = o.city || 'N/A';
    document.getElementById('detailCountry').innerText = o.country || 'N/A';
    document.getElementById('detailPhone').innerText = o.phone || 'N/A';

    // Agent Routing Visibility
    const agentSec = document.getElementById('agentRoutingSection');
    if (agentSec) {
        agentSec.classList.toggle('d-none', localStorage.getItem('userRole') !== 'agent');
    }
    
    const badge = document.getElementById('orderStatusBadge');
    badge.className = `status-badge status-${o.status}`;
    badge.innerText = o.status;
    
    renderTimeline(o);
    loadDocuments(o.id);
    setupActionPanel(o, acc);
}

async function checkBestRouteForOrder() {
    if (!currentTrackingOrder) return;
    const resBox = document.getElementById('routeResultBox');
    const btn = document.getElementById('btnCheckRoute');
    
    const city = currentTrackingOrder.city;
    const country = currentTrackingOrder.country;
    
    if (!city || !country) {
        return alert("City and Country are required to check route.");
    }

    resBox.classList.remove('d-none');
    resBox.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Fetching AI Route Guide...';
    btn.disabled = true;

    try {
        // Assume origin is somewhere fixed or we just ask for a guide to this destination
        // Since we don't have a fixed origin in the order, we'll ask for a guide TO this destination.
        const data = await apiPost('/agent/route_guide', { 
            source: "Major International Port", 
            destination: `${city}, ${country}` 
        });
        resBox.innerHTML = `<strong>AI Route Guide:</strong><br/>${data.route_guide.replace(/\n/g, '<br/>')}`;
    } catch(e) {
        resBox.innerHTML = `<span class="text-danger">Error: ${e.message}</span>`;
    } finally {
        btn.disabled = false;
    }
}

function renderTimeline(order) {
    const list = document.getElementById('timelineContainer');
    list.innerHTML = '';
    
    const stages = [
        { key: 'Created', label: 'Order Created', icon: 'fa-file-contract', date: order.created_at },
        { key: 'Confirmed', label: 'Seller Confirmed', icon: 'fa-thumbs-up', date: order.confirmed_at },
        { key: 'Shipped', label: 'Items Shipped', icon: 'fa-truck-loading', date: order.shipped_at },
        { key: 'AtCheckpoint', label: 'Agent Checkpoint', icon: 'fa-clipboard-check', date: order.in_transit_at },
        { key: 'Delivered', label: 'Delivered', icon: 'fa-truck', date: order.delivered_at },
        { key: 'Completed', label: 'Receipt Confirmed (Funds Released)', icon: 'fa-check-circle', date: order.completed_at }
    ];
    
    let isDisputed = order.status === 'Disputed';
    let currentPhaseIdx = STAGE_ORDER[order.status] !== undefined ? STAGE_ORDER[order.status] : 0;
    
    stages.forEach((s, idx) => {
        const isPast = idx <= currentPhaseIdx;
        const isActive = idx === currentPhaseIdx && !isPast; // Wait, if it's the current but not done? 
        // Actually, if idx <= currentPhaseIdx it's done. 
        const stateClass = isPast ? 'completed' : (idx === currentPhaseIdx + 1 ? 'active' : '');
        
        let timeHTML = s.date ? `<div class="timeline-date"><i class="far fa-clock me-1"></i>${new Date(s.date).toLocaleString()}</div>` : `<div class="timeline-date text-muted">Pending execution...</div>`;
        
        list.innerHTML += `
            <div class="timeline-item ${stateClass}">
                <div class="timeline-icon"><i class="fas ${s.icon}"></i></div>
                <div class="timeline-content">
                    <h6>${s.label}</h6>
                    ${timeHTML}
                </div>
            </div>
        `;
    });

    if (isDisputed) {
        list.innerHTML += `
           <div class="timeline-item active">
                <div class="timeline-icon bg-danger text-white border-danger"><i class="fas fa-gavel"></i></div>
                <div class="timeline-content border-danger">
                    <h6 class="text-danger">Dispute Raised</h6>
                    <div class="timeline-date text-muted">Awaiting Admin Resolution</div>
                </div>
            </div>
        `;
    }
}

async function loadDocuments(orderId) {
    const gallery = document.getElementById('documentGallery');
    gallery.innerHTML = '<span class="text-white-50 small">Loading proofs...</span>';
    
    try {
        const docs = await apiGet('/order/' + orderId + '/documents');
        gallery.innerHTML = '';
        if (docs.length === 0) {
            gallery.innerHTML = '<span class="text-white-50 small">No cryptographic proofs uploaded.</span>';
            return;
        }
        
        docs.forEach(d => {
            const isImg = d.doc_type === 'photo';
            const icon = isImg ? 'fa-image' : 'fa-file-alt';
            // Use IPFS gateway
            const url = `http://127.0.0.1:8080/ipfs/${d.ipfs_hash}`;
            
            // Encode OCR result to base64 to handle newlines and quotes safely
            const safeOCR = btoa(unescape(encodeURIComponent(d.ocr_result || "No data extracted.")));

            gallery.innerHTML += `
                <div class="doc-placeholder bg-dark border-secondary text-center p-2" style="cursor:pointer;" 
                     onclick="openPreview('${url}', '${d.ipfs_hash}', '${safeOCR}')" title="${d.stage} Phase Proof">
                    <i class="fas ${icon} fs-3 primary-text d-block mb-1"></i>
                    <small style="font-size: 0.6rem;">${d.stage}</small>
                </div>
            `;
        });
    } catch(e) { console.error(e); }
}

function openPreview(url, hash, ocr) {
    document.getElementById('previewModalImage').src = url;
    document.getElementById('previewModalHash').innerText = "IPFS: " + hash;
    document.getElementById('previewModalDownload').href = url;
    
    const role = localStorage.getItem('userRole');
    const ocrSec = document.getElementById('ocrSection');
    const ocrCon = document.getElementById('ocrContent');
    
    if (role === 'admin') {
        ocrSec.classList.remove('d-none');
        try {
            // Decode from base64 safely
            const decoded = decodeURIComponent(escape(atob(ocr)));
            ocrCon.innerText = decoded;
        } catch(e) {
            ocrCon.innerText = ocr || "Analyzing document content...";
        }
    } else {
        ocrSec.classList.add('d-none');
    }

    const m = new bootstrap.Modal(document.getElementById('previewModal'));
    m.show();
}

function setupActionPanel(order, myAddress) {
    const box = document.getElementById('actionPanelBox');
    const text = document.getElementById('actionText');
    const btn = document.getElementById('actionBtn');
    const disp = document.getElementById('disputeArea');
    const role = localStorage.getItem('userRole');
    
    box.classList.add('d-none');
    disp.classList.add('d-none');
    
    myAddress = myAddress.toLowerCase();
    
    // Logic: who acts next?
    if (order.status === 'Created' && order.seller.toLowerCase() === myAddress) {
        showAction("Awaiting your confirmation to accept this order.", "Confirm Order");
        disp.classList.remove('d-none');
    } 
    else if (order.status === 'Confirmed' && order.seller.toLowerCase() === myAddress) {
        showAction("Ready to ship? Upload the shipping manifest or photo and mark as shipped.", "Mark as Shipped");
        disp.classList.remove('d-none');
    }
    else if (order.status === 'Shipped' && order.agent.toLowerCase() === myAddress) {
        showAction("Confirm the cargo has arrived at the checkpoint.", "Verify Checkpoint");
    }
    else if (order.status === 'AtCheckpoint' && order.seller.toLowerCase() === myAddress) {
        showAction("Once reach final destination, mark as delivered.", "Mark Delivered");
    }
    else if (order.status === 'Delivered' && order.buyer.toLowerCase() === myAddress) {
        showAction("Please confirm receipt of your goods to release locked funds to the seller.", "Confirm Receipt");
        disp.classList.remove('d-none');
    }
    else if (order.status === 'Disputed' && role === 'admin') {
        showAction("As Admin, review the documents and force resolve this dispute.", "Resolve Dispute (Pay Seller)");
        // Add a second button dynamically for paying buyer
        const div = document.createElement('div');
        div.innerHTML = `<button class="btn btn-outline-danger w-100 fw-bold mt-2" onclick="executeAdminResolve('buyer')">Resolve Dispute (Refund Buyer)</button>`;
        btn.parentNode.insertBefore(div, btn.nextSibling);
        btn.setAttribute('onclick', "executeAdminResolve('seller')");
        // Hide file upload for admin
        document.getElementById('proofUploadSection').style.display = 'none';
        
    } else {
        // Not my turn
        return;
    }
    
    function showAction(msg, btnLabel) {
        box.classList.remove('d-none');
        text.innerText = msg;
        
        // Explicitly show which chain the action is targeting
        const chainLabel = order.is_multichain ? 'BNB' : 'ETH';
        btn.innerText = `${btnLabel} (${chainLabel})`;
        
        document.getElementById('proofUploadSection').style.display = 'block';
    }
}

// Global execution function mapper based on status
async function executeNextStage() {
    const o = currentTrackingOrder;
    let funcName = "";
    if (o.status === 'Created') funcName = "confirmOrder";
    else if (o.status === 'Confirmed') funcName = "shipOrder";
    else if (o.status === 'Shipped') funcName = "agentCheckpoint";
    else if (o.status === 'AtCheckpoint') funcName = "deliverOrder";
    else if (o.status === 'Delivered') funcName = "confirmReceipt";
    
    if(!funcName) return;
    await executeChainTransaction(funcName);
}

async function raiseDispute() {
    await executeChainTransaction("raiseDispute");
}

async function executeAdminResolve(winnerRole) {
    const o = currentTrackingOrder;
    const winnerAddr = winnerRole === 'buyer' ? o.buyer : o.seller;
    
    const btn = document.getElementById('actionBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Resolving...';
    
    try {
        const chain = o.is_multichain ? 'BNB' : 'ETH';
        const { web3, account } = getWeb3AndAccount(chain);
        const contract = await getContractInstance(chain);
        
        const txData = contract.methods.adminResolveDispute(o.order_id_onchain, winnerAddr.toLowerCase()).encodeABI();
        const txHash = await signAndSend(web3, account, txData, contract.options.address);
        
        await fetchSyncAPI('OrderResolved', txHash.transactionHash, "", account.address);
        alert("Dispute resolved successfully. Funds released.");
        window.location.reload();
    } catch(e) {
        console.error(e);
        alert("Action failed: " + e.message);
        btn.disabled = false;
        btn.innerText = 'Retry';
    }
}

async function executeChainTransaction(funcName) {
    const o = currentTrackingOrder;
    const btn = document.getElementById('actionBtn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    
    try {
        // If multichain, the source functions beyond create apply to the BNB mirror
        const chain = o.is_multichain ? 'BNB' : 'ETH';
        const { web3, account } = getWeb3AndAccount(chain);
        const contract = await getContractInstance(chain);
        
        let fileHash = "";
        const fileInput = document.getElementById('actionProofFile');
        if (fileInput && fileInput.files.length > 0) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
            fileHash = await uploadToIPFS(fileInput.files[0]);
        }
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Requesting Signature...';
        
        // Contract call
        const txData = contract.methods[funcName](o.order_id_onchain, fileHash).encodeABI();
        const txHash = await signAndSend(web3, account, txData, contract.options.address);
        
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mining & Syncing...';
        
        // Map function to Event name for Relayer/Sync backend
        const eventMap = {
            'confirmOrder' : 'OrderConfirmed',
            'shipOrder' : 'OrderShipped',
            'agentCheckpoint' : 'AgentCheckpoint',
            'deliverOrder' : 'OrderDelivered',
            'confirmReceipt' : 'OrderCompleted',
            'raiseDispute' : 'OrderDisputed'
        };
        
        // Ping backend to register the event (or wait for python relayer to do it. But to make UI snappy we ping)
        await fetchSyncAPI(eventMap[funcName], txHash.transactionHash, fileHash, account.address);
        
        alert("Operation successful!");
        window.location.reload();
    } catch(e) {
        console.error(e);
        alert("Action failed: " + e.message);
        btn.disabled = false;
        btn.innerText = 'Try Again';
    }
}

async function fetchSyncAPI(eventName, txHash, proofHash, actorStr) {
    const o = currentTrackingOrder;
    await apiPost('/order/sync', {
        dbOrderId: o.id,
        orderIdOnchain: o.order_id_onchain,
        event: eventName,
        txHash: txHash,
        blockNumber: 0, 
        proofHash: proofHash,
        actor: actorStr
    });
}