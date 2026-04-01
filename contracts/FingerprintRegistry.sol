// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title FingerprintRegistry
 * @dev Secure storage for fingerprint hashes as per technical specifications.
 */
contract FingerprintRegistry {
    
    struct UserRecord {
        string userId;
        string fingerprintHash;
        uint256 timestamp;
        bool isRegistered;
    }
    
    mapping(string => UserRecord) private records;
    string[] private userList;
    
    event Registered(string userId, string fingerprintHash, uint256 timestamp);
    
    /**
     * @dev Register a new fingerprint hash for a user
     */
    function registerFingerprint(string memory _userId, string memory _fingerprintHash) public {
        require(!records[_userId].isRegistered, "User already registered");
        
        records[_userId] = UserRecord({
            userId: _userId,
            fingerprintHash: _fingerprintHash,
            timestamp: block.timestamp,
            isRegistered: true
        });
        
        userList.push(_userId);
        emit Registered(_userId, _fingerprintHash, block.timestamp);
    }
    
    /**
     * @dev Retrieve the stored fingerprint hash for verification logic
     */
    function getFingerprintHash(string memory _userId) public view returns (string memory) {
        require(records[_userId].isRegistered, "User not found");
        return records[_userId].fingerprintHash;
    }
    
    /**
     * @dev Verify if a user exists
     */
    function verifyFingerprint(string memory _userId) public view returns (bool) {
        return records[_userId].isRegistered;
    }
    
    /**
     * @dev Get all registered user IDs
     */
    function getAllRegisteredUsers() public view returns (string[] memory) {
        return userList;
    }
    
    /**
     * @dev Get detailed record
     */
    function getUserRecord(string memory _userId) public view returns (string memory, string memory, uint256) {
        UserRecord storage record = records[_userId];
        return (record.userId, record.fingerprintHash, record.timestamp);
    }
}
