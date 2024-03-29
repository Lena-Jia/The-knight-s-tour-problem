# -*- coding: utf-8 -*-
"""
An implementation of the policyValueNet in PyTorch
Tested in PyTorch 0.2.0 and 0.3.0

@author: Dan Jia, inspired by Junxiao Song
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.autograd import Variable
import numpy as np
import KnightLogic as kl


def set_learning_rate(optimizer, lr):
    """Sets the learning rate to the given value"""
    for param_group in optimizer.param_groups:
        param_group['lr'] = lr


class Net(nn.Module):
    """policy-value network module"""
    def __init__(self, board_width, board_height):
        super(Net, self).__init__()

        self.board_width = board_width
        self.board_height = board_height

        # common layers
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)

        # action policy layers
        self.act_conv1 = nn.Conv2d(128, 4, kernel_size=1)
        self.act_fc1 = nn.Linear(4 * self.board_width * self.board_height, self.board_width * self.board_height)

        # state value layers
        self.val_conv = nn.Conv2d(128, 2, kernel_size=1)
        self.val_fc1 = nn.Linear(2 * self.board_width * self.board_height, 64)
        self.val_fc2 = nn.Linear(64, 1)

    def forward(self, state_input):

        # common layers
        # print('state input', state_input.size())
        x = F.relu(self.conv1(state_input))
        # print('x', x.size())
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))

        # action policy layers
        # print('action policy layers', x.size())
        x_act = F.relu(self.act_conv1(x))
        # print('x_act1', x_act.size())
        x_act = x_act.view(-1, 4 * self.board_width * self.board_height)
        # print('x_act2', x_act.size())
        # x_act = F.log_softmax(self.act_fc1(x_act), dim=1)
        x_act = F.log_softmax(self.act_fc1(x_act), dim=1)
        # print('x_act3', x_act.size())
        # x_act = x_act.view(self.board_width, self.board_height)

        # state value layers
        x_val = F.relu(self.val_conv(x))
        x_val = x_val.view(-1, 2 * self.board_width * self.board_height)
        x_val = F.relu(self.val_fc1(x_val))
        x_val = F.tanh(self.val_fc2(x_val))

        return x_act, x_val


class PolicyValueNet:
    """policy-value network """
    def __init__(self, board_width=7, board_height=5, model_file=None, use_gpu=False):
        self.use_gpu = use_gpu
        self.board_width = board_width
        self.board_height = board_height
        self.l2_const = 1e-4  # coef of l2 penalty
        # the policy value net module
        if self.use_gpu:
            self.policy_value_net = Net(board_width, board_height).cuda()
        else:
            self.policy_value_net = Net(board_width, board_height)
        self.optimizer = optim.Adam(self.policy_value_net.parameters(), weight_decay=self.l2_const)

        if model_file:
            net_params = torch.load(model_file)
            self.policy_value_net.load_state_dict(net_params)

    def policy_value(self, state_batch):
        """
        input: a batch of states
        output: a batch of action probabilities and state values
        """

        if self.use_gpu:
            state_batch = Variable(torch.FloatTensor(state_batch).cuda())
            log_act_probs, value = self.policy_value_net(state_batch)
            act_probs = np.exp(log_act_probs.data.cpu().numpy())
            return act_probs, value.data.cpu().numpy()
        else:
            state_batch = Variable(torch.FloatTensor(np.array(state_batch)))
            log_act_probs, value = self.policy_value_net(state_batch)
            act_probs = np.exp(log_act_probs.data.numpy())

            return act_probs, value.data.numpy()

    def policy_value_fn(self, board):
        """
        input: board
        output: a list of (action, probability) tuples for each available action and the score of the board state
        """

        legal_positions = board.knight_walk()
        _, current_state = board.get_current_player()
        states = board.states
        states_array = np.ascontiguousarray(states.reshape(-1, self.board_width, self.board_height))
        states_torch = torch.from_numpy(states_array).float()
        if self.use_gpu:
            log_act_probs, value = self.policy_value_net(Variable(torch.from_numpy(states_array)).cuda().float())
            act_probs = np.exp(log_act_probs.data.cpu().numpy().flatten())
        else:
            log_act_probs, value = self.policy_value_net(states_torch)
            act_probs = np.exp(log_act_probs.data.numpy().flatten())

        prob = []
        for legal_position in legal_positions:
            pos = legal_position[0] * self.board_width + legal_position[1]
            prob.append(act_probs[pos])

        act_probs = zip(legal_positions, prob)
        # print(list(act_probs))
        value = value.data[0][0]

        return act_probs, value

    def train_step(self, state_batch, mcts_probs, label, lr):
        """perform a training step"""

        # wrap in Variable
        if self.use_gpu:
            state_batch = Variable(torch.FloatTensor(state_batch).cuda())
            mcts_probs = Variable(torch.FloatTensor(mcts_probs).cuda())

        else:
            state_batch = Variable(torch.FloatTensor(np.array(state_batch)))
            mcts_probs = Variable(torch.FloatTensor(np.array(mcts_probs)))
            label_batch = Variable(torch.FloatTensor(label))

        # zero the parameter gradients
        self.optimizer.zero_grad()
        # set learning rate
        set_learning_rate(self.optimizer, lr)

        # forward

        log_act_probs, value = self.policy_value_net(state_batch)
        mcts_probs = mcts_probs.view(-1, self.board_width * self.board_height)

        # define the loss = (z - v)^2 - pi^T * log(p) + c||theta||^2
        # Note: the L2 penalty is incorporated in optimizer

        value_loss = F.mse_loss(value.view(-1), target=label_batch)

        policy_loss = -torch.mean(torch.sum(mcts_probs*log_act_probs, 1))
        # print('policy_loss size', policy_loss.size())
        loss = value_loss + policy_loss

        # backward and optimize
        loss.backward()
        self.optimizer.step()

        # calc policy entropy, for monitoring only
        entropy = -torch.mean(torch.sum(torch.exp(log_act_probs) * log_act_probs, 1))

        # for pytorch version >= 0.5 please use the following line instead.
        return loss.item(), entropy.item()

    def get_policy_param(self):
        net_params = self.policy_value_net.state_dict()
        return net_params

    def save_model(self, model_file):
        """ save model params to file """
        net_params = self.get_policy_param()  # get model params
        torch.save(net_params, model_file)
