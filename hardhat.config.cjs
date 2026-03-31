require("@nomicfoundation/hardhat-toolbox");

const config = {
  paths: {
    sources: "./static/contract",
  },
  solidity: {
    compilers: [
      {
        version: "0.8.20", 
      },
      {
        version: "0.8.28",
      }
    ]
  },

  networks: {
    eth_chain: {
      url: "http://127.0.0.1:8545",
      accounts: ["0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"]
    },
    bnb_chain: {
      url: "http://127.0.0.1:8546",
      accounts: ["0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"]
    },
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL || "https://eth-sepolia.g.alchemy.com/v2/mock",
      accounts: [process.env.SEPOLIA_PRIVATE_KEY || "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"],
    }
  },
};

module.exports = config;
