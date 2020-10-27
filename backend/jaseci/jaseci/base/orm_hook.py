"""
This module includes code related to hooking Jaseci's django models to the
core engine.
"""
from django.core.exceptions import ObjectDoesNotExist

from core.utils import utils
from core.utils.utils import logger
import core as core_mod
from core.utils.mem_hook import mem_hook, json_str_to_jsci_dict
import uuid


class orm_hook(mem_hook):
    """
    Hooks Django ORM database for Jaseci objects to Jaseci's core engine.

    Sets user on initialization to route calls to correct user. This hook
    lives in :class:`User` class as per :field:`User.orm_hook`.
    """

    def __init__(self, user, objects):
        self.user = user
        self.objects = objects
        self.save_list = set()
        super().__init__()

    def context_ids_adapter(self, obj):
        """Adapter for loading context_ids"""
        for i in dir(obj):
            if (i == "context_ids"):
                ctx = {}
                for j in obj.context_ids.obj_list():
                    ctx[j.name] = j.value
                setattr(obj, "context", ctx)
                delattr(obj, "context_ids")
                return True
        return False

    def get_obj_from_store(self, item_id):
        try:
            loaded_obj = self.objects.get(jid=item_id)
        except ObjectDoesNotExist:
            logger.error(
                str(f"Object {item_id} does not exist in Django ORM!")
            )
            return None

        class_for_type = \
            utils.find_class_and_import(loaded_obj.j_type, core_mod)
        ret_obj = class_for_type(h=self, auto_save=False)
        utils.map_assignment_of_matching_fields(ret_obj, loaded_obj)
        assert(uuid.UUID(ret_obj.jid) == loaded_obj.jid)

        # Unwind jsci_payload for fields beyond element object
        obj_fields = json_str_to_jsci_dict(loaded_obj.jsci_obj, ret_obj)
        for i in obj_fields.keys():
            setattr(ret_obj, i, obj_fields[i])

        if (self.context_ids_adapter(ret_obj)):
            ret_obj.save()

        return ret_obj

    def has_obj_in_store(self, item_id):
        """
        Checks for object existance in store
        """
        return self.objects.filter(jid=item_id).count()

    def save_obj_to_store(self, item):
        # import traceback as tb; tb.print_stack();  # noqa
        self.save_list.add(item)

    def commit_obj(self, item):
        item_from_db, created = self.objects.get_or_create(
            user=self.user, jid=item.id
        )
        utils.map_assignment_of_matching_fields(item_from_db, item)
        item_from_db.jsci_obj = item.jsci_payload()
        item_from_db.save()

    def destroy_obj_from_store(self, item):
        try:
            self.objects.get(user=self.user, jid=item.id).delete()
        except ObjectDoesNotExist:
            logger.error("Object does not exists so delete aborted!")

    def commit(self):
        """Write through all saves to store"""
        # dist = {}
        # for i in self.save_list:
        #     if (type(i).__name__ in dist.keys()):
        #         dist[type(i).__name__] += 1
        #     else:
        #         dist[type(i).__name__] = 1
        # print(dist)
        for i in self.save_list:
            self.commit_obj(i)
        self.save_list = set()