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
      accounts: [
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
        "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
        "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
        "0x47e171e0ec23374c6519b88dd68a322e71ead9938b98166946059e0a0f822cc0",
        "0x8b3a350cf5c34c9194bb852029B96E8f11b98bbfba97217855321303865ea30b",
        "0xea6c4434a9ee69a712f5a5602e1a383f9828d3bd6f87f0b5d9852f53d2629b13",
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
      ]
    },
    bnb_chain: {
      url: "http://127.0.0.1:8546",
      accounts: [
        "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80",
        "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d",
        "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a",
        "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6",
        "0x47e171e0ec23374c6519b88dd68a322e71ead9938b98166946059e0a0f822cc0",
        "0x8b3a350cf5c34c9194bb852029B96E8f11b98bbfba97217855321303865ea30b",
      ]
    },
    sepolia: {
      url: process.env.SEPOLIA_RPC_URL || "https://eth-sepolia.g.alchemy.com/v2/mock",
      accounts: [process.env.SEPOLIA_PRIVATE_KEY || "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"],
    }
  },
};

module.exports = config;
