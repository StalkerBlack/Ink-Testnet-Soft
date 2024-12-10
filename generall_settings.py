SLEEP_MODE = True                                     # True or False | Enables sleep after each account is used up

STREAM = False                                        # True or False | Enables parallel mode

ACCOUNTS_IN_STREAM = 10                               # Number of accounts in the stream

SLEEP_TIME_ACCOUNTS = (30, 120)                       # (minimum, maximum) seconds | Sleep time between accounts

SLEEP_TIME_TASKS = (30, 120)                          # (minimum, maximum) seconds | Sleep time between tasks

SHUFFLE_ACCOUNTS = True                               # To mix accounts or not
 
SHUFFLE_TASKS = False                                 # Shuffle the assignments or not


ACCOUNTS_TO_WORK: int | tuple | list = 0              # 0 - all accounts
                                                      # 1 - account No. 1
                                                      # 1, 7 - accounts 1 and 7
                                                      # [5, 25] - accounts 5 through 25 inclusive



""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# Settings for Web3 activities (advanced users only)

MIN_AVAILABLE_BALANCE = int(100000000000000)                        # Minimum balance

RANDOM_RANGE = (0.01, 0.1)                                          # Range of random values

ROUNDING_LEVELS = (4, 5)                                            # Rounding levels