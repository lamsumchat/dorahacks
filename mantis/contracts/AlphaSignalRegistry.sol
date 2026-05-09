// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AlphaSignalRegistry — immutable on-chain record of AI-generated trading signals
/// @notice Stores only hashes + lightweight metadata. Full reasoning lives off-chain.
contract AlphaSignalRegistry {
    struct Signal {
        bytes32 contentHash;
        uint64  timestamp;
        address emitter;
        string  asset;
        int8    direction;   // 1 = bullish, -1 = bearish, 0 = neutral
        uint8   confidence;  // 0-100
        string  timeHorizon;
    }

    Signal[] public signals;

    event SignalEmitted(
        uint256 indexed signalId,
        bytes32 contentHash,
        string  asset,
        int8    direction,
        uint8   confidence
    );

    function emitSignal(
        bytes32 _contentHash,
        string calldata _asset,
        int8 _direction,
        uint8 _confidence,
        string calldata _timeHorizon
    ) external returns (uint256) {
        uint256 id = signals.length;
        signals.push(Signal({
            contentHash: _contentHash,
            timestamp: uint64(block.timestamp),
            emitter: msg.sender,
            asset: _asset,
            direction: _direction,
            confidence: _confidence,
            timeHorizon: _timeHorizon
        }));
        emit SignalEmitted(id, _contentHash, _asset, _direction, _confidence);
        return id;
    }

    function verifySignal(uint256 _id, bytes calldata _content)
        external view returns (bool)
    {
        return signals[_id].contentHash == sha256(_content);
    }

    function getSignalCount() external view returns (uint256) {
        return signals.length;
    }
}
