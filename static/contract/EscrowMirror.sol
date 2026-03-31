// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract EscrowMirror is Ownable {
    IERC20 public usdt;

    struct Escrow {
        uint256 ethId;
        address buyer;
        address seller;
        address agent;
        uint256 amount;
        string ipfsHash;
        bool confirmedByBNB;
        bool released;
    }

    mapping(uint256 => Escrow) public escrows;
    uint256 public nextEscrowId;

    event MirrorInitialized(uint256 indexed id, uint256 ethId, address buyer, address seller, uint256 amount);
    event UserBConfirmed(uint256 indexed id, address seller);
    event FundsReleasedBNB(uint256 indexed id, address seller, uint256 amount);

    constructor(address _usdt) Ownable(msg.sender) {
        usdt = IERC20(_usdt);
    }

    // Called by the Relayer to sync from ETH
    function syncFromETH(uint256 _ethId, address _buyer, address _seller, address _agent, uint256 _amount, string memory _ipfsHash) external onlyOwner {
        uint256 id = nextEscrowId++;
        escrows[id] = Escrow(_ethId, _buyer, _seller, _agent, _amount, _ipfsHash, false, false);
        emit MirrorInitialized(id, _ethId, _buyer, _seller, _amount);
    }

    function confirmUserB(uint256 _id) external {
        Escrow storage e = escrows[_id];
        require(msg.sender == e.seller, "Only Seller can confirm");
        require(!e.confirmedByBNB, "Already confirmed");

        e.confirmedByBNB = true;
        emit UserBConfirmed(_id, msg.sender);
        
        // Final release
        _releaseFunds(_id);
    }

    function _releaseFunds(uint256 _id) internal {
        Escrow storage e = escrows[_id];
        require(e.confirmedByBNB, "Confirmation required");
        require(!e.released, "Already released");
        
        require(usdt.balanceOf(address(this)) >= e.amount, "Insufficient USDT in Mirror pool");
        
        e.released = true;
        require(usdt.transfer(e.seller, e.amount), "USDT transfer failed on BNB");
        
        emit FundsReleasedBNB(_id, e.seller, e.amount);
    }

    // Function for owner to provide liquidity (for demo purposes)
    function depositLiquidity(uint256 amount) external {
        require(usdt.transferFrom(msg.sender, address(this), amount), "Liquidity transfer failed");
    }
}
