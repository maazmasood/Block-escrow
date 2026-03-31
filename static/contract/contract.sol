// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract SimpleEscrow {
    address public user1;             // Initiator/Payer
    address public user2;             // Receiver/Seller
    address public agent;             // Third-party intermediary
    uint256 public amount;            // Escrowed amount
    string public ipfsHash;           // IPFS document hash for contract details
    
    // Confirmation flags now enforce a sequence
    bool public user1Confirmed;       // 1. User1 must confirm first
    bool public agentConfirmed;       // 2. Agent must confirm second
    bool public user2Confirmed;       // 3. User2 must confirm last
    bool public isActive;             // Escrow status

    // Events to log important actions
    event EscrowCreated(address indexed initiator, address indexed receiver, address indexed agent, uint256 amount, string ipfsHash);
    event Confirmed(address indexed party, uint step);
    event FundsReleased(address indexed receiver, uint256 amount);

    constructor() {}

    /// @notice Initialize escrow with receiver, agent, IPFS hash, and deposit ETH
    /// @param _user2 The address of the receiver (seller).
    /// @param _agent The address of the third-party agent.
    /// @param _ipfsHash The IPFS hash pointing to the document/agreement.
    function createEscrow(address _user2, address _agent, string memory _ipfsHash) external payable {
        require(!isActive, "Escrow already active");
        require(msg.value > 0, "Must send ETH to escrow");
        require(_user2 != address(0) && _agent != address(0), "Invalid receiver or agent address");
        require(_user2 != msg.sender && _agent != msg.sender, "Agent or Receiver cannot be the initiator");
        require(_user2 != _agent, "Receiver and Agent cannot be the same address");

        user1 = msg.sender;
        user2 = _user2;
        agent = _agent;
        amount = msg.value;
        ipfsHash = _ipfsHash;
        isActive = true;

        // Reset confirmations for new escrow
        user1Confirmed = false;
        agentConfirmed = false;
        user2Confirmed = false;

        emit EscrowCreated(user1, user2, agent, amount, ipfsHash);
    }

    /// @notice Step 1: User1 confirms the escrow.
    function confirmUser1() external {
        require(isActive, "No active escrow");
        require(msg.sender == user1, "Only user1 can perform this confirmation (Step 1)");
        require(!user1Confirmed, "User1 already confirmed");
        
        user1Confirmed = true;
        emit Confirmed(msg.sender, 1);
    }

    /// @notice Step 2: Agent confirms the escrow, only after User1 has confirmed.
    function confirmAgent() external {
        require(isActive, "No active escrow");
        require(user1Confirmed, "User1 must confirm first (Step 1)");
        require(msg.sender == agent, "Only the designated agent can confirm (Step 2)");
        require(!agentConfirmed, "Agent already confirmed");
        
        agentConfirmed = true;
        emit Confirmed(msg.sender, 2);
    }

    /// @notice Step 3: User2 confirms the escrow, only after User1 and Agent have confirmed.
    function confirmUser2() external {
        require(isActive, "No active escrow");
        require(user1Confirmed && agentConfirmed, "User1 and Agent must confirm first (Steps 1 & 2)");
        require(msg.sender == user2, "Only user2 can perform this confirmation (Step 3)");
        require(!user2Confirmed, "User2 already confirmed");
        
        user2Confirmed = true;
        emit Confirmed(msg.sender, 3);
        
        // Final confirmation triggers release
        _releaseFunds();
    }

    /// @notice Internal release function
    function _releaseFunds() internal {
        // Funds are released only if ALL THREE parties have confirmed in order
        require(user1Confirmed && agentConfirmed && user2Confirmed, "Confirmations incomplete or out of order");
        require(address(this).balance >= amount, "Insufficient funds");
        
        isActive = false;

        (bool success, ) = payable(user2).call{value: amount}("");
        require(success, "Transfer failed");

        emit FundsReleased(user2, amount);
    }

    /// @notice Fallback function to prevent accidental ETH transfers without calling a function
    receive() external payable {
        revert("ETH cannot be sent directly to this contract.");
    }
}