import hashlib
import time
import json

class Block:
    def __init__(self, index, timestamp, data, previous_hash=''):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.hash = self.calculate_hash()
    
    def calculate_hash(self):
        """Calculate the hash of the block"""
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash
        }, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

class Blockchain:
    def __init__(self):
        """Initialize a new blockchain with a genesis block"""
        self.chain = [self.create_genesis_block()]
    
    def create_genesis_block(self):
        """Create the first block in the blockchain"""
        return Block(0, time.time(), {"message": "Genesis Block"}, "0")
    
    def get_latest_block(self):
        """Return the most recent block in the chain"""
        return self.chain[-1]
    
    def add_block(self, data):
        """Add a new block to the blockchain"""
        index = len(self.chain)
        timestamp = time.time()
        previous_hash = self.get_latest_block().hash
        new_block = Block(index, timestamp, data, previous_hash)
        self.chain.append(new_block)
        return new_block
    
    def is_chain_valid(self):
        """Verify the blockchain is valid"""
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i-1]
            
            # Verify current block's hash
            if current_block.hash != current_block.calculate_hash():
                return False
            
            # Verify chain link (previous hash reference)
            if current_block.previous_hash != previous_block.hash:
                return False
        
        return True

# Create the blockchain instance to be imported by other modules
blockchain = Blockchain()

# Add some test blocks if running this file directly
if __name__ == "__main__":
    blockchain.add_block({"certificate_id": "CERT001", "name": "Test Certificate"})
    blockchain.add_block({"certificate_id": "CERT002", "name": "Another Certificate"})
    
    print("Blockchain valid:", blockchain.is_chain_valid())
    
    # Print the entire blockchain
    for block in blockchain.chain:
        print(f"Block #{block.index}")
        print(f"Timestamp: {block.timestamp}")
        print(f"Data: {block.data}")
        print(f"Hash: {block.hash}")
        print(f"Previous Hash: {block.previous_hash}")
        print("---")