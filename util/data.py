import numpy as np
from collections import defaultdict
import pickle


class Dataset(object):
    count = 0

    def __init__(self, path, limit=None):
        """
        Wraps dataset and produces batches for the model to consume
        :param path: path to training data for npz file
        """

        # Training Set
        with open(path + 'data.pickle', 'rb') as f:
            data = pickle.load(f)

        normalized_popularity_dict = data['popularity']

        self._n_users = data['users']
        self._n_items = max(normalized_popularity_dict) + 1

        print('self._n_users:', self._n_users)
        print('self._n_items:', self._n_items)

        # Normalized Popularity -----------------------------------------------
        self.normalized_popularity = (np.zeros(self._n_items))
        for i in range(self._n_items):
            self.normalized_popularity[i] = normalized_popularity_dict[i]
        # ---------------------------------------------------------------------

        self.thresholds = data['thresholds']
        prefs = data['prefs']

        self.train_data = []
        self.user_positive_items = {}

        for user in prefs:
            user_dict = prefs[user]

            self.user_positive_items[user] = []

            for user_key in prefs[user]:
                self.user_positive_items[user].extend(user_dict[user_key])
                if user_key == 'train' or user_key == 'vad_tr' or user_key == 'test_tr':
                    # print(user_key)
                    positive_items = user_dict[user_key]
                    # print(positive_items)
                    for item in positive_items:
                        self.train_data.append([user, item])

        # campionare fra gli oggetti negativi non contenuti negli oggetti positivi degli utenti.

        self.test_data = {}

        for user in prefs:
            user_dict = prefs[user]

            for user_key in prefs[user]:
                if user_key == 'test_te':
                    negative_items = self.sample_negative_items(user, 100)
                    assert len(set(negative_items).intersection(self.user_positive_items[user])) == 0
                    self.test_data[user] = (user_dict[user_key], negative_items)

        # print(self.test_data)

        self.user_items = defaultdict(set)
        self.item_users = defaultdict(set)
        for u, i in self.train_data:
            self.user_items[u].add(i)
            self.item_users[i].add(u)

        # LC > Implementing limit ---------------------------------------------
        if limit is not None:
            self.train_data = [element for element in self.train_data if element[0] < limit]

        self.train_data = np.array(self.train_data, dtype=np.uint32)
        self._train_index = np.arange(len(self.train_data), dtype=np.uint32)

        # Get a list version so we do not need to perform type casting
        self.item_users_list = {k: list(v) for k, v in self.item_users.items()}
        self._max_user_neighbors = max([len(x) for x in self.item_users.values()])
        self.user_items = dict(self.user_items)
        self.item_users = dict(self.item_users)

    def sample_negative_items(self, user, n):
        items = []
        for i in range(n):
            item = self._sample_item()
            while item is items or item in self.user_positive_items[user]:
                item = self._sample_item()
            items.append(item)
        return items

    @property
    def train_size(self):
        """
        :return: number of examples in training set
        :rtype: int
        """
        return len(self.train_data)

    @property
    def user_count(self):
        """
        Number of users in dataset
        """
        return self._n_users

    @property
    def item_count(self):
        """
        Number of items in dataset
        """
        return self._n_items

    def _sample_item(self):
        """
        Draw an item uniformly
        """
        return np.random.randint(0, self.item_count)

    def _sample_negative_item(self, user_id, item=None, index=None, upper_bound=None):
        """
        Uniformly sample a negative item
        """
        if user_id > self.user_count:
            raise ValueError("Trying to sample user id: {} > user count: {}".format(user_id, self.user_count))

        # positive_items = self.user_items[user_id]
        positive_items = self.user_positive_items[user_id]

        more_popular_positive_items = set()
        if item is not None:
            # objects more popular than 'item'
            more_popular_positive_items = np.array(list(filter(lambda x: self.normalized_popularity[x] > self.normalized_popularity[item], positive_items)), dtype=np.uint32)

            # ordering more_popular_positive_items by popularity (ASC)
            more_popular_positive_items_popularity = self.normalized_popularity[more_popular_positive_items]

            more_popular_positive_items = more_popular_positive_items[np.argsort(more_popular_positive_items_popularity)]

        if item is None or len(more_popular_positive_items) == 0:
            n = self._sample_item()

            if len(positive_items) >= self.item_count:
                raise ValueError("The User has rated more items than possible %s / %s" % (len(positive_items), self.item_count))

            while n in positive_items or n not in self.item_users:
                n = self._sample_item()
        else:
            # TODO LC > Dealing with popularity
            '''
            select_most_popular_first = False  # True = current experiments (LASCIARE False)
            selected_index = int(index / (upper_bound - 1) * len(more_popular_positive_items))

            if select_most_popular_first:
                selected_index = len(more_popular_positive_items) - 1 - selected_index
            '''
            # print(index)
            # index va da 1 ad upper_bound-1 a passi di 2...
            # esempio upper_bound=4 -> index -> 1,3
            # calcolo selected index.
            # index
            selected_index = int((index - 1) / upper_bound * len(more_popular_positive_items))
            '''
            if index == 1:  # 0 more, 1 less
                selected_index = len(more_popular_positive_items) - 1
            else:
                selected_index = 0
            '''
            n = more_popular_positive_items[selected_index]

            verbose = False
            if verbose:
                print('---------------------------------------')
                print('item:', item)
                print('\nindex:', index)
                print('upper_bound:', upper_bound)
                print('\npositive_items:', positive_items)
                print('self.normalized_popularity[positive_items]:', self.normalized_popularity[positive_items])
                print('\nmore_popular_positive_items:', more_popular_positive_items)
                print('self.normalized_popularity[more_popular_positive_items]:', self.normalized_popularity[more_popular_positive_items])
                print('\nselected_index:', selected_index)
                print('\nselected item (n):', n)
                print('Item popularity:', self.normalized_popularity[item])
                print('Selected Item popularity:', self.normalized_popularity[n])
                print('---------------------------------------')

        return n

    def _generate_data(self, neg_count):
        idx = 0
        self._examples = np.zeros((self.train_size * neg_count, 3),
                                  dtype=np.uint32)
        self._examples[:, :] = 0
        for user_idx, item_idx in self.train_data:
            for _ in range(neg_count):
                neg_item_idx = self._sample_negative_item(user_idx)
                self._examples[idx, :] = [user_idx, item_idx, neg_item_idx]
                idx += 1

    def get_data(self, batch_size: int, neighborhood: bool, neg_count: int, use_popularity=False):
        """
        Batch data together as (user, item, negative item), pos_neighborhood,
        length of neighborhood, negative_neighborhood, length of negative neighborhood

        if neighborhood is False returns only user, item, negative_item so we
        can reuse this for non-neighborhood-based methods.

        :param batch_size: size of the batch
        :param neighborhood: return the neighborhood information or not
        :param neg_count: number of negative samples to uniformly draw per a pos
                          example
        :return: generator
        """
        # Allocate inputs
        batch = np.zeros((batch_size, 3), dtype=np.uint32)
        pos_neighbor = np.zeros((batch_size, self._max_user_neighbors), dtype=np.int32)
        pos_length = np.zeros(batch_size, dtype=np.int32)
        neg_neighbor = np.zeros((batch_size, self._max_user_neighbors), dtype=np.int32)
        neg_length = np.zeros(batch_size, dtype=np.int32)

        # Shuffle index
        np.random.shuffle(self._train_index)

        idx = 0
        print('\n', self._train_index)
        for user_idx, item_idx in self.train_data[self._train_index]:
            # for user_idx, item_idx in self.train_data:
            # TODO: set positive values outside of for loop
            for i in range(neg_count):
                # TODO > modified by Luciano Caroprese. Now a negative item of a user wrt a positive item is an item not explicitly positive or a positive item with an higher popularity

                if use_popularity:
                    '''
                    if i % neg_count == (neg_count - 1):
                        # selecting a negative item
                        neg_item_idx = self._sample_negative_item(user_idx)
                    else:
                        # selecting a positive but more popular item (if there is one)
                        neg_item_idx = self._sample_negative_item(user_idx, item_idx, i, neg_count)
                        
                    '''
                    if i % 2 == 0:
                        # selecting a negative item
                        neg_item_idx = self._sample_negative_item(user_idx)
                    else:
                        # selecting a positive but more popular item (if there is one)
                        neg_item_idx = self._sample_negative_item(user_idx, item_idx, i, neg_count)
                else:
                    neg_item_idx = self._sample_negative_item(user_idx)
                batch[idx, :] = [user_idx, item_idx, neg_item_idx]

                # Get neighborhood information
                if neighborhood:
                    if len(self.item_users.get(item_idx, [])) > 0:
                        pos_length[idx] = len(self.item_users[item_idx])
                        pos_neighbor[idx, :pos_length[idx]] = self.item_users_list[item_idx]
                    else:
                        # Length defaults to 1
                        pos_length[idx] = 1
                        pos_neighbor[idx, 0] = item_idx

                    if len(self.item_users.get(neg_item_idx, [])) > 0:
                        neg_length[idx] = len(self.item_users[neg_item_idx])
                        neg_neighbor[idx, :neg_length[idx]] = self.item_users_list[neg_item_idx]
                    else:
                        # Length defaults to 1
                        neg_length[idx] = 1
                        neg_neighbor[idx, 0] = neg_item_idx

                idx += 1
                # Yield batch if we filled queue
                if idx == batch_size:
                    if neighborhood:
                        max_length = max(neg_length.max(), pos_length.max())
                        yield batch, pos_neighbor[:, :max_length], pos_length, \
                              neg_neighbor[:, :max_length], neg_length
                        pos_length[:] = 1
                        neg_length[:] = 1
                    else:
                        yield batch
                    # Reset
                    idx = 0

        # Provide remainder
        if idx > 0:
            if neighborhood:
                max_length = max(neg_length[:idx].max(), pos_length[:idx].max())
                yield batch[:idx], pos_neighbor[:idx, :max_length], pos_length[:idx], \
                      neg_neighbor[:idx, :max_length], neg_length[:idx]
            else:
                yield batch[:idx]
