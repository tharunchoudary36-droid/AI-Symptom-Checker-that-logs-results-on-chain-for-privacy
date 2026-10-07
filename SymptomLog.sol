// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title SymptomLog
/// @notice Logs only a hash of an encrypted symptom-check session, its care level and a timestamp.
///         Symptoms are never on-chain. Care levels: 0 self-care, 1 see a doctor, 2 urgent care.
contract SymptomLog {
    struct Entry { bytes32 hash; uint8 careLevel; uint64 time; address user; }

    event CheckLogged(uint256 indexed id, address indexed user, bytes32 hash, uint8 careLevel, uint256 time);

    mapping(uint256 => Entry) public entries; // id => entry (ids start at 1)
    uint256 public count;

    /// @notice Log a session fingerprint (SHA-256 of the encrypted session).
    function log(bytes32 hash, uint8 careLevel) external returns (uint256 id) {
        require(careLevel <= 2, "bad care level");
        id = ++count;
        entries[id] = Entry(hash, careLevel, uint64(block.timestamp), msg.sender);
        emit CheckLogged(id, msg.sender, hash, careLevel, block.timestamp);
    }

    /// @notice Free check: does this hash match the one stored under id?
    function verify(uint256 id, bytes32 hash) external view returns (bool) {
        return hash != bytes32(0) && entries[id].hash == hash;
    }
}
