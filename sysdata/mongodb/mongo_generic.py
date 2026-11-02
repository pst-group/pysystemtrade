from copy import copy
from datetime import date, time

from syscore.constants import arg_not_supplied
from syscore.exceptions import missingData, existingData
from sysdata.mongodb.mongo_connection import (
    mongoConnection,
    MONGO_ID_KEY,
    mongo_clean_ints,
    clean_mongo_host,
)
from syslogging.logger import get_logger


class mongoDataWithSingleKey(object):
    """
    Read and write data class to get data from a mongo database

    """

    def __init__(self, collection_name, key_name, mongo_db=arg_not_supplied):
        self.init_mongo(collection_name, key_name, mongo_db=mongo_db)

    def init_mongo(
        self,
        collection_name: str,
        key_name: str,
        mongo_db=arg_not_supplied,
    ):
        mongo_object = mongoConnection(collection_name, mongo_db=mongo_db)

        self._mongo = mongo_object
        self._key_name = key_name

        # this won't create the index if it already exists
        # if a different index exists (FIX ME WILL HAPPEN UNTIL NEW DATA READY)...
        try:
            self._mongo.create_index(self.key_name)
        except:
            pass
            ## no big deal

    def __repr__(self):
        return self.name

    @property
    def key_name(self) -> str:
        return self._key_name

    @property
    def name(self) -> str:
        col = self._mongo.collection_name
        db = self._mongo.database_name
        host = clean_mongo_host(self._mongo.host)

        return f"mongoData connection for {col}/{db}, {host}"

    @property
    def collection(self):
        return self._mongo.collection

    def get_list_of_keys(self) -> list:
        return self.collection.distinct(self.key_name)

    def get_max_of_keys(self) -> int:
        doc = self.collection.find_one(sort=[(self.key_name, -1)])
        if doc is None:
            return 0
        if self.key_name in doc:
            return doc[self.key_name]
        else:
            return 0

    def get_list_of_values_for_dict_key(self, dict_key):
        return [
            row[dict_key]
            for row in self.collection.find(
                {self.key_name: {"$exists": True}}, {dict_key: 1}
            )
        ]

    def get_result_dict_for_key(self, key) -> dict:
        key_name = self.key_name
        result_dict = self.collection.find_one({key_name: key})
        if result_dict is None:
            raise missingData("Key %s not found in Mongo data" % key)

        result_dict.pop(MONGO_ID_KEY)

        return result_dict

    def get_result_dict_for_key_without_key_value(self, key) -> dict:
        key_name = self.key_name
        result_dict = self.get_result_dict_for_key(key)

        result_dict.pop(key_name)

        return result_dict

    def get_list_of_result_dict_for_custom_dict(self, custom_dict: dict) -> list:
        cursor = self._mongo.collection.find(custom_dict)
        dict_list = [db_entry for db_entry in cursor]
        _ = [dict_item.pop(MONGO_ID_KEY) for dict_item in dict_list]

        return dict_list

    def key_is_in_data(self, key):
        try:
            self.get_result_dict_for_key(key)
        except missingData:
            return False
        else:
            return True

    def delete_data_without_any_warning(self, key):
        key_name = self.key_name

        if not self.key_is_in_data(key):
            raise missingData("%s:%s not in data %s" % (key_name, key, self.name))

        self.collection.remove({key_name: key})

    def delete_data_with_any_warning_for_custom_dict(self, custom_dict: dict):
        self.collection.remove(custom_dict)

    def add_data(self, key, data_dict: dict, allow_overwrite=False, clean_ints=True):
        if clean_ints:
            cleaned_data_dict = mongo_clean_ints(data_dict)
        else:
            cleaned_data_dict = copy(data_dict)

        if self.key_is_in_data(key):
            if allow_overwrite:
                self._update_existing_data_with_cleaned_dict(key, cleaned_data_dict)
            else:
                raise existingData(
                    "Can't overwrite existing data %s/%s for %s"
                    % (self.key_name, key, self.name)
                )
        else:
            try:
                self._add_new_cleaned_dict(key, cleaned_data_dict)
            except:
                ## this could happen if the key has just been added most likely for logs
                raise existingData(
                    "Can't overwrite existing data %s/%s for %s"
                    % (self.key_name, key, self.name)
                )

    def _update_existing_data_with_cleaned_dict(self, key, cleaned_data_dict):
        key_name = self.key_name
        self.collection.update_one({key_name: key}, {"$set": cleaned_data_dict})

    def _add_new_cleaned_dict(self, key, cleaned_data_dict):
        key_name = self.key_name
        cleaned_data_dict[key_name] = key
        self.collection.insert_one(cleaned_data_dict)


class mongoDataWithMultipleKeys(object):
    """
    Read and write data class to get data from a mongo database

    Use this if you want a collection with a compound index, ie if you need to
    search for documents using more than one field
    """

    def __init__(
        self,
        collection_name: str,
        mongo_db=arg_not_supplied,
        index_config: dict = None,
    ):
        self._log = get_logger("mongoDataWithMultipleKeys")
        self.init_mongo(collection_name, mongo_db=mongo_db, index_config=index_config)

    def init_mongo(
        self,
        collection_name: str,
        mongo_db=arg_not_supplied,
        index_config=None,
    ):
        self._mongo = mongoConnection(collection_name, mongo_db=mongo_db)

        if index_config:
            try:
                self._mongo.create_compound_index(index_config)
            except Exception as exc:
                self._log.error(
                    "Failed to create compound index for collection '%s', "
                    "check config: %s" % (collection_name, exc),
                )

    def __repr__(self):
        return self.name

    @property
    def name(self) -> str:
        col = self._mongo.collection_name
        db = self._mongo.database_name
        host = clean_mongo_host(self._mongo.host)

        return f"mongoData connection for {col}/{db}, {host}"

    def get_list_of_all_dicts(self) -> list:
        cursor = self._mongo.collection.find()
        dict_list = [db_entry for db_entry in cursor]
        _ = [dict_item.pop(MONGO_ID_KEY) for dict_item in dict_list]

        return dict_list

    def get_result_dict_for_dict_keys(self, dict_of_keys: dict) -> dict:
        result_dict = self._mongo.collection.find_one(dict_of_keys)
        if result_dict is None:
            raise missingData("Keys %s not found in Mongo data" % dict_of_keys)

        result_dict.pop(MONGO_ID_KEY)

        return result_dict

    def get_list_of_result_dicts_for_dict_keys(self, dict_of_keys: dict) -> list:
        cursor_of_result_dicts = self._mongo.collection.find(dict_of_keys)

        if cursor_of_result_dicts is None:
            return []

        list_of_result_dicts = list(cursor_of_result_dicts)
        _ = [result_dict.pop(MONGO_ID_KEY) for result_dict in list_of_result_dicts]

        return list_of_result_dicts

    def key_dict_is_in_data(self, dict_of_keys: dict) -> bool:
        try:
            self.get_result_dict_for_dict_keys(dict_of_keys)
        except missingData:
            return False
        else:
            return True

    def add_data(
        self,
        dict_of_keys: dict,
        data_dict: dict,
        allow_overwrite=False,
        clean_ints=True,
    ):
        if clean_ints:
            cleaned_data_dict = mongo_clean_ints(data_dict)
        else:
            cleaned_data_dict = copy(data_dict)

        if self.key_dict_is_in_data(dict_of_keys):
            if allow_overwrite:
                self._update_existing_data_with_cleaned_dict(
                    dict_of_keys, cleaned_data_dict
                )
            else:
                raise existingData(
                    "Can't overwrite existing data %s for %s"
                    % (str(dict_of_keys), self.name)
                )
        else:
            self._add_new_cleaned_dict(dict_of_keys, cleaned_data_dict)

    def _update_existing_data_with_cleaned_dict(
        self, dict_of_keys: dict, cleaned_data_dict: dict
    ):
        self._mongo.collection.update_one(dict_of_keys, {"$set": cleaned_data_dict})

    def _add_new_cleaned_dict(self, dict_of_keys: dict, cleaned_data_dict: dict):
        dict_with_both_keys_and_data = {}
        dict_with_both_keys_and_data.update(cleaned_data_dict)
        dict_with_both_keys_and_data.update(dict_of_keys)

        self._mongo.collection.insert_one(dict_with_both_keys_and_data)

    def delete_data_without_any_warning(self, dict_of_keys):
        self._mongo.collection.remove(dict_of_keys)


_date = date
_time = time
