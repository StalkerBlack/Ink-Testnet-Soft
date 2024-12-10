import random
import os
import json
import asyncio

from datetime import datetime, timedelta
from web3 import AsyncWeb3
from eth_abi import encode
from curl_cffi.requests import AsyncSession
from typing import Union

from utils.core import*
from data.config import*
from generall_settings import MIN_AVAILABLE_BALANCE, RANDOM_RANGE, ROUNDING_LEVELS


class Worker():
    def __init__(self, client: Client):
        self.client: Client = client  

        self.gm_check_time = 'data/gm_check_time.json'
        self.feedback = 'data/feedback.json'
        self.deploy_erc_721 = 'data/deploy_contract_erc_721.json'

        self.ds_headers = {
                    'authority': 'discord.com',
                    'accept': '*/*',
                    'authorization': self.client.ds_auth_token,
                    'content-type': 'application/json',
                    'user-agent': self.client.get_user_agent(),
                }

    @staticmethod
    def generate_random_greeting():
        greetings_dict = {
            "greetings": [
                "Hello", "Hi", "Greetings", "Hey", "Howdy", "Salutations", 
                "What's up", "Yo", "Welcome", "Hey there", "Nice to meet you", 
                "How's it going?", "Good to see you", "Glad you're here", 
                "What's happening?", "How's everything?", "What's new?", "Cheers"
            ],
            "questions": [
                "How are you?", "How's it going?", "How are you today?", "What's new?", 
                "How do you do?", "What's up?", "What's going on?", "What's happening?", 
                "How have you been?", "How's life?", "What's good?", "How's everything?", 
                "What are you up to?", "How's your day?", "What have you been up to?", 
                "Feeling good today?", "What’s new with you?", "How's your mood?", 
                "What's on your mind?"
            ],
            "forms_of_address": [
                "friend", "buddy", "stranger", "partner", "sir", "ma'am", 
                "user", "companion", "mate", "pal", "dude", "bro", "sis", "chief", 
                "champ", "professor", "boss", "champion", "maverick", "captain", 
                "hero", "matey", "buddy ol' pal", "leader", "advisor", "colleague"
            ],
            "emojis": [
                "😊", "👋", "😎", "🌟", "🤖", "💫", "✨", "🎉", "🤩", "🥳", "💥", 
                "🔥", "💪", "🙏", "😃", "🤗", "🌻", "🦄", "🤖", "👑", "🥰", 
                "😜", "🙌", "🌺", "💖", "🍀", "☀️", "💬", "💡", "🌙", "🎶", "🥺"
            ]
        }
        
        greeting = random.choice(greetings_dict["greetings"])
        question = random.choice(greetings_dict["questions"])
        address = random.choice(greetings_dict["forms_of_address"])
        emoji = random.choice(greetings_dict["emojis"])

        string =  f"{greeting}, {address}! {question} {emoji}"

        return string

    async def searh_contract_address(self):
        url = f'https://explorer-sepolia.inkonchain.com/api/v2/addresses/{self.client.address}/transactions?filter=to%3DNone'
        async with AsyncSession() as session:
            try:
                response = await session.get(
                    url=url, proxy=self.client.proxy_init
                )

                if response.status_code != 200:
                    logger.error(f'{self.client.name} |Request error: {response.status_code}')
                    return False
                
                data = response.json()

                if data.get('items'):
                    for transaction in data['items']:
                        if transaction.get('created_contract'):
                            contract_hash = transaction['created_contract'].get('hash')
                            transaction_hash = transaction.get('hash')
                            
                            if contract_hash and transaction_hash:
                                return contract_hash, transaction_hash
                    
                    logger.warning(f'{self.client.name} | No transactions with contract creation')
                else:
                    logger.warning(f'{self.client.name} | No transactions at all')

            except Exception as e:
                logger.error(f'{self.client.name} |Request error of the contract address: {e}')
                return False

    def load_progress(self, file):
        os.makedirs(os.path.dirname(file), exist_ok=True)

        if not os.path.exists(file):
            with open(file, 'w') as f:
                json.dump({}, f, indent=4)
            return {}

        try:
            with open(file, 'r') as f:
                progress = json.load(f)
                if not isinstance(progress, dict):
                    logger.error(f"Incorrect data format in {file}. Expected dictionar")
                    return {}
                return progress
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"File read error {file}: {e}")
            return {}
        
    def check_last_request(self, address, file):
        progress = self.load_progress(file)
        
        if address not in progress or 'timestamp' not in progress[address]:
            return False
        
        last_time = datetime.fromisoformat(progress[address]['timestamp'])
        time_since_last_gm = datetime.now() - last_time
        
        return time_since_last_gm < timedelta(hours=24)
        
    def save_progress(self, progress, file):
        try:
            with open(file, 'w') as f:
                json.dump(progress, f, indent=4)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"File saving error {file}: {e}")

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
    
    def get_value(
            self,
        balance: int, 
        random_range: tuple[float, float] = RANDOM_RANGE, 
        rounding_levels: tuple[int, int] = ROUNDING_LEVELS
    ) -> Union[tuple[int, float], bool]:

        random_percent = random.uniform(*random_range)
        
        normalized_balance = balance / 10 ** 18

        if normalized_balance < 0.003:
            logger.warning(
                f"{self.client.name} | Insufficient {self.client.network.token} "
                f"for the swap, in network: {self.client.network.name} | Address: {self.client.address}"
            )
            return False

        elif normalized_balance > 1:
            normalized_value = round(1 * random_percent, random.randint(*rounding_levels))
        else:
            normalized_value = round(normalized_balance * random.uniform(0.2, 0.4), random.randint(*rounding_levels))
        
        value = int(normalized_value * 10 ** 18)
        
        return value, normalized_value
        
    async def bridge_sepolia_to_ink(self):
        logger.info(
            f'{self.client.name} | Swap ETH from Sepolia to Ink'
        )

        balance = await self.client.get_token_balance(check_native=True)

        if not self.control_balance(balance=balance):
            return
        
        value, balance = self.get_value(balance=balance)
        if value is False:
            return
        
        logger.info(
            f"{self.client.name} | Swap {balance} {self.client.network.token}"
            f" from Sepolia to Ink | Address: {self.client.address}"
        )
        contract_address = AsyncWeb3.to_checksum_address(
            '0x33f60714BbD74d62b66D79213C348614DE51901C'
        )
        
        tx_params = await self.client.prepare_transaction(value=value)
        transaction = {
            **tx_params,
            'to': contract_address,
            'data': '0x'
        }
        await self.client.send_transaction(transaction, need_hash=True)

    async def bridge_ink_to_sepolia(self):
        # soon
        pass

    async def deploy_contract_erc_721(self):

        progress = self.load_progress(file=self.deploy_erc_721)

        if self.client.address in progress:
            logger.warning(f"{self.client.name} | The rollout of the ERC-721 contract is skipped because it has already been done")
            return

        logger.info(
            f'{self.client.name} | ERC-721 contract deployment to Ink Sepolia'
        )

        balance = await self.client.get_token_balance(check_native=True)

        if not self.control_balance(balance=balance, min_available_balance=2000000000000000):
            return        

        tx_params = await self.client.prepare_transaction()
        transcation = {**tx_params, 'data': ERC_721_BYTE_CODE}
        tx = await self.client.send_transaction(transcation)

        if not tx:
            logger.error(f"{self.client.address} | Error when deploying an ERC-721 contract")
            return False
        
        await asyncio.sleep(5)
        
        contract_address, _ = await self.searh_contract_address()
        
        progress[self.client.address] = {
            "verificationContract": {
                contract_address: False
            },
            "setGreeting": False,
            "feedBackDiscord": False
        }
        self.save_progress(progress, file=self.deploy_erc_721)

    async def verif_contract_erc_721(self):
        progress = self.load_progress(file=self.deploy_erc_721)

        if self.client.address not in progress:
            logger.warning(f"{self.client.name} | The ERC-721 contract has not yet been created, it is not possible to verify the contract")
            return
        
        contract_address, _ = await self.searh_contract_address()
        if not contract_address:
            return
        
        verification_contract = (
            progress
            .setdefault(self.client.address, {})
            .setdefault("verificationContract", {})
        ).get(contract_address, False)

        if verification_contract:
            logger.warning(f"{self.client.name} | The ERC-721 contract has already been verified")
            return
        
        logger.info(
            f'{self.client.name} | Verification of ERC-721 contract in Ink Sepolia'
        )
        
        url = f'https://explorer-sepolia.inkonchain.com/api/v2/smart-contracts/{contract_address}/verification/via/flattened-code'

        headers = {
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': 'https://explorer-sepolia.inkonchain.com',
            'referer': f'https://explorer-sepolia.inkonchain.com/address/{contract_address}/contract-verification',
            'user-agent': self.client.get_user_agent(),
        }

        json = {
            'compiler_version': 'v0.8.19+commit.7dd6d404',
            'source_code': '// SPDX-License-Identifier: MIT\npragma solidity ^0.8.19;\n \ncontract InkContract {\n    string public greeting = "Hello, Ink!";\n    \n    function setGreeting(string memory _greeting) public {\n        greeting = _greeting;\n    }\n}',
            'is_optimization_enabled': True,
            'is_yul_contract': False,
            'optimization_runs': '200',
            'evm_version': 'default',
            'autodetect_constructor_args': False,
            'constructor_args': '',
            'license_type': 'mit',
        }

        async with AsyncSession() as session:
            try:
                response = await session.post(
                    url=url, headers=headers, json=json, proxy=self.client.proxy_init
                )

                if response.status_code != 200:
                    logger.error(f'{self.client.name} |Request error: {response.status_code}')
                    return False
                
                logger.success(f'{self.client.name} | Successfully verified the contract. Contract address: {contract_address}')

                progress[self.client.address]["verificationContract"][contract_address] = True
                self.save_progress(progress, file=self.deploy_erc_721)

            except Exception as e:
                logger.error(f'{self.client.name} | Contract verification error: {e}')
                return False

    async def set_greeting(self):
        progress = self.load_progress(file=self.deploy_erc_721)

        if self.client.address not in progress:
            logger.warning(f"{self.client.name} | The ERC-721 contract has not yet been created, it is not possible to change the salutation")
            return

        set_greeting_value = (
            progress
            .setdefault(self.client.address, {})
            .get("setGreeting", False)
        )
        if set_greeting_value:
            logger.warning(f"{self.client.name} | The ERC-721 contract greeting change is skipped because it has already been executed")
            return

        logger.info(
            f'{self.client.name} | ERC-721 contract greeting change in Ink Sepolia'
        )

        balance = await self.client.get_token_balance(check_native=True)

        if not self.control_balance(balance=balance):
            return 

        contract_address, _ = await self.searh_contract_address()
        if not contract_address:
            logger.error(f"{self.client.name} | Request error of the contract address")
            return

        greeting = self.generate_random_greeting()
        encoded_parameters: bytes = encode(['string'], [greeting])
        data: bytes = bytes.fromhex("a4136862") + encoded_parameters

        tx_params = await self.client.prepare_transaction()
        transaction = {
            **tx_params,
            'to': contract_address,
            'data': data
        }
        tx = await self.client.send_transaction(transaction, need_hash=True)

        if not tx:
            logger.error(f"{self.client.address} | Error when changing the welcome message of the ERC-721 contract")
            return False

        progress[self.client.address]["setGreeting"] = True
        self.save_progress(progress, file=self.deploy_erc_721)
        logger.success(f"{self.client.name} | The ERC-721 contract greeting has been successfully modified")

    async def dicrod_feedback(self):
        if self.client.ds_auth_token in [None, '']:
            logger.warning(f'Skip {self.client.name}: missing DS-token')
            return

        progress = self.load_progress(file=self.feedback)

        contract_address, transaction_hash = await self.searh_contract_address()
        if not contract_address:
            return

        if self.client.address in progress and progress[self.client.address]:
            logger.warning(f"{self.client.name} | Sending feedback is skipped because it has already been done")
            return

        json = {
            'mobile_network_type': 'unknown',
            'content': f'Contract Deployment Completed!\n'
                       f'My Adress: {self.client.address}\n'
                       f'Contract Adress: {contract_address}\n'
                       f'TxHash: {transaction_hash}',
            'tts': False,
            'flags': 0,
        }

        async with AsyncSession() as session:
            try:
                response = await session.post(
                    url='https://discord.com/api/v9/channels/1295483942803210260/messages',
                    headers=self.ds_headers, json=json, proxy=self.client.proxy_init
                )

                if response.status_code != 200:
                    logger.error(
                        f'{self.client.name} |Request error: {response.status_code}'
                        f'Check Discrod authorization token !'
                    )
                    progress[self.client.address] = False
                    self.save_progress(progress, file=self.feedback)
                    return False
                
                logger.success(f'{self.client.name} | Successfully sent feedback. Contract Address: {contract_address}')

                progress[self.client.address] = True
                self.save_progress(progress, file=self.feedback)

            except Exception as e:
                logger.error(f'{self.client.name} | Error when sending feedback: {e}')
                return False
            
    async def gm_gn_message(self):
        if self.client.ds_auth_token in [None, '']:
            logger.warning(f'Skip {self.client.name}: missing DS-token')
            return
        
        if self.check_last_request(self.client.address, self.gm_check_time):
            logger.warning(f"{self.client.name} | It hasn't been 24 hours since the last message was sent")
            return
        
        message = random.choice(['gm', 'gn'])

        json = {
            'mobile_network_type': 'unknown',
            'content': message,
            'tts': False,
            'flags': 0,
        }

        progress = self.load_progress(self.gm_check_time)

        async with AsyncSession() as session:
            try:
                response = await session.post(
                    url='https://discord.com/api/v9/channels/1298244488640335883/messages',
                    headers=self.ds_headers, json=json, proxy=self.client.proxy_init
                )

                if response.status_code != 200:
                    logger.error(
                        f'{self.client.name} |Request error: {response.status_code}'
                        f'Check Discrod authorization token !'
                    )
                    progress[self.client.address] = False
                    self.save_progress(progress, file=self.gm_check_time)
                    return False
                
                logger.success(f'{self.client.name} | Successfully sent a message')

                progress[self.client.address] = {
                    'timestamp': datetime.now().isoformat()
                }
                self.save_progress(progress, file=self.gm_check_time)

            except Exception as e:
                logger.error(f'{self.client.name} | Error when sending a message: {e}')
                return False