import hre from "hardhat";
const { ethers } = hre;
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  console.log("--- Deploying to ETH Network (8545) ---");
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  // 1. Deploy MockUSDT
  const MockUSDT = await hre.ethers.getContractFactory("MockUSDT");
  const usdtEth = await MockUSDT.deploy();
  await usdtEth.waitForDeployment();
  const usdtAddr = await usdtEth.getAddress();
  console.log("MockUSDT (ETH) Deployed:", usdtAddr);

  // 2. Deploy SupplyChainSource
  const SupplyChainSource = await hre.ethers.getContractFactory("SupplyChainSource");
  const source = await SupplyChainSource.deploy();
  await source.waitForDeployment();
  const sourceAddr = await source.getAddress();
  console.log("SupplyChainSource (ETH) Deployed:", sourceAddr);

  // Update Config
  const configPath = path.join(__dirname, "../static/contract/multichain_config.json");
  let config = {};
  if (fs.existsSync(configPath)) {
    config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
  }

  config.USDT_ETH = usdtAddr;
  config.ETH_SOURCE = sourceAddr;

  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log("Updated multichain_config.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
