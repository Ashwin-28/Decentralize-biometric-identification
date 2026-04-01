// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract VoiceAuth {
    mapping(string => string) public userHashes;

    function storeHash(string memory userId, string memory hashValue) public {
        userHashes[userId] = hashValue;
    }

    function getHash(string memory userId) public view returns (string memory) {
        return userHashes[userId];
    }
}
