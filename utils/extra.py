import re

from web3 import AsyncWeb3
from faker import Faker

from utils.core import*
from data.config import*
from generall_settings import MIN_AVAILABLE_BALANCE

faker = Faker()


class Extra:
    def __init__(self, client: Client):
        self.client: Client = client 

    def control_balance(self, balance: int, min_available_balance = MIN_AVAILABLE_BALANCE) -> bool:
        if balance is None:
            logger.warning(
                f"{self.client.name} | Failed to get a balance for the address: {self.client.address}"
                f"Most likely the balance is completely empty of tokens {self.client.network.token}"
            )
            return False

        if balance < min_available_balance:
            logger.warning(
                f"{self.client.name} | Insufficient {self.client.network.token} "
                f"for the transaction, on the network: {self.client.network.name} | Address: {self.client.address} "
                f"You need at least {(min_available_balance/10**18)} {self.client.network.token}"
            )
            return False
        return True

    async def register_domen(self):
        logger.info(
            f'{self.client.name} | Domain Registration with Ink Sepolia'
        )

        balance = await self.client.get_token_balance(check_native=True)

        if not self.control_balance(balance=balance):
            return 

        contract_address = AsyncWeb3.to_checksum_address(
            '0xf180136DdC9e4F8c9b5A9FE59e2b1f07265C5D4D'
        )
        contract = self.client.w3.eth.contract(
            address=contract_address, abi=ZNS_CONNECT
        )
        while True:
            domain_name = faker.domain_name()
            name = re.split(r'\.', domain_name)[0]

            owners = [self.client.address]
            domain_names = [name]
            expiries = [1]
            referral = AsyncWeb3.to_checksum_address('0x0000000000000000000000000000000000000000')
            credits = 0

            length_of_domain = len(domain_names[0])

            price = await contract.functions.priceToRegister(length_of_domain).call()

            tx_params = await self.client.prepare_transaction(value=price)
            transaction = await contract.functions.registerDomains(
                owners,
                domain_names,
                expiries,
                referral,
                credits
            ).build_transaction(tx_params)
            try:
                await self.client.send_transaction(tx_params, need_hash=True)
            except Exception as e:
                if '0x3a81d6fc' in str(e):
                    logger.warning(f"Domain {domain_names} already registered, skipping...")
                    continue
                else:
                    raise e
            return