const { Web3 } = require('web3');
const web3 = new Web3('http://127.0.0.1:8545');

async function main() {
    try {
        const accounts = await web3.eth.getAccounts();
        accounts.forEach((acc, i) => console.log(`ACC_${i}: ${acc}`));
    } catch (e) {
        console.error('Error:', e);
    }
}

main();
