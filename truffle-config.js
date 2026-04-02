require('dotenv').config();
const HDWalletProvider = require('@truffle/hdwallet-provider');

module.exports = {
  networks: {
    development: {
      host: "127.0.0.1",
      port: 8545,
      network_id: "*",
    },
    sepolia: {
      provider: () => new HDWalletProvider(
        process.env.PRIVATE_KEY || process.env.MNEMONIC, 
        `https://eth-sepolia.g.alchemy.com/v2/-S_jlAhzwC3u6P2OQbH4i`
      ),
      network_id: 11155111,       // Sepolia's id
      gas: 5500000,        
      confirmations: 2,    
      timeoutBlocks: 200,  
      skipDryRun: true     
    }
  },
  compilers: {
    solc: {
      version: "0.8.20",
    },
  },
};