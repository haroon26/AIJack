import copy

import torch

from ..core import BaseClient
from ..core.utils import GRADIENTS_TAG, PARAMETERS_TAG
from ..optimizer import AdamFLOptimizer, SGDFLOptimizer


class FedAvgClient(BaseClient):
    """Client of FedAVG for single process simulation

    Args:
        model (torch.nn.Module): local model
        user_id (int, optional): if of this client. Defaults to 0.
        lr (float, optional): learning rate. Defaults to 0.1.
        send_gradient (bool, optional): if True, communicate gradient to the server. otherwise, communicates model parameters. Defaults to True.
        optimizer_type_for_global_grad (str, optional): type of optimizer for model update with global gradient. sgd|adam. Defaults to "sgd".
        server_side_update (bool, optional): If True, the global model update is conducted in the server side. Defaults to True.
        optimizer_kwargs_for_global_grad (dict, optional): kwargs for the optimizer for global gradients. Defaults to {}.
        device (str, optional): device type. Defaults to "cpu".
    """

    def __init__(
        self,
        model,
        user_id=0,
        lr=0.1,
        send_gradient=True,
        optimizer_type_for_global_grad="sgd",
        server_side_update=True,
        optimizer_kwargs_for_global_grad={},
        device="cpu",
    ):
        super(FedAvgClient, self).__init__(model, user_id=user_id)
        self.lr = lr
        self.send_gradient = send_gradient
        self.server_side_update = server_side_update
        self.device = device

        if not self.server_side_update:
            self._setup_optimizer_for_global_grad(
                optimizer_type_for_global_grad, **optimizer_kwargs_for_global_grad
            )

        self.prev_parameters = []
        for param in self.model.parameters():
            self.prev_parameters.append(copy.deepcopy(param))

        self.initialized = False

    def _setup_optimizer_for_global_grad(self, optimizer_type, **kwargs):
        if optimizer_type == "sgd":
            self.optimizer_for_gloal_grad = SGDFLOptimizer(
                self.model.parameters(), lr=self.lr, **kwargs
            )
        elif optimizer_type == "adam":
            self.optimizer_for_gloal_grad = AdamFLOptimizer(
                self.model.parameters(), lr=self.lr, **kwargs
            )
        elif optimizer_type == "none":
            self.optimizer_for_gloal_grad = None
        else:
            raise NotImplementedError(
                f"{optimizer_type} is not supported. You can specify `sgd`, `adam`, or `none`."
            )

    def upload(self):
        """Upload the current local model state"""
        if self.send_gradient:
            return self.upload_gradients()
        else:
            return self.upload_parameters()

    def upload_parameters(self):
        """Upload the model parameters"""
        return self.model.state_dict()

    def upload_gradients(self):
        """Upload the local gradients"""
        gradients = []
        for param, prev_param in zip(self.model.parameters(), self.prev_parameters):
            gradients.append((prev_param - param) / self.lr)
        return gradients

    def revert(self):
        """Revert the local model state to the previous global model"""
        for param, prev_param in zip(self.model.parameters(), self.prev_parameters):
            if param is not None:
                param = prev_param

    def download(self, new_global_model):
        """Download the new global model"""
        if self.server_side_update or (not self.initialized):
            # receive the new global model as the model state
            self.model.load_state_dict(new_global_model)
        else:
            # receive the new global model as the global gradients
            self.revert()
            self.optimizer_for_gloal_grad.step(new_global_model)

        if not self.initialized:
            self.initialized = True

        self.prev_parameters = []
        for param in self.model.parameters():
            self.prev_parameters.append(copy.deepcopy(param))


class MPIFedAVGClient(BaseClient):
    """Client of FedAVG for mpi-backend simulation"""

    def __init__(self, comm, model, user_id=0, lr=0.1, device="cpu"):
        super(MPIFedAVGClient, self).__init__(model, user_id=user_id)
        self.comm = comm
        self.lr = lr
        self.device = device

        self.prev_parameters = []
        for param in self.model.parameters():
            self.prev_parameters.append(copy.deepcopy(param))

    def upload(self):
        self.upload_gradient()

    def upload_gradient(self, destination_id=0):
        self.gradients = []
        for param, prev_param in zip(self.model.parameters(), self.prev_parameters):
            self.gradients.append((prev_param - param) / self.lr)
        self.comm.send(self.gradients, dest=destination_id, tag=GRADIENTS_TAG)

    def download(self):
        new_parameters = self.comm.recv(tag=PARAMETERS_TAG)
        for params, new_params in zip(self.model.parameters(), new_parameters):
            params.data = torch.Tensor(new_params).reshape(params.shape).to(self.device)
