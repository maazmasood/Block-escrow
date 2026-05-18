@echo off
title Multichain Escrow Launcher

echo ==========================================
echo Starting Multichain Escrow Environment...
echo ==========================================

REM ------------------------------------------
REM 1. Start Ethereum Hardhat Node
REM ------------------------------------------
echo Launching ETH Node on 8545...
start "ETH Chain - Hardhat 8545" cmd /k "npx hardhat node --port 8545"

timeout /t 5 /nobreak > nul

REM ------------------------------------------
REM 2. Start BNB Hardhat Node
REM ------------------------------------------
echo Launching BNB Node on 8546...
start "BNB Chain - Hardhat 8546" cmd /k "npx hardhat node --port 8546"

timeout /t 5 /nobreak > nul

REM ------------------------------------------
REM 3. Deploy Contracts + Start IPFS
REM ------------------------------------------
echo Launching Deployment & IPFS...
start "Deploy + IPFS" cmd /c "echo Deploying ETH contracts... && npx hardhat run scripts/deploy_eth.js --network eth_chain && timeout /t 5 && echo Deploying BNB contracts... && npx hardhat run scripts/deploy_bnb.js --network bnb_chain && timeout /t 5 && echo Starting IPFS daemon... && ipfs daemon"

timeout /t 10 /nobreak > nul

REM ------------------------------------------
REM 4. Fund Users + Start Flask App
REM ------------------------------------------
echo Initializing Backend and Funding...
start "Fund Users + Flask Backend" cmd /c "echo Funding users... && python fund_users.py && timeout /t 5 && echo Starting Flask backend... && python app.py"

timeout /t 8 /nobreak > nul

REM ------------------------------------------
REM 5. Start Relayer
REM ------------------------------------------
echo Launching Relayer...
start "Cross-Chain Relayer" cmd /k "python relayer.py"

echo.
echo ==========================================
echo All services launched successfully.
echo ==========================================

pause