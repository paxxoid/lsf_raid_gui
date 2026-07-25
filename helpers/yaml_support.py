from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError
import os


class YAMLParser:
    def __init__(self, config_file_path=None):
        if config_file_path is None:
            config_file_path = os.path.join('config', 'config.yaml')

        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.config_file_path = config_file_path
        
        self.data = self.load_yaml_file(config_file_path)
        
    def load_yaml_file(self, file_path):
        try:
            with open(file_path, 'r') as file:
                return self.yaml.load(file)
        except FileNotFoundError:
            print(f"Error: The file {file_path} was not found.")
            return None
        except YAMLError as e:
            print(f"Error parsing YAML file: {e}")
            return None

    def get_yaml_data(self, category, name):
        if not self.data:
            return None

        if category in self.data:
            return self.data[category].get(name, None)
        else:
            return None

    def update_yaml_data(self, keys, value):
        if self.data is None:
            self.data = {}

        current = self.data

        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}

            current = current[key]

        current[keys[-1]] = value

        try:
            with open(self.config_file_path, "w", encoding="utf-8") as file:
                self.yaml.dump(self.data, file)

            return True

        except OSError as error:
            print(f"Error updating YAML file: {error}")
            return False
