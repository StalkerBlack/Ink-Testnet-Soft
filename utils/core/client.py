import asyncio
import random

from web3.contract import AsyncContract
from web3.exceptions import TransactionNotFound, TimeExhausted
from web3 import AsyncHTTPProvider, AsyncWeb3
from web3.datastructures import AttributeDict


from .network import Network
from .logger import logger
from data.config import ERC20_ABI, NETWORK_TOKEN_CONTRACTS


class BlockchainException(Exception):
    pass

class SoftwareException(Exception):
    pass


class Client():
    def __init__(
            self, network: Network, private_key: str, name: str,
            proxy: None | str = None, ds_auth_token: None | str = None
        ):
        self.name = name
        self.network: Network = network
        self.proxy_init = proxy
        self.rpc = random.choice(self.network.rpc)
        self.request_kwargs = {"proxy": f'{proxy}', "verify_ssl": False} if proxy else {"verify_ssl": False}
        self.w3 = AsyncWeb3(AsyncHTTPProvider(self.rpc, request_kwargs=self.request_kwargs))
        self.private_key = private_key
        self.address = AsyncWeb3.to_checksum_address(self.w3.eth.account.from_key(private_key).address)

        self.ds_auth_token = ds_auth_token

    @staticmethod
    def get_user_agent():
        random_version = f"{random.uniform(520, 540):.2f}"
        return (f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/{random_version}'
                f' (KHTML, like Gecko) Chrome/121.0.0.0 Safari/{random_version} Edg/121.0.0.0')

    @staticmethod
    def get_normalize_error(error: Exception) -> Exception | str:
        try:
            if error.args:
                first_arg = error.args[0]
                
                if isinstance(first_arg, dict):
                    return first_arg.get('message', str(error))
                
                elif isinstance(first_arg, str):
                    return first_arg

            return str(error)
        except Exception as e:
            return f"Unexpected error: {str(e)}"



    async def change_rpc(self):
        logger.warning(f'Replacing RPC | {self.address}')

        if len(self.network.rpc) != 1:
            rpcs_list = [rpc for rpc in self.network.rpc if rpc != self.rpc]
            new_rpc = random.choice(rpcs_list)
            self.w3 = AsyncWeb3(AsyncHTTPProvider(new_rpc, request_kwargs=self.request_kwargs))
            logger.success(f'The RPC replacement was a success! | {self.address}')
        else:
            logger.error(f'Failed to change RPC | {self.address}')

    def get_contract(self, contract_address: str, abi: dict = ERC20_ABI) -> AsyncContract:
        return self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(contract_address),
            abi=abi
        )
        
    async def get_decimals(self, token_name: str = None) -> int:
        contract = await self.get_contract(NETWORK_TOKEN_CONTRACTS[token_name])
        return await contract.functions.decimals().call()
    
    async def get_normalize_amount(self, token_name: str, amount_in_wei: int) -> float:
        decimals = await self.get_decimals(token_name)
        return float(amount_in_wei / 10 ** decimals)
    
    async def get_token_balance(self, token: str = None, check_native: bool = False) -> int | None:
        if check_native:
            token_balance = await self.w3.eth.get_balance(self.address)
            return token_balance or None
        contract = await self.get_contract(NETWORK_TOKEN_CONTRACTS[token])
        token_balance = await contract.functions.balanceOf(self.address).call()
        return token_balance or None
    
    async def get_allowance(self, token_address: str, spender_address: str) -> int:
        contract = self.get_contract(token_address)
        return await contract.functions.allowance(
            self.address,
            spender_address
        ).call()
    
    async def get_priotiry_fee(self):
        fee_history = await self.w3.eth.fee_history(25, 'latest', [20.0])
        non_empty_block_priority_fees = [fee[0] for fee in fee_history["reward"] if fee[0] != 0]

        divisor_priority = max(len(non_empty_block_priority_fees), 1)

        priority_fee = int(round(sum(non_empty_block_priority_fees) / divisor_priority))

        return priority_fee
    
    async def prepare_transaction(self, value: int = 0):
        try:
            tx_params = {
                'from': self.address,
                'nonce': await self.w3.eth.get_transaction_count(self.address),
                'value': value,
                'chainId': self.network.chain_id
            }
            if self.network.eip1559_support:
                base_fee = await self.w3.eth.gas_price
                max_priority_fee_per_gas = await self.get_priotiry_fee()
                max_fee_per_gas = base_fee + max_priority_fee_per_gas
                tx_params['maxPriorityFeePerGas'] = max_priority_fee_per_gas
                tx_params['maxFeePerGas'] = int(max_fee_per_gas * 1.25)
                tx_params['type'] = '0x2'
            else:
                tx_params['gasPrice'] = int(await self.w3.eth.gas_price * 1.25)

            return tx_params
        except Exception as error:
            raise BlockchainException(f'{self.get_normalize_error(error)}')
        
    async def send_transaction(self, transaction, need_hash: bool = False, without_gas: bool = False,
                            poll_latency: int = 10, timeout: int = 360):
        try:
            estimated_gas = await self.w3.eth.estimate_gas(transaction)
            transaction['gas'] = min(int(estimated_gas * 1.25), 10_000_000)
        except Exception as error:
            normalized_error = self.get_normalize_error(error)
            logger.error(f'Failed to estimate gas: {normalized_error} | {self.address}')
            return False

        try:
            signed_tx = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = await self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        except Exception as error:
            normalized_error = self.get_normalize_error(error)
            logger.error(f'Failed to send transaction: {normalized_error} | {self.address}')
            return False

        try:
            total_time = 0
            while True:
                try:
                    receipts = await self.w3.eth.get_transaction_receipt(tx_hash)
                    status = receipts.get("status") if isinstance(receipts, dict) else receipts["status"]
                    
                    if status == 1:
                        logger.success(f'Transaction successful: {self.network.explorer}/tx/{tx_hash.hex()} | {self.address}')
                        return tx_hash if need_hash else True
                    elif status is None:
                        await asyncio.sleep(poll_latency)
                    else:
                        logger.error(f'Transaction failed: {self.network.explorer}/tx/{tx_hash.hex()}')
                        return False
                except TransactionNotFound:
                    if total_time > timeout:
                        logger.error(f'Transaction not found after {timeout} seconds')
                        return False
                    total_time += poll_latency
                    await asyncio.sleep(poll_latency)
                except Exception as error:
                    normalized_error = self.get_normalize_error(error)
                    logger.error(f'Error checking transaction status: {normalized_error} | {self.address}')
                    total_time += poll_latency
                    await asyncio.sleep(poll_latency)
        except Exception as error:
            normalized_error = self.get_normalize_error(error)
            logger.error(f'Unexpected error during transaction: {normalized_error} | {self.address}')
            return False
