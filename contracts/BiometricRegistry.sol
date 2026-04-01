// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title BiometricRegistry
 * @dev Decentralized Biometric Identity Verification Registry
 * @notice Implements Fuzzy Commitment Scheme (FCS) for privacy-preserving biometric authentication
 * 
 * Architecture:
 * - Enrollment Centers (EC): Register new subjects with biometric commitments
 * - Authentication Centers (AC): Verify identity claims
 * - Subjects: Users whose biometric identities are registered
 * 
 * Security Model:
 * - No raw biometric data stored on-chain
 * - Only cryptographic commitments (h(K), δ) stored
 * - Fuzzy Commitment Scheme allows matching within error tolerance
 */
contract BiometricRegistry {
    
    // ═══════════════════════════════════════════════════════════════
    //                         DATA STRUCTURES
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * @dev BiometricType enum for different biometric modalities
     */
    enum BiometricType {
        FACIAL,          // 0 - Facial recognition
        FINGERPRINT,     // 1 - Fingerprint scan
        IRIS,            // 2 - Iris pattern
        MULTIMODAL       // 3 - Combined modalities
    }
    
    /**
     * @dev Subject represents a registered identity with biometric commitment
     * Uses the Fuzzy Commitment Scheme:
     * - commitmentHash: h(K) where K is the secret key
     * - delta: δ = x ⊕ C where x is biometric template, C is error-correcting codeword
     */
    struct Subject {
        bytes32 subjectId;           // Unique identifier
        bytes32 commitmentHash;      // h(K) - hash of secret key
        bytes delta;               // δ = biometric ⊕ codeword
        string templateCID;          // IPFS CID for encrypted template
        BiometricType biometricType; // Type of biometric used
        address enrolledBy;          // EC that enrolled this subject
        uint256 enrolledAt;          // Enrollment timestamp
        uint256 updatedAt;           // Last update timestamp
        bool isActive;               // Active status
    }
    
    /**
     * @dev Node represents an Enrollment Center (EC) or Authentication Center (AC)
     */
    struct Node {
        uint256 nodeId;
        string name;
        address nodeAddress;
        bool isEnrollmentCenter;     // true = EC, false = AC only
        bool isAuthorized;
        uint256 registeredAt;
        uint256 enrollmentCount;     // Number of subjects enrolled (for ECs)
    }
    
    /**
     * @dev AuthRecord stores authentication attempts for audit
     */
    struct AuthRecord {
        bytes32 subjectId;
        address verifier;
        bool success;
        string reason;
        uint256 timestamp;
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                         STATE VARIABLES
    // ═══════════════════════════════════════════════════════════════
    
    address private _owner;
    
    // Counters
    uint256 private _subjectCount;
    uint256 private _nodeCount;
    uint256 private _authRecordCount;
    
    // Primary mappings
    mapping(bytes32 => Subject) private _subjects;
    mapping(address => Node) private _nodes;
    mapping(uint256 => AuthRecord) private _authRecords;
    
    // Existence checks
    mapping(bytes32 => bool) private _subjectExists;
    
    // Relationships
    mapping(address => bytes32[]) private _nodeEnrollments;
    
    // Enumeration arrays
    bytes32[] private _allSubjectIds;
    address[] private _allNodeAddresses;
    
    // ═══════════════════════════════════════════════════════════════
    //                              EVENTS
    // ═══════════════════════════════════════════════════════════════
    
    event SubjectEnrolled(
        bytes32 indexed subjectId,
        address indexed enrolledBy,
        BiometricType biometricType,
        uint256 timestamp
    );
    
    event SubjectUpdated(
        bytes32 indexed subjectId,
        address indexed updatedBy,
        uint256 timestamp
    );
    
    event SubjectDeactivated(
        bytes32 indexed subjectId,
        address indexed deactivatedBy,
        uint256 timestamp
    );
    
    event SubjectReactivated(
        bytes32 indexed subjectId,
        address indexed reactivatedBy,
        uint256 timestamp
    );
    
    event NodeRegistered(
        uint256 indexed nodeId,
        address indexed nodeAddress,
        string name,
        bool isEnrollmentCenter,
        uint256 timestamp
    );
    
    event NodeStatusChanged(
        address indexed nodeAddress,
        bool isAuthorized,
        uint256 timestamp
    );
    
    event AuthenticationLogged(
        bytes32 indexed subjectId,
        address indexed verifier,
        bool success,
        uint256 timestamp
    );
    
    event OwnershipTransferred(
        address indexed previousOwner,
        address indexed newOwner
    );
    
    // ═══════════════════════════════════════════════════════════════
    //                            MODIFIERS
    // ═══════════════════════════════════════════════════════════════
    
    modifier onlyOwner() {
        require(msg.sender == _owner, "BiometricRegistry: caller is not owner");
        _;
    }
    
    modifier onlyAuthorizedNode() {
        require(_nodes[msg.sender].isAuthorized, "BiometricRegistry: not authorized node");
        _;
    }
    
    modifier onlyEnrollmentCenter() {
        require(
            _nodes[msg.sender].isAuthorized && _nodes[msg.sender].isEnrollmentCenter,
            "BiometricRegistry: not an enrollment center"
        );
        _;
    }
    
    modifier subjectMustExist(bytes32 subjectId) {
        require(_subjectExists[subjectId], "BiometricRegistry: subject not found");
        _;
    }
    
    modifier subjectMustBeActive(bytes32 subjectId) {
        require(_subjects[subjectId].isActive, "BiometricRegistry: subject not active");
        _;
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                           CONSTRUCTOR
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * @dev Initializes the registry with deployer as owner and Main EC
     */
    constructor() {
        _owner = msg.sender;
        _nodeCount = 1;
        
        // Register deployer as Main Enrollment Center
        _nodes[msg.sender] = Node({
            nodeId: 1,
            name: "Main Enrollment Center",
            nodeAddress: msg.sender,
            isEnrollmentCenter: true,
            isAuthorized: true,
            registeredAt: block.timestamp,
            enrollmentCount: 0
        });
        
        _allNodeAddresses.push(msg.sender);
        
        emit NodeRegistered(1, msg.sender, "Main Enrollment Center", true, block.timestamp);
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                     SUBJECT MANAGEMENT
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * @dev Enroll a new subject with biometric commitment
     * @param subjectId Unique identifier for the subject
     * @param commitmentHash h(K) from Fuzzy Commitment Scheme
     * @param delta δ = x ⊕ C from Fuzzy Commitment Scheme
     * @param templateCID IPFS CID for encrypted biometric template
     * @param biometricType Type of biometric used
     */
    function enrollSubject(
        bytes32 subjectId,
        bytes32 commitmentHash,
        bytes calldata delta,
        string calldata templateCID,
        BiometricType biometricType
    ) external onlyEnrollmentCenter {
        require(subjectId != bytes32(0), "BiometricRegistry: invalid subject ID");
        require(commitmentHash != bytes32(0), "BiometricRegistry: invalid commitment hash");
        require(!_subjectExists[subjectId], "BiometricRegistry: subject already exists");
        
        _subjects[subjectId] = Subject({
            subjectId: subjectId,
            commitmentHash: commitmentHash,
            delta: delta,
            templateCID: templateCID,
            biometricType: biometricType,
            enrolledBy: msg.sender,
            enrolledAt: block.timestamp,
            updatedAt: block.timestamp,
            isActive: true
        });
        
        _subjectExists[subjectId] = true;
        _allSubjectIds.push(subjectId);
        _nodeEnrollments[msg.sender].push(subjectId);
        _nodes[msg.sender].enrollmentCount++;
        _subjectCount++;
        
        emit SubjectEnrolled(subjectId, msg.sender, biometricType, block.timestamp);
    }
    
    /**
     * @dev Update subject's biometric commitment (re-enrollment)
     */
    function updateSubject(
        bytes32 subjectId,
        bytes32 commitmentHash,
        bytes calldata delta,
        string calldata templateCID
    ) external onlyEnrollmentCenter subjectMustExist(subjectId) subjectMustBeActive(subjectId) {
        require(commitmentHash != bytes32(0), "BiometricRegistry: invalid commitment hash");
        
        Subject storage subject = _subjects[subjectId];
        subject.commitmentHash = commitmentHash;
        subject.delta = delta;
        subject.templateCID = templateCID;
        subject.updatedAt = block.timestamp;
        
        emit SubjectUpdated(subjectId, msg.sender, block.timestamp);
    }
    
    /**
     * @dev Deactivate a subject (revoke identity)
     */
    function deactivateSubject(bytes32 subjectId) 
        external 
        onlyEnrollmentCenter 
        subjectMustExist(subjectId) 
    {
        _subjects[subjectId].isActive = false;
        _subjects[subjectId].updatedAt = block.timestamp;
        
        emit SubjectDeactivated(subjectId, msg.sender, block.timestamp);
    }
    
    /**
     * @dev Reactivate a previously deactivated subject
     */
    function reactivateSubject(bytes32 subjectId) 
        external 
        onlyEnrollmentCenter 
        subjectMustExist(subjectId) 
    {
        _subjects[subjectId].isActive = true;
        _subjects[subjectId].updatedAt = block.timestamp;
        
        emit SubjectReactivated(subjectId, msg.sender, block.timestamp);
    }
    
    /**
     * @dev Get subject data for authentication
     */
    function getSubject(bytes32 subjectId) 
        external 
        view 
        onlyAuthorizedNode 
        subjectMustExist(subjectId)
        subjectMustBeActive(subjectId)
        returns (
            bytes32 id,
            bytes32 commitmentHash,
            bytes memory delta,
            string memory templateCID,
            BiometricType biometricType,
            uint256 enrolledAt
        ) 
    {
        Subject storage s = _subjects[subjectId];
        return (
            s.subjectId,
            s.commitmentHash,
            s.delta,
            s.templateCID,
            s.biometricType,
            s.enrolledAt
        );
    }
    
    /**
     * @dev Check if subject exists and their status
     */
    function checkSubjectStatus(bytes32 subjectId) 
        external 
        view 
        returns (bool exists, bool isActive) 
    {
        return (_subjectExists[subjectId], _subjects[subjectId].isActive);
    }
    
    /**
     * @dev Verify commitment hash matches (used in authentication)
     */
    function verifyCommitment(bytes32 subjectId, bytes32 providedHash) 
        external 
        view 
        onlyAuthorizedNode
        subjectMustExist(subjectId)
        subjectMustBeActive(subjectId)
        returns (bool) 
    {
        return _subjects[subjectId].commitmentHash == providedHash;
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                      AUTHENTICATION LOGGING
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * @dev Log an authentication attempt for audit trail
     */
    function logAuthentication(
        bytes32 subjectId,
        bool success,
        string calldata reason
    ) external onlyAuthorizedNode {
        _authRecordCount++;
        
        _authRecords[_authRecordCount] = AuthRecord({
            subjectId: subjectId,
            verifier: msg.sender,
            success: success,
            reason: reason,
            timestamp: block.timestamp
        });
        
        emit AuthenticationLogged(subjectId, msg.sender, success, block.timestamp);
    }
    
    /**
     * @dev Get authentication record by ID
     */
    function getAuthRecord(uint256 recordId) 
        external 
        view 
        onlyAuthorizedNode
        returns (
            bytes32 subjectId,
            address verifier,
            bool success,
            string memory reason,
            uint256 timestamp
        ) 
    {
        AuthRecord storage record = _authRecords[recordId];
        return (
            record.subjectId,
            record.verifier,
            record.success,
            record.reason,
            record.timestamp
        );
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                       NODE MANAGEMENT
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * @dev Register a new node (EC or AC)
     */
    function registerNode(
        address nodeAddress,
        string calldata name,
        bool isEnrollmentCenter
    ) external onlyEnrollmentCenter {
        require(nodeAddress != address(0), "BiometricRegistry: invalid address");
        require(_nodes[nodeAddress].nodeAddress == address(0), "BiometricRegistry: node exists");
        
        _nodeCount++;
        
        _nodes[nodeAddress] = Node({
            nodeId: _nodeCount,
            name: name,
            nodeAddress: nodeAddress,
            isEnrollmentCenter: isEnrollmentCenter,
            isAuthorized: true,
            registeredAt: block.timestamp,
            enrollmentCount: 0
        });
        
        _allNodeAddresses.push(nodeAddress);
        
        emit NodeRegistered(_nodeCount, nodeAddress, name, isEnrollmentCenter, block.timestamp);
    }
    
    /**
     * @dev Update node authorization status
     */
    function setNodeAuthorization(address nodeAddress, bool authorized) 
        external 
        onlyEnrollmentCenter 
    {
        require(_nodes[nodeAddress].nodeAddress != address(0), "BiometricRegistry: node not found");
        require(nodeAddress != _owner, "BiometricRegistry: cannot modify owner");
        
        _nodes[nodeAddress].isAuthorized = authorized;
        
        emit NodeStatusChanged(nodeAddress, authorized, block.timestamp);
    }
    
    /**
     * @dev Get node information
     */
    function getNode(address nodeAddress) 
        external 
        view 
        returns (
            uint256 nodeId,
            string memory name,
            bool isEnrollmentCenter,
            bool isAuthorized,
            uint256 registeredAt,
            uint256 enrollmentCount
        ) 
    {
        Node storage node = _nodes[nodeAddress];
        return (
            node.nodeId,
            node.name,
            node.isEnrollmentCenter,
            node.isAuthorized,
            node.registeredAt,
            node.enrollmentCount
        );
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                        ADMIN FUNCTIONS
    // ═══════════════════════════════════════════════════════════════
    
    /**
     * @dev Transfer ownership of the registry
     */
    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "BiometricRegistry: invalid new owner");
        
        address previousOwner = _owner;
        _owner = newOwner;
        
        // Transfer node privileges
        _nodes[newOwner] = _nodes[previousOwner];
        _nodes[newOwner].nodeAddress = newOwner;
        delete _nodes[previousOwner];
        
        _allNodeAddresses.push(newOwner);
        
        emit OwnershipTransferred(previousOwner, newOwner);
    }
    
    // ═══════════════════════════════════════════════════════════════
    //                        VIEW FUNCTIONS
    // ═══════════════════════════════════════════════════════════════
    
    function owner() external view returns (address) {
        return _owner;
    }
    
    function totalSubjects() external view returns (uint256) {
        return _subjectCount;
    }
    
    function totalNodes() external view returns (uint256) {
        return _nodeCount;
    }
    
    function totalAuthRecords() external view returns (uint256) {
        return _authRecordCount;
    }
    
    function isAuthorizedNode(address nodeAddress) external view returns (bool) {
        return _nodes[nodeAddress].isAuthorized;
    }
    
    function isEnrollmentCenter(address nodeAddress) external view returns (bool) {
        return _nodes[nodeAddress].isEnrollmentCenter && _nodes[nodeAddress].isAuthorized;
    }
    
    function getNodeEnrollments(address nodeAddress) 
        external 
        view 
        onlyAuthorizedNode
        returns (bytes32[] memory) 
    {
        return _nodeEnrollments[nodeAddress];
    }
}
