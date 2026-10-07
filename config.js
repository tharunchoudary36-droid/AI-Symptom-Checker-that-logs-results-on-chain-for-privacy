// Edit after deploying the contract. Everything in this folder is public: no secrets here.
window.CONFIG = {
  CONTRACT_ADDRESS: "0x6621E321923202d191aAAA5DfE81236650c52F46",
  BACKEND_URL: "http://localhost:5000",
  CHAIN_ID: 11155111, // Ethereum Sepolia
  CHAIN_NAME: "Ethereum Sepolia",
  EXPLORER: "https://sepolia.etherscan.io",
  ABI: [
    "function log(bytes32 hash, uint8 careLevel) returns (uint256)",
    "function verify(uint256 id, bytes32 hash) view returns (bool)",
    "function entries(uint256) view returns (bytes32 hash, uint8 careLevel, uint64 time, address user)",
    "event CheckLogged(uint256 indexed id, address indexed user, bytes32 hash, uint8 careLevel, uint256 time)"
  ]
};
