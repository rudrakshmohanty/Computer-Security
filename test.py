from brownie import Certificate, accounts
account = accounts[0]  # Use first Ganache account
certificate_contract = Certificate.deploy({'from': account})
print("Contract Address:", certificate_contract.address)
