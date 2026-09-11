from __future__ import annotations

import asyncio
from dataclasses import dataclass

from autoflow.application.kernels.operations import KernelOperation


@dataclass
class KernelEventSubscription:
    queue: asyncio.Queue[list[KernelOperation]]
    _broker: KernelEventBroker

    def close(self) -> None:
        self._broker.unsubscribe(self)


class KernelEventBroker:
    def __init__(self, *, queue_size: int = 1) -> None:
        if queue_size < 1:
            raise ValueError("queue_size must be positive")
        self._queue_size = queue_size
        self._subscriptions: list[KernelEventSubscription] = []

    def subscribe(self) -> KernelEventSubscription:
        subscription = KernelEventSubscription(
            asyncio.Queue(maxsize=self._queue_size), self
        )
        self._subscriptions.append(subscription)
        return subscription

    def unsubscribe(self, subscription: KernelEventSubscription) -> None:
        try:
            self._subscriptions.remove(subscription)
        except ValueError:
            pass

    def publish(self, snapshot: list[KernelOperation]) -> None:
        for subscription in tuple(self._subscriptions):
            while subscription.queue.full():
                subscription.queue.get_nowait()
            subscription.queue.put_nowait(snapshot)
