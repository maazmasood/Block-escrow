// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract EscrowSource is Ownable {
    IERC20 public usdt;
    
    struct Escrow {
        address buyer;
        address seller;
        address agent;
        uint256 amount;
        string ipfsHash;
        bool agentConfirmed;
        bool isBridged; // True when User B confirms on BNB
    }

    mapping(uint256 => Escrow) public escrows;
    uint256 public nextEscrowId;

    event EscrowFunded(uint256 indexed id, address buyer, address seller, address agent, uint256 amount, string ipfsHash);
    event AgentConfirmed(uint256 indexed id, address agent);
    event EscrowBridged(uint256 indexed id);

    constructor(address _usdt) Ownable(msg.sender) {
        usdt = IERC20(_usdt);
    }

    function createEscrow(address _seller, address _agent, uint256 _amount, string memory _ipfsHash) external {
        require(_amount > 0, "Amount must be > 0");
        require(usdt.transferFrom(msg.sender, address(this), _amount), "USDT transfer failed");

        uint256 id = nextEscrowId++;
        escrows[id] = Escrow(msg.sender, _seller, _agent, _amount, _ipfsHash, false, false);

        emit EscrowFunded(id, msg.sender, _seller, _agent, _amount, _ipfsHash);
    }

    function confirmAgent(uint256 _id) external {
        Escrow storage e = escrows[_id];
        require(msg.sender == e.agent, "Only Agent can confirm");
        require(!e.agentConfirmed, "Already confirmed");

        e.agentConfirmed = true;
        emit AgentConfirmed(_id, msg.sender);
    }

    // Called by the Relayer once User B confirms on BNB
    function relayerMarkBridged(uint256 _id) external onlyOwner {
        Escrow storage e = escrows[_id];
        require(!e.isBridged, "Already bridged");
        e.isBridged = true;
        emit EscrowBridged(_id);
    }
}
