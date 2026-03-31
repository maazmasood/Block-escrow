import hre from "hardhat";
const { ethers } = hre;
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
  console.log("--- Deploying to BNB Network (8546) ---");
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);

  // 1. Deploy MockUSDT
  const MockUSDT = await hre.ethers.getContractFactory("MockUSDT");
  const usdtBnb = await MockUSDT.deploy();
  await usdtBnb.waitForDeployment();
  const usdtAddr = await usdtBnb.getAddress();
  console.log("MockUSDT (BNB) Deployed:", usdtAddr);

  // 2. Deploy EscrowMirror
  const EscrowMirror = await hre.ethers.getContractFactory("EscrowMirror");
  const mirror = await EscrowMirror.deploy(usdtAddr);
  await mirror.waitForDeployment();
  const mirrorAddr = await mirror.getAddress();
  console.log("EscrowMirror (BNB) Deployed:", mirrorAddr);

  // 3. Provide liquidity to the Mirror contract
  console.log("Minting liquidity to Mirror pool...");
  const initialLiquidity = ethers.parseUnits("1000000", 18);
  await usdtBnb.mint(mirrorAddr, initialLiquidity);
  console.log("MockUSDT liquidity seeded to Mirror pool.");

  // Update Config
  const configPath = path.join(__dirname, "../static/contract/multichain_config.json");
  let config = {};
  if (fs.existsSync(configPath)) {
    config = JSON.parse(fs.readFileSync(configPath, "utf-8"));
  }

  config.USDT_BNB = usdtAddr;
  config.BNB_MIRROR = mirrorAddr;

  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log("Updated multichain_config.json");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
