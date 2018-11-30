import numpy as np
import pandas as pd
import collections
import operator
import random


from tsp.tsp import Edge


class TspHeuristic:
    def __init__(self, tsp_config):
        self.tsp = tsp_config
        self.tour = np.zeros_like(tsp_config.distance_matrix,dtype=bool)
        self.num_nodes = self.tour.shape[0]
        self.num_edges = self.num_nodes - 1
        self.stopping_criterion = 2*(self.num_nodes - 1) # All nodes have 2 edges attached, except start/end, which have 1
        self.length = 0
        self.start = None

    @property
    def nodes(self):
        return self.tsp.nodes

    def calculate_tour(self):
        """"""
        raise NotImplementedError()

    def loss(self):
        if not self.get_tour_length():
            self.calculate_tour()
        return self.get_tour_length()

    def get_tour(self):
        """Returns the sequence of the tour (node numbers)."""
        nodes = []
        nodes.append(self.start)

        current = self.start
        next = True

        candidates = np.arange(self.num_nodes)

        print("Starting at node: {}".format(self.start))

        while len(nodes) < self.num_nodes:
            mask = self.tour[current,:] == True # look at row for current node. Connections are true
            possible_nexts = list(candidates[mask])
            print("Possible nexts before comparison: {}".format(possible_nexts))
            if len(possible_nexts) == 1:
                # We either have first or last node. If it's the last, we simply do nothing.
                if current == self.start:
                    next = possible_nexts[0]
            else:
                # We're inside the tour. Remove the node we came from
                try:
                    possible_nexts.remove(nodes[-2])
                except IndexError:
                    # We are at the beginning, but it was probably an edge-base heuristic.
                    # The starting node has two connections. We go in an arbitrary direction from here
                    pass
                next = possible_nexts[0]
            nodes.append(next)
            current = next
        return nodes

    def get_tour_length(self):
        """Returns the length of the final tour."""
        if not self._tour_finished():
            return False
        else:
            tour = self.get_tour()
            for i in range(len(tour)-1):
                self.length += self.tsp.distance_matrix[tour[i]][tour[i+1]]
            self.length += self.tsp.distance_matrix[tour[-1]][tour[1]]
        return self.length

    def get_tour_for_plotting(self):
        """Returns the node coordinates in the final sequence."""
        nodes = self.get_tour()
        tour = [self.nodes[i].coords for i in nodes]
        return tour

    def get_starting_node_for_plotting(self):
        """Returns the first node's coordinates."""
        return self.nodes[self.start].coords

    def _select_new_node(self, size=1):
        """Randomly selects one of the nodes that have no connection so far."""
        available = [i for (i,v) in zip(range(self.tour.shape[0]),self.tour.sum(axis=1) == 0) if v]
        selected = random.sample(available, size)
        return selected[0] if size == 1 else selected

    def _insert_into_tour(self, left, new, right=False):
        """Inserts a node into the tour. If only left is given, the node is appended after left.
        If left and right are given, the new node goes in between left and right."""
        if not right:
            self.tour.itemset((left, new),1)
            self.tour.itemset((new, left),1)
        else:
            self.tour[left][right] = 0 # break connection
            self.tour[right][left] = 0
            self.tour[left][new] = 1 # append new after left
            self.tour[new][left] = 1
            self.tour[new][right] = 1 # prepend new before right
            self.tour[right][new] = 1

    def _get_occupied_nodes_in_tour(self):
        """Returns all nodes with two connections (fully connected)"""
        connected = np.where(self.tour.sum(axis=1) == 2)
        connections = [(i,j) for i in connected[0] for j in np.where(self.tour[i,:]==True)[0] if i < j]
        return connections

    def _tour_finished(self):
        # Tour is finished when all nodes except start and end have 2 neighbors
        if np.sum(self.tour) == self.stopping_criterion:
            return True
        return False

    def _get_last_in_tour(self):
        open_nodes = tuple([i for (i,v) in zip(range(self.num_nodes),self.tour.sum(axis=1) == 1) if v])
        if not open_nodes:
            return False
        else:
            last = set(open_nodes) - set([self.start])
            if len(last) == 1:
                return last.pop()
            else:
                return False

############################################################################################
# The three construction heuristics inherit from a common class


class ConstructionHeuristic(TspHeuristic):
    def __init__(self, tsp_config):
        super().__init__(tsp_config)


class BestInsertion(ConstructionHeuristic):
    def __init__(self, tsp_config):
        super().__init__(tsp_config)

    def _init_algo(self):
        """ Initializes the best insertion algorithm.
        Selects three random nodes as the starting tour.
        """
        self.length = 0
        self.tour = np.zeros_like(self.tsp.distance_matrix)

        # draw 3 random nodes
        start_nodes = self._select_new_node(size=3)
        self._insert_into_tour(start_nodes[0],start_nodes[1],start_nodes[2])
        self.start = start_nodes[0]

    def calculate_tour(self):
        """Runs the best insertion algorithm."""

        self._init_algo()

        while not self._tour_finished():
            try:
                next = self._select_new_node()
            except ValueError:
                print("No more nodes available! {}".format(set(self.tsp.nodes.keys()) - set(self.tour)))
                print("Number of None values in tour: {}".format(len([i for i in self.tour if i is None])))
            left, right = self._calc_loss(next)
            self._insert_into_tour(left, next, right)

    def _calc_loss(self, new_node):
        """Calculates the increase when the new point is inserted between any of the
        existing nodes.
        The returned list's indices can be used to select the left node for insertion, chosen
        where the added distance is minimal.
        """
        deltas = []
        c = self._get_occupied_nodes_in_tour() # returns coordinate tuples of fully connected nodes
        start = self.start
        end = self._get_last_in_tour()

        def d(n1,n2):
            return self.tsp.distance_matrix[n1,n2]

        if len(c) > 0:
            for i in range(len(c)):
                deltas.append(d(c[i][0], new_node) + d(new_node,c[i][1]) - d(c[i][0], c[i][1]))
        else: # We are at the start of the algorithm, there are 3 nodes.
            visited = self.get_tour()
            second = visited[1]
            c = c + [(start, second), (second, end)]
            deltas.append(d(start, new_node)+d(new_node, second) - d(start, second))
            deltas.append(d(second, new_node)+d(new_node, end) - d(second, end))

        #Check between current end and start of tour
        deltas.append(d(end, new_node) + d(new_node,start) - d(end,start))
        c = c + [(end, False)]

        shortest = np.argmin(deltas)
        insert_between = c[shortest]

        return insert_between


class BestBestInsertion(ConstructionHeuristic):
    def __init__(self, tsp_config):
        super().__init__(tsp_config)

    def _init_algo(self):
        """ Initializes the best-best insertion algorithm.
        Selects one random node to start the tour.
        """
        self.tour = np.zeros_like(self.tsp.distance_matrix)
        self.length = 0
        self.start = self._select_new_node()
        next = [operator.itemgetter(0)(n) for n in sorted(enumerate(self.tsp.distance_matrix[self.start,:]), key=operator.itemgetter(1))][1]
        self._insert_into_tour(self.start,next)

    def calculate_tour(self):
        """Runs the best insertion algorithm."""

        self._init_algo()

        while not self._tour_finished():
            left, next, right = self._select_next()
            self._insert_into_tour(left, next, right)

    def _select_next(self):
        """Finds the next node to insert. Determines the distance of all nodes
        not in the tour so far to all the nodes already in the tour.

        Returns:
        A tuple of the format(left, next, right)
        next:   Node number of next to insert
        left:   The node to the left"""
        visited = self.get_tour()

        available = np.where(self.tour.sum(axis=1) == 0)[0] # Select available nodes
        candidates = np.where(self.tour.sum(axis=1) > 0)[0] # Select the nodes already in the tour
        available_mask = np.ones_like(self.tour,dtype=bool) # By default, mask everything
        #Unmask where we could possibly insert
        for row in available:
            for col in candidates:
                available_mask[row][col] = False
        # Build masked distance matrix
        masked_distance = np.ma.array(self.tsp.distance_matrix, mask=available_mask,shrink=False)
        # Get numbers of next and left nodes
        next_after = np.where(masked_distance == masked_distance.min())
        left = next_after[1][0]
        next = next_after[0][0]
        # figure out right node
        if not next_after[1][0] == visited[-1]:
            right = visited[np.where(visited == next_after[1][0])[0][0]+1]
        else:
            right = False

        return (left, next, right)

class ShortestEdge(ConstructionHeuristic):
    def __init__(self, tsp_config):
        super().__init__(tsp_config)
        self.edges = sorted([Edge(i,j,self.tsp) for i in range(self.num_nodes)
                                                for j in range(i+1, self.num_nodes)])
        self.condition_tour_premature = self.num_nodes*2

    def _init_algo(self):
        self.tour = np.zeros_like(self.tsp.distance_matrix)
        self.length = 0
        self.start = self.edges[0].node1
        self._insert_into_tour(self.edges[0].node1,self.edges[0].node2, right=False)


    def _check_constraints(self, new_edge):
        n1 = new_edge.node1
        n2 = new_edge.node2

        # Check prematurely closed loop.
        # If all other rows in matrix have a sum of 2 and the next 2 are both equal to 1, we would finish too early
        mask = [False]*self.num_nodes
        mask[n1] = mask[n2] = True
        if self.tour[n1,:].sum() == 1 and self.tour[n2,:].sum() == 1 and np.all(np.sum(self.tour[mask,:],axis =1)==2):
            return False
        # Check node degrees:
        if self.tour[n1,:].sum() == 2 or self.tour[n2,:].sum() == 2:
            return False
        return True

    def calculate_tour(self):

        self._init_algo()
        edge_stack = self.edges.copy()
        edge_stack.remove(self.edges[0]) # The first edge already inserted

        while not self._tour_finished():
            print("Starting new iteration. Number of edges in tour: {}".format(self.tour.sum()/2))
            for e in edge_stack:
                if self._check_constraints(e) and not self._tour_finished():
                    self._insert_into_tour(e.node1,e.node2,False)
                    edge_stack.remove(e)
                #else:
                #    print("Checks failed for edge {}".format(e))
