const BiometricRegistry = artifacts.require("BiometricRegistry");
const FingerprintRegistry = artifacts.require("FingerprintRegistry");

module.exports = function (deployer) {
  deployer.deploy(BiometricRegistry);
  deployer.deploy(FingerprintRegistry);
};
