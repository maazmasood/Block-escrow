// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract SupplyChainSource is Ownable {
    
    enum OrderStatus {
        Created,        // 0: Buyer placed order & locked funds
        Confirmed,      // 1: Seller accepted
        Shipped,        // 2: Seller initiated shipment
        AtCheckpoint,   // 3: Agent confirmed arrival at checkpoint
        Delivered,      // 4: Seller marked as delivered
        Completed,      // 5: Buyer confirmed receipt -> funds released
        Disputed,       // 6: Either party raised a dispute
        Resolved        // 7: Admin resolved the dispute
    }

    struct Order {
        address buyer;
        address seller;
        address agent;
        uint256 amount;
        address tokenAddress; // address(0) for native ETH
        bool isMultichain;
        bool isBridged;      // true when Relayer confirms the order finished on BNB
        OrderStatus status;
    }

    mapping(uint256 => Order) public orders;
    mapping(address => bool) public isAuthorizedAdmin; // Whitelist for resolution
    uint256 public nextOrderId;

    // Events
    event OrderCreated(uint256 indexed id, address buyer, address seller, address agent, address tokenAddress, uint256 amount, string ipfsHash, bool isMultichain);
    event OrderConfirmed(uint256 indexed id, address seller, string ipfsHash);
    event OrderShipped(uint256 indexed id, address seller, string ipfsHash);
    event AgentCheckpoint(uint256 indexed id, address agent, string ipfsHash);
    event OrderDelivered(uint256 indexed id, address seller, string ipfsHash);
    event OrderCompleted(uint256 indexed id, address buyer, string ipfsHash);
    event OrderDisputed(uint256 indexed id, address disputer, string ipfsHash);
    event OrderResolved(uint256 indexed id, address resolver, address winner);
    event OrderBridged(uint256 indexed id);

    constructor() Ownable(msg.sender) {
        isAuthorizedAdmin[msg.sender] = true; // Owner is admin by default
    }

    function setAdminStatus(address _admin, bool _status) external onlyOwner {
        isAuthorizedAdmin[_admin] = _status;
    }

    function createOrder(address _seller, address _agent, address _tokenAddress, uint256 _amount, string memory _ipfsHash, bool _isMultichain) external payable {
        require(_amount > 0, "Amount must be > 0");
        require(_seller != address(0) && _agent != address(0), "Invalid addresses");

        if (_tokenAddress == address(0)) {
            require(msg.value == _amount, "ETH sent does not match amount");
        } else {
            require(msg.value == 0, "Cannot send ETH with ERC20 order");
            require(IERC20(_tokenAddress).transferFrom(msg.sender, address(this), _amount), "USDT transfer failed");
        }

        uint256 id = nextOrderId++;
        orders[id] = Order(msg.sender, _seller, _agent, _amount, _tokenAddress, _isMultichain, false, OrderStatus.Created);

        emit OrderCreated(id, msg.sender, _seller, _agent, _tokenAddress, _amount, _ipfsHash, _isMultichain);
    }

    function confirmOrder(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(msg.sender == o.seller, "Only seller");
        require(o.status == OrderStatus.Created, "Invalid status");

        o.status = OrderStatus.Confirmed;
        emit OrderConfirmed(_id, msg.sender, _ipfsHash);
    }

    function shipOrder(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(msg.sender == o.seller, "Only seller");
        require(o.status == OrderStatus.Confirmed, "Invalid status");

        o.status = OrderStatus.Shipped;
        emit OrderShipped(_id, msg.sender, _ipfsHash);
    }

    function agentCheckpoint(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(msg.sender == o.agent, "Only agent");
        require(o.status == OrderStatus.Shipped, "Invalid status");

        o.status = OrderStatus.AtCheckpoint;
        emit AgentCheckpoint(_id, msg.sender, _ipfsHash);
    }

    function deliverOrder(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(msg.sender == o.seller, "Only seller");
        require(o.status == OrderStatus.AtCheckpoint, "Invalid status");

        o.status = OrderStatus.Delivered;
        emit OrderDelivered(_id, msg.sender, _ipfsHash);
    }

    function confirmReceipt(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(msg.sender == o.buyer, "Only buyer");
        require(o.status == OrderStatus.Delivered, "Invalid status");

        o.status = OrderStatus.Completed;
        emit OrderCompleted(_id, msg.sender, _ipfsHash);
        
        _releaseFunds(_id, o.seller);
    }

    function raiseDispute(uint256 _id, string memory _ipfsHash) external {
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(msg.sender == o.buyer || msg.sender == o.seller, "Only buyer or seller");
        require(o.status != OrderStatus.Completed && o.status != OrderStatus.Resolved, "Already finished");

        o.status = OrderStatus.Disputed;
        emit OrderDisputed(_id, msg.sender, _ipfsHash);
    }

    function adminResolveDispute(uint256 _id, address _winner) external {
        require(isAuthorizedAdmin[msg.sender] || msg.sender == owner(), "Not authorized");
        Order storage o = orders[_id];
        require(!o.isMultichain, "Must execute on Mirror chain");
        require(o.status == OrderStatus.Disputed, "Not disputed");
        require(_winner == o.buyer || _winner == o.seller, "Invalid winner");

        o.status = OrderStatus.Resolved;
        emit OrderResolved(_id, msg.sender, _winner);
        
        _releaseFunds(_id, _winner);
    }

    // Called by the Relayer once multichain order finishes on BNB
    function relayerMarkBridged(uint256 _id) external onlyOwner {
        Order storage o = orders[_id];
        require(o.isMultichain, "Not multichain");
        require(!o.isBridged, "Already bridged");
        
        o.isBridged = true;
        o.status = OrderStatus.Completed; // Mark completed on source
        emit OrderBridged(_id);
        
        // Note: Funds remain locked in this contract Treasury to prevent balance 'reset' for the admin.
    }

    function _releaseFunds(uint256 _id, address _to) internal {
        Order storage o = orders[_id];
        if (o.tokenAddress == address(0)) {
            (bool success, ) = payable(_to).call{value: o.amount}("");
            require(success, "ETH transfer failed");
        } else {
            require(IERC20(o.tokenAddress).transfer(_to, o.amount), "USDT transfer failed");
        }
    }
}
