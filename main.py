import asyncio
import random
import sys

from typing import List, Dict, Optional
from questionary import select, Choice

from utils.core import *
from generall_settings import *
from utils.worker import Worker
from utils.core.network import Sepolia, Ink_Sepolia
from data.config import TITLE


class Runner:
    @staticmethod
    async def smart_sleep(up, to, msg: str = None):
        duration = random.randint(up, to)
        if msg is None:
            logger.info(f"💤 The next account will start in {duration:.2f} seconds")
        else:
            logger.info(f"💤 {msg} {duration:.2f} seconds")
        await asyncio.sleep(duration)

    @staticmethod
    async def get_proxy_for_account(account_data: Dict) -> Optional[str]:
        try:
            return account_data['proxies']
        except Exception as error:
            logger.info(f"Account {account_data['account_name']} runs without a proxy: {error}")
            return None

    @classmethod
    def get_selected_accounts(cls) -> List[Dict]:
        accounts = get_accounts_data()

        if ACCOUNTS_TO_WORK == 0:
            return accounts

        if isinstance(ACCOUNTS_TO_WORK, int):
            return [accounts[ACCOUNTS_TO_WORK - 1]]

        if isinstance(ACCOUNTS_TO_WORK, tuple):
            return [accounts[i - 1] for i in ACCOUNTS_TO_WORK]

        if isinstance(ACCOUNTS_TO_WORK, list):
            start, end = ACCOUNTS_TO_WORK
            return accounts[start-1:end]

        return []

    async def execute_action(self, account_data: Dict, action: int) -> None:
        account_name = account_data['account_name']
        proxy = await self.get_proxy_for_account(account_data)

        if action == 1:
            network = Sepolia
        else:
            network = Ink_Sepolia

        client = Client(
            name=account_name,
            private_key=account_data['private_key'],
            proxy=proxy,
            network=network,
            ds_auth_token=account_data['ds_auth_token']
        )

        logger.info(
            f"{account_name} | "
            f"Task: {action} | Uses a proxy: {bool(proxy)}"
        )

        try:
            worker = Worker(client=client)
            action_map = {
                1: worker.bridge_sepolia_to_ink,
                2: worker.bridge_ink_to_sepolia,
                3: worker.deploy_contract_erc_721,
                4: worker.verif_contract_erc_721,
                5: worker.set_greeting,
                6: worker.dicrod_feedback,
                7: worker.gm_gn_message
            }

            task_func = action_map.get(action)
            if task_func:
                await task_func()
            else:
                logger.warning(f"{account_name} received an unknown action: {action}")

        except Exception as e:
            logger.error(f"Error when executing a {action} task for an account {account_name}: {e}")

    async def run_account_modules(
        self, 
        account_data: Dict, 
        proxy: Optional[str], 
        parallel_mode: bool = STREAM, 
        actions_to_perform: Optional[List[int]] = None
    ) -> None:
        
        logger.info(f"Account startup: {account_data['account_name']} (parallel mode: {parallel_mode})")

        actions = actions_to_perform if isinstance(actions_to_perform, list) else [actions_to_perform]

        if SHUFFLE_TASKS:
            random.shuffle(actions)

        for action in actions:
            await self.execute_action(account_data, action)
            if len(actions) > 1:
                await self.smart_sleep(
                    SLEEP_TIME_TASKS[0], SLEEP_TIME_TASKS[1],
                    msg=f'The following task for {account_data["account_name"]} will be executed via '
                )
                
    async def run_parallel(self, actions_to_perform: Optional[List[int]] = None) -> None:
        selected_accounts = self.get_selected_accounts()

        if SHUFFLE_ACCOUNTS:
            random.shuffle(selected_accounts)

        tasks = []

        for idx, account_data in enumerate(selected_accounts):
            proxy = await self.get_proxy_for_account(account_data)

            async def account_task():
                await self.run_account_modules(account_data, proxy, actions_to_perform=actions_to_perform)

            if idx > 0:
                if SLEEP_MODE:
                    await self.smart_sleep(SLEEP_TIME_ACCOUNTS[0], SLEEP_TIME_ACCOUNTS[1])

            task = asyncio.create_task(account_task())
            tasks.append(task)

        await asyncio.gather(*tasks)

    async def run_sequential(self, actions_to_perform: Optional[List[int]] = None) -> None:
        selected_accounts = self.get_selected_accounts()

        if SHUFFLE_ACCOUNTS:
            random.shuffle(selected_accounts)

        for idx, account_data in enumerate(selected_accounts):
            proxy = await self.get_proxy_for_account(account_data)
            await self.run_account_modules(account_data, proxy, actions_to_perform=actions_to_perform)
            
            if idx < len(selected_accounts) - 1 and SLEEP_MODE:
                await self.smart_sleep(SLEEP_TIME_ACCOUNTS[0], SLEEP_TIME_ACCOUNTS[1]) 
            await asyncio.sleep(0)          

    async def run(self, actions_to_perform: Optional[List[int]] = None) -> None:
        if STREAM:
            await self.run_parallel(actions_to_perform=actions_to_perform)
        else:
            await self.run_sequential(actions_to_perform=actions_to_perform)


def main():
    print(TITLE)
    print('\033[32m💬 Updates and code support ➡️  https://t.me/divinus_xyz  🍀 Subscribe 🍀 \033[0m')
    print()
    try:
        while True:
            answer = select(
                'What do you want to do?',
                choices=[
                    Choice(" 🚀 Complete all tasks", 'run_all'),
                    Choice(" 📝 Select tasks to be performed", 'select_actions'),
                    Choice(' ❌ Exit', 'exit')
                ],
                qmark='🛠️',
                pointer='👉'
            ).ask()

            runner = Runner()
            if answer == 'run_all':
                print()
                actions_to_perform = [1, 2, 3, 4, 5]
                if SHUFFLE_TASKS:
                    random.shuffle(actions_to_perform)
                asyncio.run(runner.run(actions_to_perform=actions_to_perform))
                print()
            elif answer == 'select_actions':
                actions = select(
                    "Select the tasks to be performed:",
                    choices=[
                        Choice(" 1️⃣  Bridge from Sepolia to Ink Sepolia", 1),
                        Choice(" 2️⃣  Bridge from Ink Sepolia to Sepolia", 2),
                        Choice(" 3️⃣  Deploy contract ERC-721 in netwotk Ink Sepolia", 3),
                        Choice(" 4️⃣  Verification smart contract in Ink Sepolia", 4),
                        Choice(" 5️⃣  Changing the greeting on a smart contract", 5),
                        Choice(" 🍀  Sending feedback to Discord (optional)", 6),
                        Choice(" 🍀  Send a message 'gm' or 'gn' (optional)", 7),
                    ],
                    qmark="🤖",
                    pointer="👉",
                ).ask()
                asyncio.run(runner.run(actions_to_perform=actions))
            elif answer == 'exit':
                sys.exit()
            else:
                print("Unknown action selected")
    except KeyboardInterrupt:
        print("\nExiting the program by signal <Ctrl+C>")
        sys.exit()

if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())