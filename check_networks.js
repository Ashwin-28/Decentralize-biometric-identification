const fs = require('fs');
const json = JSON.parse(fs.readFileSync('./build/contracts/BiometricRegistry.json', 'utf8'));
for (const netId in json.networks) {
    console.log(`NETWORK_${netId}: ${json.networks[netId].address}`);
}
