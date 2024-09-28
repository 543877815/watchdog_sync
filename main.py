import time
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from resource_types import OpType, ResourceType
from json_handler import JsonHandler
import shutil


class SyncHandler(FileSystemEventHandler):
    def __init__(self, source_root_dir, target_root_dir, verbose=True):
        self.source_root_dir = source_root_dir + "/"
        self.target_root_dir = target_root_dir + "/"
        self.verbose = verbose
        self.path_mapping = {}
        self.keys = set()
        self.values = set()
        self.init_mapping()
        self.last_op = None
        self.last_op_path_key = None
        self.last_op_path_value = None
        self.last_op_resource = None

    def init_mapping(self):
        print("----------------------------------------------")
        print(f"Initialize path mapping from {JsonHandler.filename}")
        print("----------------------------------------------")
        self.path_mapping = JsonHandler.read_json()
        for [key, value] in self.path_mapping.items():
            self.keys.add(key)
            self.values.add(value)

    def update_mapping(self):
        JsonHandler.write_json(self.path_mapping)

    def on_modified(self, event):
        event_src_path = SyncHandler.path_formatter(event.src_path)

        if not event.is_directory:
            self.sync_file(event_src_path)
            if self.verbose:
                self.changed_log(event_src_path, OpType.MODIFIED, ResourceType.FILE)
        else:
            if self.verbose:
                self.changed_log(event_src_path, OpType.MODIFIED, ResourceType.DIRECTORY)

        src_path = self.get_key(event_src_path)
        desc_path = self.get_mapping(src_path)
        self.set_last(op_type=OpType.MODIFIED, op_src_path=src_path, op_dest_path=desc_path, resource_type=event.is_directory)

    def on_created(self, event):
        event_src_path = SyncHandler.path_formatter(event.src_path)
        if not event.is_directory:
            if self.last_op == OpType.DELETED and self.last_op_path_key is not None and \
                    os.path.basename(self.last_op_path_key) == os.path.basename(event_src_path):  # cut and paste
                self.set_mapping(self.get_key(event_src_path), self.last_op_path_value)
            if self.verbose:
                self.changed_log(event_src_path, OpType.CREATED, ResourceType.FILE)
        else:
            if self.verbose:
                self.changed_log(event_src_path, OpType.CREATED, ResourceType.DIRECTORY)

        src_path = self.get_key(event_src_path)
        desc_path = self.get_mapping(src_path)
        self.set_last(op_type=OpType.CREATED, op_src_path=src_path, op_dest_path=desc_path,
                      resource_type=event.is_directory)

    def on_deleted(self, event):
        event_src_path = SyncHandler.path_formatter(event.src_path)
        if not event.is_directory:
            if self.verbose:
                self.changed_log(event_src_path, OpType.DELETED, ResourceType.FILE)
            [src_path, dest_path] = self.remove_mapping(self.get_key(event_src_path))

            self.set_last(op_type=OpType.DELETED, op_src_path=src_path, op_dest_path=dest_path,
                          resource_type=event.is_directory)
        else:
            if self.verbose:
                self.changed_log(event_src_path, OpType.DELETED, ResourceType.DIRECTORY)

    def on_moved(self, event):
        event_src_path = SyncHandler.path_formatter(event.src_path)
        event_dest_path = SyncHandler.path_formatter(event.dest_path)

        if not event.is_directory:  # file rename
            if self.verbose:
                self.changed_log(event_src_path, OpType.MOVED, ResourceType.FILE, target=event_dest_path)
            old_src_path_key = self.get_key(event_src_path)
            new_src_path_key = self.get_key(event_dest_path)
            if self.need_track(old_src_path_key):
                self.set_mapping(new_src_path_key, self.get_mapping(old_src_path_key))
                [_, dest_path] = self.remove_mapping(old_src_path_key)
                JsonHandler.write_json(self.path_mapping)
                self.set_last(op_type=OpType.MOVED, resource_type=event.is_directory, op_src_path=new_src_path_key,
                              op_dest_path=dest_path)
        else:
            if self.verbose:
                self.changed_log(event_src_path, OpType.MOVED, ResourceType.DIRECTORY)

    def need_track(self, path):
        return path in self.path_mapping

    def set_last(self, op_src_path, op_dest_path, op_type, resource_type):
        self.last_op = op_type
        self.last_op_path_key = op_src_path
        self.last_op_path_value = op_dest_path
        self.last_op_resource = resource_type

    def remove_mapping(self, src_path):
        if src_path in self.path_mapping:
            dest_path = self.path_mapping.pop(src_path)
            self.update_mapping()
            return [src_path, dest_path]
        return None, None

    def set_mapping(self, src_path, dest_path):
        self.path_mapping[src_path] = dest_path
        self.update_mapping()

    def get_mapping(self, src_path):
        return self.path_mapping[src_path] if src_path in self.path_mapping else None

    def get_key(self, abs_src_path):
        return abs_src_path.replace(self.source_root_dir, "")

    def sync_file(self, event_src_path):
        source_path = event_src_path.replace(self.source_root_dir, "")
        if source_path not in self.path_mapping:
            return
        target_path = self.path_mapping[source_path]
        source_file_extension = os.path.splitext(source_path)[1]
        target_file_extension = os.path.splitext(target_path)[1]
        if source_file_extension != target_file_extension:
            print(f"Alert: the extension of source file is {source_file_extension}, "
                  f"while the extension of target file is {target_file_extension}.")
        final_target_path = os.path.join(self.target_root_dir, target_path)
        final_target_dir = os.path.dirname(final_target_path)
        if not os.path.exists(final_target_dir):
            os.makedirs(final_target_dir)
        try:
            shutil.copy2(event_src_path, final_target_path)
            print(f"Synchronizing from {event_src_path} to {final_target_path}.")
        except Exception as e:
            print(e)

    @staticmethod
    def path_formatter(path):
        return path.replace("\\", "/").replace("//", "/")

    def changed_log(self, path, change, source, target=""):
        if source == ResourceType.FILE and not self.need_track(self.get_key(path)):
            return
        if target == "":
            print(f"Detected {source.name} {change.name}: {path}")
        else:
            print(f"Detected {source.name} {change.name}: {path} -> {target}")


class MappingChangeHandler(FileSystemEventHandler):
    def __init__(self, filename, event_handler):
        self.filename = filename
        self.event_handler = event_handler

    def on_modified(self, event):
        if not event.is_directory:
            self.event_handler.init_mapping()
            print(f"Detected {self.filename} changed, reloading...")


if __name__ == "__main__":
    source_dir = "./source"
    target_dir = "./target"
    event_handler = SyncHandler(source_dir, target_dir)
    mapping_handler = MappingChangeHandler(JsonHandler.filename, event_handler)
    observer = Observer()
    observer.schedule(event_handler, path=source_dir, recursive=True)
    observer.start()

    observer1 = Observer()
    observer1.schedule(mapping_handler, path="./mapping", recursive=False)
    observer1.start()

    try:
        print("Monitoring...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer1.stop()
    observer.join()
    observer1.join()
