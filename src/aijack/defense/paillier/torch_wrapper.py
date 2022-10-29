import functools

import numpy as np
import torch

HANDLED_FUNCTIONS = {}


def implements(torch_function):
    """Register a torch function override for ScalarTensor"""

    @functools.wraps(torch_function)
    def decorator(func):
        HANDLED_FUNCTIONS[torch_function] = func
        return func

    return decorator


class PaillierTensor(object):
    def __init__(self, paillier_array):
        if type(paillier_array) == list:
            self._paillier_np_array = np.array(paillier_array)
        elif type(paillier_array) == np.ndarray:
            self._paillier_np_array = paillier_array
        else:
            raise TypeError(f"{type(paillier_array)} is not supported.")

    def __repr__(self):
        return "PaillierTensor"

    def decypt(self, sk):
        return torch.Tensor(
            np.vectorize(lambda x: sk.decrypt2float(x))(self._paillier_np_array)
        )

    def tensor(self, sk=None):
        if sk is not None:
            return self.decypt(sk)
        else:
            return torch.zeros(self._paillier_np_array.shape)

    def numpy(self):
        return self._paillier_np_array

    @classmethod
    def __torch_function__(cls, func, types, args=(), kwargs=None):
        if kwargs is None:
            kwargs = {}
        if func not in HANDLED_FUNCTIONS or not all(
            issubclass(t, (torch.Tensor, PaillierTensor)) for t in types
        ):
            return NotImplemented
        return HANDLED_FUNCTIONS[func](*args, **kwargs)

    @implements(torch.add)
    def add(input, other):
        if type(other) in [int, float]:
            return PaillierTensor(input._paillier_np_array + other)
        elif type(other) in [torch.Tensor, PaillierTensor]:
            return PaillierTensor(input._paillier_np_array + other.numpy())
        else:
            raise NotImplementedError(f"{type(other)} is not supported.")

    @implements(torch.sub)
    def sub(input, other):
        if type(other) in [int, float]:
            return PaillierTensor(input._paillier_np_array + (-1 * other))
        elif type(other) in [torch.Tensor, PaillierTensor]:
            return PaillierTensor(input._paillier_np_array + (-1 * other.numpy()))
        else:
            raise NotImplementedError(f"{type(other)} is not supported.")

    @implements(torch.mul)
    def mul(input, other):
        if type(other) in [int, float]:
            return PaillierTensor(input._paillier_np_array * other)
        elif type(other) in [torch.Tensor, PaillierTensor]:
            return PaillierTensor(input._paillier_np_array * other.numpy())
        else:
            raise NotImplementedError(f"{type(other)} is not supported.")

    def __add__(self, other):
        return torch.add(self, other)

    def __sub__(self, other):
        return torch.sub(self, other)

    def __mul__(self, other):
        return torch.mul(self, other)
