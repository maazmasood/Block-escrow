// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract SupplyChainMirror is Ownable {
    
    enum OrderStatus {
        Created,        // 0: Buyer placed order on ETH & synced here
        Confirmed,      // 1: Seller accepted
        Shipped,        // 2: Seller initiated shipment
        AtCheckpoint,   // 3: Agent confirmed arrival at checkpoint
        Delivered,      // 4: Seller marked as delivered
        Completed,      // 5: Buyer confirmed receipt -> funds released
        Disputed,       // 6: Either party raised a dispute
        Resolved        // 7: Admin resolved the dispute
    }

    struct Order {
        uint256 ethId;
        address buyer;
        address seller;
        address agent;
        uint256 amount;
        address tokenAddress; // address(0) for native BNB (if supported, though mirror usually uses bridged USDT)
        OrderStatus status;
        bool fundsReleased;
    }

    mapping(uint256 => Order) public orders;
    mapping(address => bool) public isAuthorizedAdmin;

    // Events
    event MirrorInitialized(uint256 indexed id, address buyer, address seller, address agent, address tokenAddress, uint256 amount);
    event OrderConfirmed(uint256 indexed id, address seller, string ipfsHash);
    event OrderShipped(uint256 indexed id, address seller, string ipfsHash);
    event AgentCheckpoint(uint256 indexed id, address agent, string ipfsHash);
    event OrderDelivered(uint256 indexed id, address seller, string ipfsHash);
    event OrderCompleted(uint256 indexed id, address buyer, string ipfsHash);
    event OrderDisputed(uint256 indexed id, address disputer, string ipfsHash);
    event OrderResolved(uint256 indexed id, address resolver, address winner);
    event FundsReleased(uint256 indexed id, address to, uint256 amount);

    constructor() Ownable(msg.sender) {
        isAuthorizedAdmin[msg.sender] = true;
    }

    function setAdminStatus(address _admin, bool _status) external onlyOwner {
        isAuthorizedAdmin[_admin] = _status;
    }

    // Called by the Relayer to sync from ETH using the SAME ethId
    function syncFromETH(uint256 _ethId, address _buyer, address _seller, address _agent, address _tokenAddress, uint256 _amount) external onlyOwner {
        require(orders[_ethId].buyer == address(0), "Order already synced");
        orders[_ethId] = Order(_ethId, _buyer, _seller, _agent, _amount, _tokenAddress, OrderStatus.Created, false);
        emit MirrorInitialized(_ethId, _buyer, _seller, _agent, _tokenAddress, _amount);
    }

    function confirmOrder(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(msg.sender == o.seller, "Only seller");
        require(o.status == OrderStatus.Created, "Invalid status");

        o.status = OrderStatus.Confirmed;
        emit OrderConfirmed(_id, msg.sender, _ipfsHash);
    }

    function shipOrder(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(msg.sender == o.seller, "Only seller");
        require(o.status == OrderStatus.Confirmed, "Invalid status");

        o.status = OrderStatus.Shipped;
        emit OrderShipped(_id, msg.sender, _ipfsHash);
    }

    function agentCheckpoint(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(msg.sender == o.agent, "Only agent");
        require(o.status == OrderStatus.Shipped, "Invalid status");

        o.status = OrderStatus.AtCheckpoint;
        emit AgentCheckpoint(_id, msg.sender, _ipfsHash);
    }

    function deliverOrder(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(msg.sender == o.seller, "Only seller");
        require(o.status == OrderStatus.AtCheckpoint, "Invalid status");

        o.status = OrderStatus.Delivered;
        emit OrderDelivered(_id, msg.sender, _ipfsHash);
    }

    function confirmReceipt(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(msg.sender == o.buyer, "Only buyer");
        require(o.status == OrderStatus.Delivered, "Invalid status");

        o.status = OrderStatus.Completed;
        emit OrderCompleted(_id, msg.sender, _ipfsHash);
        
        _releaseFunds(_id, o.seller);
    }

    function raiseDispute(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(msg.sender == o.buyer || msg.sender == o.seller, "Only buyer or seller");
        require(o.status != OrderStatus.Completed && o.status != OrderStatus.Resolved, "Already finished");

        o.status = OrderStatus.Disputed;
        emit OrderDisputed(_id, msg.sender, _ipfsHash);
    }

    function adminResolveDispute(uint256 _id, address _winner) external {
        require(isAuthorizedAdmin[msg.sender] || msg.sender == owner(), "Not authorized");
        Order storage o = orders[_id];
        require(o.status == OrderStatus.Disputed, "Not disputed");
        require(_winner == o.buyer || _winner == o.seller, "Invalid winner");

        o.status = OrderStatus.Resolved;
        emit OrderResolved(_id, msg.sender, _winner);
        
        _releaseFunds(_id, _winner);
    }

    function _releaseFunds(uint256 _id, address _to) internal {
        Order storage o = orders[_id];
        require(!o.fundsReleased, "Already released");
        
        o.fundsReleased = true;
        
        if (o.tokenAddress == address(0)) {
            require(address(this).balance >= o.amount, "Insufficient BNB in Mirror");
            (bool success, ) = payable(_to).call{value: o.amount}("");
            require(success, "BNB transfer failed");
        } else {
            require(IERC20(o.tokenAddress).balanceOf(address(this)) >= o.amount, "Insufficient USDT in Mirror");
            require(IERC20(o.tokenAddress).transfer(_to, o.amount), "USDT transfer failed");
        }
        
        emit FundsReleased(_id, _to, o.amount);
    }

    // Function for owner to provide liquidity (for cross-chain payout)
    function depositLiquidity(address _token, uint256 amount) external payable {
        if (_token != address(0)) {
            require(IERC20(_token).transferFrom(msg.sender, address(this), amount), "Liquidity transfer failed");
        }
    }
}
