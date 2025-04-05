#!/usr/bin/python3

import random

def randstr(n):
    return random.randbytes(n).hex()

for i in range(10000):
    print(f'tst-{randstr(10)} "{randstr(100)}"')
