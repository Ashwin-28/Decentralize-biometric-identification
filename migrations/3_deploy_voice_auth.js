const VoiceAuth = artifacts.require("VoiceAuth");

module.exports = function (deployer) {
  deployer.deploy(VoiceAuth);
};
