#!/usr/bin/env python3
class CodexNotFound(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
