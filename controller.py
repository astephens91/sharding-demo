import json
import os
from shutil import copyfile
from typing import List, Dict


filename = "chapter2.txt"

__author__ = "astephens91 with assistance from Peter Marsh"


def load_data_from_file(path=None) -> str:
    with open(path if path else filename, 'r') as f:
        data = f.read()
    return data


class ShardHandler(object):
    """
    Take any text file and shard it into X number of files with
    Y number of replications.
    """

    def __init__(self):
        self.mapping = self.load_map()
        self.last_char_position = 0
        self.replication_level = 0

    mapfile = "mapping.json"

    def write_map(self) -> None:
        """Write the current 'database' mapping to file."""
        with open(self.mapfile, 'w') as m:
            json.dump(self.mapping, m, indent=2)

    def load_map(self) -> Dict:
        """Load the 'database' mapping from file."""
        if not os.path.exists(self.mapfile):
            return dict()
        with open(self.mapfile, 'r') as m:
            return json.load(m)

    def _reset_char_position(self):
        self.last_char_position = 0

    def get_shard_ids(self):
        return sorted([key for key in self.mapping.keys() if '-' not in key])

    def get_replication_ids(self):
        return sorted([key for key in self.mapping.keys() if '-' in key])

    def build_shards(self, count: int, data: str = None) -> [str, None]:
        """Initialize our miniature databases from a clean mapfile. Cannot
        be called if there is an existing mapping -- must use add_shard() or
        remove_shard()."""
        if self.mapping != {}:
            return "Cannot build shard setup -- sharding already exists."

        spliced_data = self._generate_sharded_data(count, data)

        for num, d in enumerate(spliced_data):
            self._write_shard(num, d)

        self.write_map()

    def _write_shard_mapping(self, num: str, data: str, replication=False):
        """Write the requested data to the mapfile. The optional `replication`
        flag allows overriding the start and end information with the shard
        being replicated."""
        if replication:
            parent_shard = self.mapping.get(num[:num.index('-')])
            self.mapping.update(
                {
                    num: {
                        'start': parent_shard['start'],
                        'end': parent_shard['end']
                    }
                }
            )
        else:
            if int(num) == 0:
                # We reset it here in case we perform multiple write operations
                # within the same instantiation of the class. The char position
                # is used to power the index creation.
                self._reset_char_position()

            self.mapping.update(
                {
                    str(num): {
                        'start': (
                            self.last_char_position if
                            self.last_char_position == 0 else
                            self.last_char_position + 1
                        ),
                        'end': self.last_char_position + len(data)
                    }
                }
            )

            self.last_char_position += len(data)

    def _write_shard(self, num: int, data: str) -> None:
        """Write an individual database shard to disk and add it to the
        mapping."""
        if not os.path.exists("data"):
            os.mkdir("data")
        with open(f"data/{num}.txt", 'w') as s:
            s.write(data)
        self._write_shard_mapping(str(num), data)

    def _generate_sharded_data(self, count: int, data: str) -> List[str]:
        """Split the data into as many pieces as needed."""
        splicenum, rem = divmod(len(data), count)

        result = [data[splicenum * z:splicenum * (z + 1)] for z in range(count)]
        # take care of any odd characters
        if rem > 0:
            result[-1] += data[-rem:]

        return result

    def load_data_from_shards(self) -> str:
        """Grab all the shards, pull all the data, and then concatenate it."""
        result = list()

        for db in self.get_shard_ids():
            with open(f'data/{db}.txt', 'r') as f:
                result.append(f.read())
        return ''.join(result)

    def get_replication_level(self):
        keys = [k[-1] for k in self.get_replication_ids()]
        if not keys:
            return 0
        return(int(max(keys)))
        
        

    def add_shard(self) -> None:
        """Add a new shard to the existing pool and rebalance the data."""
        self.mapping = self.load_map()
        data = self.load_data_from_shards()
        keys = [int(z) for z in self.get_shard_ids()]
        keys.sort()
        # why 2? Because we have to compensate for zero indexing
        new_shard_num = max(keys) + 2

        spliced_data = self._generate_sharded_data(new_shard_num, data)

        for num, d in enumerate(spliced_data):
            self._write_shard(num, d)

        self.write_shard()

        self.sync_replication()

    def remove_shard(self) -> None:
        """Loads the data from all shards, removes the extra 'database' file,
        and writes the new number of shards to disk.
        """

        self.mapping = self.load_map()
        data = self.load_data_from_shards()
        keys = [int(z) for z in self.get_shard_ids()]
        keys.sort()

        new_shard_num = max(keys)

        spliced_data = self._generate_sharded_data(new_shard_num, data)

        self.mapping = {}

        os.remove("data/" + str(new_shard_num) + ".txt")

        for num, d in enumerate(spliced_data):
            self._write_shard(num, d)

        self.write_map()

    def add_replication(self) -> None:
        """Add a level of replication so that each shard has a backup. Label
        them with the following format:

        1.txt (shard 1, primary)
        1-1.txt (shard 1, replication 1)
        1-2.txt (shard 1, replication 2)
        2.txt (shard 2, primary)
        2-1.txt (shard 2, replication 1)
        ...etc.

        By default, there is no replication -- add_replication should be able
        to detect how many levels there are and appropriately add the next
        level.
        """

        """returns a list of the absolute paths of the special files in a dir"""
        
        self.replication_level = self.get_replication_level()

        self.replication_level += 1
        file_list = os.listdir("./data")  # list path in directory
        shard_list = []
        keys = self.get_shard_ids()

        for shard_name in file_list:
            if '-' not in shard_name:
                shard_list.append(shard_name)

        for i, file in enumerate(sorted(shard_list)):
            file_source = f'./data/{file}'
            file_destination = f'./data/{i}-{self.replication_level}.txt'
            copyfile(file_source, file_destination)

        for i, k in enumerate(keys):
            self.mapping[f'{i}-{self.replication_level}'] = self.mapping[k]

        self.write_map()

    def remove_replication(self) -> None:
        """Remove the highest replication level.

        If there are only primary files left, remove_replication should raise
        an exception stating that there is nothing left to remove.

        For example:

        1.txt (shard 1, primary)
        1-1.txt (shard 1, replication 1)
        1-2.txt (shard 1, replication 2)
        2.txt (shard 2, primary)
        etc...

        to:

        1.txt (shard 1, primary)
        1-1.txt (shard 1, replication 1)
        2.txt (shard 2, primary)
        etc...
        """
        self.replication_level = self.get_replication_level()

        if self.replication_level > 0:
            

            file_list = os.listdir("./data")  # list path in directory

            for shard_name in file_list:
                if '-' in shard_name:        

                    if int(shard_name[-5]) == self.replication_level:
                        os.remove(f'./data/{shard_name}')

            keys = self.get_shard_ids()

            for i, key in enumerate(keys):
                top_level_key = f'{i}-{self.replication_level}'
                self.mapping.pop(top_level_key)

            self.write_map()
            self.replication_level -= 1

        else:
            print("ERROR: Too few levels to remove")

        # for shard_names in file_list:


    def sync_replication(self) -> None:
        """Verify that all replications are equal to their primaries and that
        any missing primaries are appropriately recreated from their
        replications."""

        def check_primaries():
            primaries = []
            replications = []
            reps_to_be_recreated = []
            file_list = os.listdir("./data")

            for file in file_list:
                if "-" in file:
                    replications.append(file)
                else:
                    primaries.append(file)
            
            for reps in replications:
                primary_num = reps[0]
                statinfo = os.stat("./data/" + reps)
                rep_size = statinfo.st_size
                statinfo2 = os.stat("./data/" + primary_num + ".txt")
                primary_size = statinfo2.st_size
                if rep_size != primary_size:
                    reps_to_be_recreated.append(reps)
                else:
                    print("All good bruh!")
                
            print(reps_to_be_recreated)
            return(reps_to_be_recreated)

        def recreate_replications(r):
            for replication in r:
                primary_num = replication[0]
                copyfile(f'./data/{primary_num}.txt', f'./data/{replication}')

        def recreate_primaries():
            replication_level = self.get_replication_level()


            keys = self.get_shard_ids()

            for prime in keys:
                if not os.path.exists(f'./data/{prime}.txt'):
                    copyfile(f'./data/{prime}-{replication_level}.txt', f'./data/{prime}.txt')
                    print(f'Primary {prime} was recreated from {prime}-{replication_level}.txt')

        def check_both_exists():
            prime_flag = False
            reps_flag = False
            primary_keys = self.get_shard_ids()
            reps_keys = self.get_replication_ids()

            for prime in primary_keys:
                if not os.path.exists(f'./data/{prime}.txt'):
                    prime_flag = True
                    print(f'{prime} does not exist!')
            for reps in reps_keys:
                if not os.path.exists(f'./data/{reps}.txt'):
                    reps_flag = True
                    print(f'{reps} does not exist!')
            if prime_flag:
                raise Exception("No primary!")
            if reps_flag:
                raise Exception("No replication!")

        reps_to_be_recreated = check_primaries()

        try:
            check_both_exists()
        except Exception as e:
            if "primary" in e.args:
                recreate_primaries()
            elif "replication" in e.args:
                recreate_replications(reps_to_be_recreated)
            else:
                raise Exception("Critical failure")
        


    def get_shard_data(self, shardnum=None) -> [str, Dict]:
        """Return information about a shard from the mapfile."""
        if not shardnum:
            return self.get_all_shard_data()
        data = self.mapping.get(shardnum)
        if not data:
            return f"Invalid shard ID. Valid shard IDs: {self.get_shard_ids()}"
        return f"Shard {shardnum}: {data}"

    def get_all_shard_data(self) -> Dict:
        """A helper function to view the mapping data."""
        return self.mapping


s = ShardHandler()

# s.build_shards(5, load_data_from_file())

# print(s.mapping.keys())

# s.remove_shard()
# s.get_replication_level()
# s.remove_shard()
# s.add_replication()
s.sync_replication()

# print(s.mapping.keys())
