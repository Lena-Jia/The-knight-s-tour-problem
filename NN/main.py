import numpy as np
import itertools
import time

knight_moves = np.array(
    [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]])


def create_neurons(width, height):
    neurons = set()
    for i, j, (k, l) in itertools.product(range(width), range(height), knight_moves):
        u, v = i+k, j+l
        if 0 <= u < width and 0 <= v < height and (u, v, i, j) not in neurons:
            neurons.add((i, j, u, v))
    return np.array(list(neurons))


def create_neighbour_bitfield(neurons):
    neis = []
    for i, j, u, v in neurons:
        n1 = np.all(neurons[:, :2] == [i, j], axis=1)
        n2 = np.all(neurons[:, 2:] == [i, j], axis=1)
        n3 = np.all(neurons[:, :2] == [u, v], axis=1)
        n4 = np.all(neurons[:, 2:] == [u, v], axis=1)
        neigh = np.zeros(shape=(len(neurons)), dtype=np.int16)
        neigh[np.argwhere(n1 | n2 | n3 | n4)] = 1
        neis.append(neigh)
    neis = np.array(neis)
    np.fill_diagonal(neis, 0)
    return neis.astype(bool)


def is_2_degree(Vt, N):
    active_neurons = N[Vt.astype(bool)]
    catted = np.concatenate(
        (active_neurons[:, 2:], active_neurons[:, :2]), axis=0)
    _, counts = np.unique(catted, return_counts=True, axis=0)
    return len(counts[counts != 2]) == 0


def hamiltonian_cycle(N, Vt, width, height):
    active_neurons = N[Vt.astype(bool)]
    curr = [0, 0]
    board = np.zeros((width, height), dtype=np.int16)
    index = 0
    while len(active_neurons) > 0:
        board[curr[0], curr[1]] = index
        index += 1
        active_neighbours = active_neurons[
            np.all(active_neurons[:, 2:] == curr, axis=1) |
            np.all(active_neurons[:, :2] == curr, axis=1)
        ]
        if len(active_neighbours) == 0:
            return (False, [])
        nex = active_neighbours[0]
        active_neurons = active_neurons[np.logical_not(
            np.all(active_neurons == nex, axis=1))]
        curr = nex[2:] if np.all(nex[:2] == curr) else nex[:2]
    return (True, board)


def knights_tour(width, height):
    ini = 0
    while True:
        ini += 1
        N = create_neurons(width, height)
        Vt = np.random.randint(2, size=(len(N)), dtype=np.int16)
        Ut = np.zeros(shape=(len(N)), dtype=np.int16)
        G = create_neighbour_bitfield(N)

        for _ in range(40):
            Vt_tile = np.tile(Vt, (len(N), 1))
            Ut_1 = Ut + 3 - np.sum(Vt_tile * G, axis=1) - Vt
            if np.count_nonzero(Ut != Ut_1) == 0:
                break
            Vt[np.argwhere(Ut_1 < 0).ravel()] = 0
            Vt[np.argwhere(Ut_1 > 3).ravel()] = 1
            Ut = Ut_1

            if is_2_degree(Vt, N):
                tour_found, tour = hamiltonian_cycle(N, Vt, width, height)
                if tour_found:
                    # print('The search time is', time.process_time())
                    return tour, 1/ini


if __name__ == "__main__":
    print("running knights tour NN..")
    re, succ = list(knights_tour(5, 5))
    for i in range(len(re)):
        print(re[i])
    print("The success rate is ", succ)
    print('The running time is', time.process_time())


